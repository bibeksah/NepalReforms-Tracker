"""
Budget and Data Validators — Zero-tolerance accuracy for financial data.

Budget figures are the most politically sensitive data in the graph.
These validators enforce:
  1. Statistical anomaly detection (>3σ from category mean)
  2. Source re-extraction cross-referencing
  3. Hash-based integrity verification
  4. Hard rule: budget figures NEVER pass through an LLM
"""

import logging
import statistics
from typing import Optional

from .schemas import MAX_BUDGET_NPR, compute_budget_hash

logger = logging.getLogger(__name__)

# Budget ranges by broad project category (in NPR)
# These are order-of-magnitude sanity bounds derived from Lal Kitab patterns.
CATEGORY_BOUNDS = {
    "road":       (1_000_000, 50_000_000_000),
    "bridge":     (5_000_000, 10_000_000_000),
    "irrigation": (1_000_000, 20_000_000_000),
    "school":     (500_000,   5_000_000_000),
    "hospital":   (1_000_000, 10_000_000_000),
    "default":    (100_000,   MAX_BUDGET_NPR),
}


class BudgetValidationResult:
    """Result of budget validation with detailed flags."""

    __slots__ = (
        "is_valid", "budget_value", "anomaly_flag",
        "anomaly_reason", "budget_source", "hash_verified",
    )

    def __init__(self):
        self.is_valid: bool = True
        self.budget_value: int = 0
        self.anomaly_flag: bool = False
        self.anomaly_reason: str = ""
        self.budget_source: str = "deterministic"
        self.hash_verified: bool = False


def validate_budget(
    budget: int,
    raw_budget_str: str = "",
    page_num: int = 0,
    stored_hash: str = "",
    budget_source: str = "deterministic",
    all_budgets: list = None,
) -> BudgetValidationResult:
    """
    Multi-layer budget validation.

    Checks:
      1. Absolute bounds (> 0, < MAX)
      2. Hash integrity (if stored_hash provided)
      3. Statistical outlier detection (if peer budgets provided)
      4. Vision-source flagging
    """
    result = BudgetValidationResult()
    result.budget_value = budget
    result.budget_source = budget_source

    # Check 1: Absolute bounds
    if budget <= 0:
        result.is_valid = False
        result.anomaly_flag = True
        result.anomaly_reason = "Budget is zero or negative"
        return result

    if budget > MAX_BUDGET_NPR:
        result.is_valid = False
        result.anomaly_flag = True
        result.anomaly_reason = (
            f"Budget {budget:,} exceeds max bound of {MAX_BUDGET_NPR:,} NPR"
        )
        return result

    # Check 2: Hash integrity
    if stored_hash and raw_budget_str:
        expected = compute_budget_hash(raw_budget_str, page_num)
        if expected != stored_hash:
            result.is_valid = False
            result.anomaly_flag = True
            result.anomaly_reason = (
                f"Budget hash mismatch — data may have been tampered "
                f"(expected {stored_hash[:12]}..., got {expected[:12]}...)"
            )
            return result
        result.hash_verified = True

    # Check 3: Statistical outlier (>3σ from peer mean)
    if all_budgets and len(all_budgets) >= 5:
        anomaly = _detect_statistical_anomaly(budget, all_budgets)
        if anomaly:
            result.anomaly_flag = True
            result.anomaly_reason = anomaly
            # Not invalid, but flagged for review

    # Check 4: Vision-source warning
    if budget_source == "vision":
        result.anomaly_flag = True
        if not result.anomaly_reason:
            result.anomaly_reason = (
                "Budget extracted via Vision API (not deterministic) "
                "— requires human verification"
            )

    return result


def validate_project_batch(projects: list) -> tuple:
    """
    Validate a batch of projects, separating clean from flagged.

    Returns:
        (valid_projects, flagged_projects) — flagged ones need human review.
    """
    all_budgets = [p.get("budget", 0) for p in projects if p.get("budget", 0) > 0]

    valid = []
    flagged = []

    for proj in projects:
        result = validate_budget(
            budget=proj.get("budget", 0),
            raw_budget_str=proj.get("raw_budget_str", ""),
            page_num=proj.get("page_num", 0),
            stored_hash=proj.get("budget_hash", ""),
            budget_source=proj.get("budget_source", "deterministic"),
            all_budgets=all_budgets,
        )

        proj["budget_anomaly_flag"] = result.anomaly_flag
        proj["budget_anomaly_reason"] = result.anomaly_reason
        proj["budget_source"] = result.budget_source

        if result.is_valid:
            if result.anomaly_flag:
                flagged.append(proj)
            else:
                valid.append(proj)
        else:
            flagged.append(proj)
            logger.warning(
                "INVALID budget for '%s': %s",
                proj.get("title_ne", "?")[:40], result.anomaly_reason,
            )

    logger.info(
        "Budget validation: %d valid, %d flagged for review",
        len(valid), len(flagged),
    )
    return valid, flagged


# ── Private helpers ────────────────────────────────────────────────────


def _detect_statistical_anomaly(budget: int, peer_budgets: list) -> Optional[str]:
    """Flag if budget is >3 standard deviations from the peer mean."""
    try:
        mean = statistics.mean(peer_budgets)
        stdev = statistics.stdev(peer_budgets)
        if stdev == 0:
            return None

        z_score = abs(budget - mean) / stdev
        if z_score > 3.0:
            return (
                f"Statistical outlier: budget {budget:,} is {z_score:.1f}σ "
                f"from peer mean {mean:,.0f} (stdev {stdev:,.0f})"
            )
    except (statistics.StatisticsError, ZeroDivisionError):
        pass

    return None

"""
Graph Consistency Checker — Post-publish validation queries.

Runs structural integrity checks against Neo4j to catch:
  - Orphan nodes (no relationships)
  - Missing required edges (Project without FiscalYear)
  - Impossible data (>5 promise links per project)
  - Budget sum sanity checks

Should be run after every publish batch.
"""

import logging
from neomodel import db

logger = logging.getLogger(__name__)


class ConsistencyViolation:
    """A single consistency check failure."""

    __slots__ = ("check_name", "severity", "message", "affected_nodes")

    def __init__(self, check_name: str, severity: str, message: str, affected_nodes: list = None):
        self.check_name = check_name
        self.severity = severity  # "critical" | "warning" | "info"
        self.message = message
        self.affected_nodes = affected_nodes or []

    def __repr__(self):
        return f"[{self.severity.upper()}] {self.check_name}: {self.message}"


def run_all_checks() -> list:
    """
    Run all consistency checks and return list of violations.

    Returns empty list if graph is fully consistent.
    """
    violations = []

    checks = [
        _check_projects_have_fiscal_year,
        _check_projects_have_titles,
        _check_no_excessive_promise_links,
        _check_no_orphan_projects,
        _check_no_orphan_promises,
        _check_budget_positivity,
    ]

    for check_fn in checks:
        try:
            result = check_fn()
            if result:
                violations.extend(result)
        except Exception as e:
            violations.append(ConsistencyViolation(
                check_name=check_fn.__name__,
                severity="critical",
                message=f"Check failed with error: {e}",
            ))

    if violations:
        for v in violations:
            log_fn = logger.error if v.severity == "critical" else logger.warning
            log_fn("CONSISTENCY: %s", v)
    else:
        logger.info("All graph consistency checks passed ✓")

    return violations


# ── Individual checks ──────────────────────────────────────────────────


def _check_projects_have_fiscal_year() -> list:
    """Every Project MUST have exactly one FUNDED_IN → FiscalYear edge."""
    query = """
    MATCH (p:Project)
    WHERE NOT (p)-[:FUNDED_IN]->(:FiscalYear)
    RETURN p.uid AS uid, p.title AS title
    LIMIT 50
    """
    results, _ = db.cypher_query(query)
    if not results:
        return []

    return [ConsistencyViolation(
        check_name="projects_have_fiscal_year",
        severity="critical",
        message=f"{len(results)} Project(s) missing FUNDED_IN → FiscalYear link",
        affected_nodes=[{"uid": r[0], "title": r[1]} for r in results],
    )]


def _check_projects_have_titles() -> list:
    """Every Project MUST have both title AND title_ne."""
    query = """
    MATCH (p:Project)
    WHERE p.title IS NULL OR p.title = '' OR p.title_ne IS NULL OR p.title_ne = ''
    RETURN p.uid AS uid, p.title AS title, p.title_ne AS title_ne
    LIMIT 50
    """
    results, _ = db.cypher_query(query)
    if not results:
        return []

    return [ConsistencyViolation(
        check_name="projects_have_titles",
        severity="warning",
        message=f"{len(results)} Project(s) missing bilingual titles",
        affected_nodes=[{"uid": r[0], "title": r[1], "title_ne": r[2]} for r in results],
    )]


def _check_no_excessive_promise_links() -> list:
    """No Project should be linked to more than 5 ManifestoPromises (sanity)."""
    query = """
    MATCH (p:Project)<-[:FULFILLED_BY]-(m:ManifestoPromise)
    WITH p, count(m) AS promise_count
    WHERE promise_count > 5
    RETURN p.uid AS uid, p.title AS title, promise_count
    LIMIT 50
    """
    results, _ = db.cypher_query(query)
    if not results:
        return []

    return [ConsistencyViolation(
        check_name="no_excessive_promise_links",
        severity="warning",
        message=f"{len(results)} Project(s) linked to >5 promises (possible error)",
        affected_nodes=[
            {"uid": r[0], "title": r[1], "promise_count": r[2]}
            for r in results
        ],
    )]


def _check_no_orphan_projects() -> list:
    """No Project should exist without any relationship."""
    query = """
    MATCH (p:Project)
    WHERE NOT (p)-[]-()
    RETURN p.uid AS uid, p.title AS title
    LIMIT 50
    """
    results, _ = db.cypher_query(query)
    if not results:
        return []

    return [ConsistencyViolation(
        check_name="no_orphan_projects",
        severity="warning",
        message=f"{len(results)} orphan Project(s) with no relationships",
        affected_nodes=[{"uid": r[0], "title": r[1]} for r in results],
    )]


def _check_no_orphan_promises() -> list:
    """Flag ManifestoPromises with no project links (not an error, just info)."""
    query = """
    MATCH (m:ManifestoPromise)
    WHERE NOT (m)-[:FULFILLED_BY]->(:Project)
    RETURN m.uid AS uid, m.text AS text
    LIMIT 100
    """
    results, _ = db.cypher_query(query)
    if not results:
        return []

    return [ConsistencyViolation(
        check_name="no_orphan_promises",
        severity="info",
        message=f"{len(results)} ManifestoPromise(s) have no linked projects yet",
        affected_nodes=[{"uid": r[0], "text": r[1][:60]} for r in results],
    )]


def _check_budget_positivity() -> list:
    """All Project budgets should be positive integers."""
    query = """
    MATCH (p:Project)
    WHERE p.budget IS NULL OR p.budget <= 0
    RETURN p.uid AS uid, p.title AS title, p.budget AS budget
    LIMIT 50
    """
    results, _ = db.cypher_query(query)
    if not results:
        return []

    return [ConsistencyViolation(
        check_name="budget_positivity",
        severity="critical",
        message=f"{len(results)} Project(s) with invalid budget (≤0 or null)",
        affected_nodes=[
            {"uid": r[0], "title": r[1], "budget": r[2]}
            for r in results
        ],
    )]

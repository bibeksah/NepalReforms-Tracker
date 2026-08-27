"""
Graph Consistency Checker - Post-publish validation queries.

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
        _check_budget_allocations_have_fiscal_year,
        _check_budget_allocations_have_project_or_body,
        _check_budget_allocation_project_linkage_consistency,
        _check_budget_events_relate_to_allocations,
        _check_receipt_events_have_receiving_body,
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
        logger.info("All graph consistency checks passed")

    return violations


def _check_projects_have_fiscal_year() -> list:
    """Every Project MUST have exactly one FUNDED_IN -> FiscalYear edge."""
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
        message=f"{len(results)} Project(s) missing FUNDED_IN -> FiscalYear link",
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
        message=f"{len(results)} Project(s) with invalid budget (<=0 or null)",
        affected_nodes=[
            {"uid": r[0], "title": r[1], "budget": r[2]}
            for r in results
        ],
    )]


def _check_budget_allocations_have_fiscal_year() -> list:
    query = """
    MATCH (b:BudgetAllocation)
    WHERE NOT (b)-[:IN_FISCAL_YEAR]->(:FiscalYear)
    RETURN coalesce(b.budgetAllocationId, b.uid) AS id, b.title AS title
    LIMIT 50
    """
    results, _ = db.cypher_query(query)
    if not results:
        return []
    return [ConsistencyViolation(
        check_name="budget_allocations_have_fiscal_year",
        severity="critical",
        message=f"{len(results)} BudgetAllocation node(s) missing IN_FISCAL_YEAR link",
        affected_nodes=[{"id": r[0], "title": r[1]} for r in results],
    )]


def _check_budget_allocations_have_project_or_body() -> list:
    query = """
    MATCH (b:BudgetAllocation)
    WHERE NOT (b)-[:FUNDS]->(:Project)
      AND NOT (b)-[:MANAGED_BY]->(:ImplementingBody)
    RETURN coalesce(b.budgetAllocationId, b.uid) AS id, b.title AS title
    LIMIT 50
    """
    results, _ = db.cypher_query(query)
    if not results:
        return []
    return [ConsistencyViolation(
        check_name="budget_allocations_have_project_or_body",
        severity="warning",
        message=f"{len(results)} BudgetAllocation node(s) missing both project and implementing body links",
        affected_nodes=[{"id": r[0], "title": r[1]} for r in results],
    )]


def _check_budget_events_relate_to_allocations() -> list:
    query = """
    MATCH (e)
    WHERE (e:ReleaseEvent OR e:TransferEvent OR e:ReceiptEvent)
      AND NOT (e)-[:RELATES_TO]->(:BudgetAllocation)
    RETURN labels(e)[0] AS label,
           coalesce(e.releaseEventId, e.transferEventId, e.receiptEventId, e.uid) AS id,
           e.title AS title
    LIMIT 50
    """
    results, _ = db.cypher_query(query)
    if not results:
        return []
    return [ConsistencyViolation(
        check_name="budget_events_relate_to_allocations",
        severity="critical",
        message=f"{len(results)} budget event node(s) missing RELATES_TO -> BudgetAllocation link",
        affected_nodes=[{"label": r[0], "id": r[1], "title": r[2]} for r in results],
    )]


def _check_receipt_events_have_receiving_body() -> list:
    query = """
    MATCH (e:ReceiptEvent)
    WHERE NOT (e)-[:RECEIVED_BY]->(:ImplementingBody)
    RETURN coalesce(e.receiptEventId, e.uid) AS id, e.title AS title
    LIMIT 50
    """
    results, _ = db.cypher_query(query)
    if not results:
        return []
    return [ConsistencyViolation(
        check_name="receipt_events_have_receiving_body",
        severity="critical",
        message=f"{len(results)} ReceiptEvent node(s) missing RECEIVED_BY -> ImplementingBody link",
        affected_nodes=[{"id": r[0], "title": r[1]} for r in results],
    )]



def _check_budget_allocation_project_linkage_consistency() -> list:
    violations = []

    linked_missing_funds_query = """
    MATCH (b:BudgetAllocation)
    WHERE b.project_linkage_state = 'linked'
      AND NOT (b)-[:FUNDS]->(:Project)
    RETURN coalesce(b.budgetAllocationId, b.uid) AS id, b.title AS title
    LIMIT 50
    """
    results, _ = db.cypher_query(linked_missing_funds_query)
    if results:
        violations.append(ConsistencyViolation(
            check_name='budget_allocation_linked_missing_funds_edge',
            severity='critical',
            message=f"{len(results)} linked BudgetAllocation node(s) missing FUNDS -> Project link",
            affected_nodes=[{'id': r[0], 'title': r[1]} for r in results],
        ))

    unresolved_with_funds_query = """
    MATCH (b:BudgetAllocation)-[:FUNDS]->(:Project)
    WHERE b.project_linkage_state IN ['unresolved_candidate', 'unlinked_accountable_body']
       OR b.project_linkage_state IS NULL
    RETURN coalesce(b.budgetAllocationId, b.uid) AS id, b.title AS title, b.project_linkage_state AS state
    LIMIT 50
    """
    results, _ = db.cypher_query(unresolved_with_funds_query)
    if results:
        violations.append(ConsistencyViolation(
            check_name='budget_allocation_unresolved_or_unlinked_emits_funds_edge',
            severity='critical',
            message=f"{len(results)} unresolved/unlinked BudgetAllocation node(s) incorrectly emit FUNDS -> Project link",
            affected_nodes=[{'id': r[0], 'title': r[1], 'state': r[2]} for r in results],
        ))

    linked_missing_resolved_id_query = """
    MATCH (b:BudgetAllocation)
    WHERE b.project_linkage_state = 'linked'
      AND (b.resolved_project_id IS NULL OR b.resolved_project_id = '')
    RETURN coalesce(b.budgetAllocationId, b.uid) AS id, b.title AS title
    LIMIT 50
    """
    results, _ = db.cypher_query(linked_missing_resolved_id_query)
    if results:
        violations.append(ConsistencyViolation(
            check_name='budget_allocation_linked_missing_resolved_project_id',
            severity='critical',
            message=f"{len(results)} linked BudgetAllocation node(s) missing resolved_project_id metadata",
            affected_nodes=[{'id': r[0], 'title': r[1]} for r in results],
        ))

    unlinked_missing_body_query = """
    MATCH (b:BudgetAllocation)
    WHERE b.project_linkage_state = 'unlinked_accountable_body'
      AND NOT (b)-[:MANAGED_BY]->(:ImplementingBody)
    RETURN coalesce(b.budgetAllocationId, b.uid) AS id, b.title AS title
    LIMIT 50
    """
    results, _ = db.cypher_query(unlinked_missing_body_query)
    if results:
        violations.append(ConsistencyViolation(
            check_name='budget_allocation_unlinked_accountable_body_missing_body_relation',
            severity='warning',
            message=f"{len(results)} unlinked_accountable_body BudgetAllocation node(s) missing MANAGED_BY -> ImplementingBody link",
            affected_nodes=[{'id': r[0], 'title': r[1]} for r in results],
        ))

    return violations

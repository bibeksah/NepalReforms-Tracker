import tracker.agents.consistency as consistency


def test_run_all_checks_includes_budget_flow_checks(monkeypatch):
    monkeypatch.setattr(consistency, "_check_projects_have_fiscal_year", lambda: [])
    monkeypatch.setattr(consistency, "_check_projects_have_titles", lambda: [])
    monkeypatch.setattr(consistency, "_check_no_excessive_promise_links", lambda: [])
    monkeypatch.setattr(consistency, "_check_no_orphan_projects", lambda: [])
    monkeypatch.setattr(consistency, "_check_no_orphan_promises", lambda: [])
    monkeypatch.setattr(consistency, "_check_budget_positivity", lambda: [])
    monkeypatch.setattr(consistency, "_check_budget_allocations_have_fiscal_year", lambda: [])
    monkeypatch.setattr(consistency, "_check_budget_allocations_have_project_or_body", lambda: [])
    monkeypatch.setattr(consistency, "_check_budget_events_relate_to_allocations", lambda: [])
    monkeypatch.setattr(consistency, "_check_receipt_events_have_receiving_body", lambda: [])

    assert consistency.run_all_checks() == []


def test_run_all_checks_returns_budget_flow_violation(monkeypatch):
    violation = consistency.ConsistencyViolation(
        check_name="budget_events_relate_to_allocations",
        severity="critical",
        message="1 budget event node missing relation",
    )
    monkeypatch.setattr(consistency, "_check_projects_have_fiscal_year", lambda: [])
    monkeypatch.setattr(consistency, "_check_projects_have_titles", lambda: [])
    monkeypatch.setattr(consistency, "_check_no_excessive_promise_links", lambda: [])
    monkeypatch.setattr(consistency, "_check_no_orphan_projects", lambda: [])
    monkeypatch.setattr(consistency, "_check_no_orphan_promises", lambda: [])
    monkeypatch.setattr(consistency, "_check_budget_positivity", lambda: [])
    monkeypatch.setattr(consistency, "_check_budget_allocations_have_fiscal_year", lambda: [])
    monkeypatch.setattr(consistency, "_check_budget_allocations_have_project_or_body", lambda: [])
    monkeypatch.setattr(consistency, "_check_budget_events_relate_to_allocations", lambda: [violation])
    monkeypatch.setattr(consistency, "_check_receipt_events_have_receiving_body", lambda: [])

    violations = consistency.run_all_checks()
    assert violations == [violation]


def test_check_receipt_events_have_receiving_body_reports_missing_relation(monkeypatch):
    monkeypatch.setattr(
        consistency.db,
        "cypher_query",
        lambda _query: ([["receipt_event:1", "Treasury receipt"]], None),
    )

    violations = consistency._check_receipt_events_have_receiving_body()

    assert len(violations) == 1
    violation = violations[0]
    assert violation.check_name == "receipt_events_have_receiving_body"
    assert violation.severity == "critical"
    assert violation.affected_nodes[0]["id"] == "receipt_event:1"



def test_run_all_checks_includes_budget_project_linkage_check(monkeypatch):
    monkeypatch.setattr(consistency, '_check_projects_have_fiscal_year', lambda: [])
    monkeypatch.setattr(consistency, '_check_projects_have_titles', lambda: [])
    monkeypatch.setattr(consistency, '_check_no_excessive_promise_links', lambda: [])
    monkeypatch.setattr(consistency, '_check_no_orphan_projects', lambda: [])
    monkeypatch.setattr(consistency, '_check_no_orphan_promises', lambda: [])
    monkeypatch.setattr(consistency, '_check_budget_positivity', lambda: [])
    monkeypatch.setattr(consistency, '_check_budget_allocations_have_fiscal_year', lambda: [])
    monkeypatch.setattr(consistency, '_check_budget_allocations_have_project_or_body', lambda: [])
    monkeypatch.setattr(consistency, '_check_budget_allocation_project_linkage_consistency', lambda: [])
    monkeypatch.setattr(consistency, '_check_budget_events_relate_to_allocations', lambda: [])
    monkeypatch.setattr(consistency, '_check_receipt_events_have_receiving_body', lambda: [])
    assert consistency.run_all_checks() == []


def test_budget_allocation_project_linkage_consistency_reports_linked_missing_funds(monkeypatch):
    queries = []
    responses = [
        ([["alloc:1", "Road allocation"]], None),
        ([], None),
        ([], None),
        ([], None),
    ]
    def fake_cypher_query(query):
        queries.append(query)
        return responses[len(queries)-1]
    monkeypatch.setattr(consistency.db, 'cypher_query', fake_cypher_query)
    violations = consistency._check_budget_allocation_project_linkage_consistency()
    assert len(violations) == 1
    assert violations[0].check_name == 'budget_allocation_linked_missing_funds_edge'
    assert violations[0].severity == 'critical'
    assert violations[0].affected_nodes[0]['id'] == 'alloc:1'


def test_budget_allocation_project_linkage_consistency_reports_unresolved_with_funds(monkeypatch):
    responses = [
        ([], None),
        ([["alloc:2", "Ghost allocation", "unresolved_candidate"]], None),
        ([], None),
        ([], None),
    ]
    call = {'n': 0}
    def fake_cypher_query(_query):
        idx = call['n']
        call['n'] += 1
        return responses[idx]
    monkeypatch.setattr(consistency.db, 'cypher_query', fake_cypher_query)
    violations = consistency._check_budget_allocation_project_linkage_consistency()
    assert len(violations) == 1
    assert violations[0].check_name == 'budget_allocation_unresolved_or_unlinked_emits_funds_edge'
    assert violations[0].affected_nodes[0]['state'] == 'unresolved_candidate'


def test_budget_allocation_project_linkage_consistency_reports_linked_missing_resolved_project_id(monkeypatch):
    responses = [
        ([], None),
        ([], None),
        ([["alloc:3", "Linked allocation"]], None),
        ([], None),
    ]
    call = {'n': 0}
    def fake_cypher_query(_query):
        idx = call['n']
        call['n'] += 1
        return responses[idx]
    monkeypatch.setattr(consistency.db, 'cypher_query', fake_cypher_query)
    violations = consistency._check_budget_allocation_project_linkage_consistency()
    assert len(violations) == 1
    assert violations[0].check_name == 'budget_allocation_linked_missing_resolved_project_id'
    assert violations[0].severity == 'critical'


def test_budget_allocation_project_linkage_consistency_allows_unlinked_accountable_body_without_project_edge(monkeypatch):
    responses = [
        ([], None),
        ([], None),
        ([], None),
        ([], None),
    ]
    call = {'n': 0}
    def fake_cypher_query(_query):
        idx = call['n']
        call['n'] += 1
        return responses[idx]
    monkeypatch.setattr(consistency.db, 'cypher_query', fake_cypher_query)
    violations = consistency._check_budget_allocation_project_linkage_consistency()
    assert violations == []


def test_budget_allocation_project_linkage_consistency_warns_when_unlinked_accountable_body_missing_body_relation(monkeypatch):
    responses = [
        ([], None),
        ([], None),
        ([], None),
        ([["alloc:4", "Body allocation"]], None),
    ]
    call = {'n': 0}
    def fake_cypher_query(_query):
        idx = call['n']
        call['n'] += 1
        return responses[idx]
    monkeypatch.setattr(consistency.db, 'cypher_query', fake_cypher_query)
    violations = consistency._check_budget_allocation_project_linkage_consistency()
    assert len(violations) == 1
    assert violations[0].check_name == 'budget_allocation_unlinked_accountable_body_missing_body_relation'
    assert violations[0].severity == 'warning'

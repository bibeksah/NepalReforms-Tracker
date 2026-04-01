import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import tracker.agents.smart_neo4j_publisher as publisher


def test_publish_project_records_batch_success(monkeypatch):
    def fake_cypher_query(_query, params):
        fingerprints = [row["fingerprint"] for row in params["rows"]]
        return [[[fingerprints]]][0], None

    monkeypatch.setattr(publisher.db, "cypher_query", fake_cypher_query)
    records = [
        {"title_ne": "Nepali road", "title_en": "Road", "budget": 1000, "fiscal_year": "2081/82", "gov_level": "federal", "province_name": "", "source_hash": "a1", "page_num": 1},
        {"title_ne": "Nepali school", "title_en": "School", "budget": 2000, "fiscal_year": "2081/82", "gov_level": "federal", "province_name": "", "source_hash": "a2", "page_num": 2},
    ]
    result = publisher.publish_project_records_batch(records, batch_size=2)
    assert result["ok_count"] == 2
    assert not result["failed_fingerprints"]


def test_publish_project_records_batch_chunk_error(monkeypatch):
    def fake_cypher_query(_query, _params):
        raise RuntimeError("neo4j unavailable")

    monkeypatch.setattr(publisher.db, "cypher_query", fake_cypher_query)
    records = [{"title_ne": "Nepali road", "title_en": "Road", "budget": 1000, "fiscal_year": "2081/82", "gov_level": "federal", "province_name": "", "source_hash": "a1", "page_num": 1}]
    result = publisher.publish_project_records_batch(records, batch_size=1)
    assert result["ok_count"] == 0
    assert len(result["failed_fingerprints"]) == 1
    assert result["errors"]


def test_publish_records_batch_mixes_projects_and_non_projects(monkeypatch):
    def fake_project_batch(records, batch_size=200):
        return {"ok_count": 1, "published_fingerprints": [publisher.compute_project_fingerprint(records[0])], "failed_fingerprints": [], "errors": []}

    calls = []
    monkeypatch.setattr(publisher, "publish_project_records_batch", fake_project_batch)
    monkeypatch.setattr(publisher, "publish_record", lambda record: calls.append(record["entity_type"]) or {"ok": True, "node_id": (record.get("graph_payload") or {}).get("id")})

    records = [
        {"entity_type": "Project", "title_ne": "Nepali road", "title_en": "Road", "budget": 1000, "fiscal_year": "2081/82", "gov_level": "federal", "province_name": "", "source_hash": "a1", "page_num": 1},
        {"entity_type": "PoliticalPromise", "graph_payload": {"id": "promise:1"}, "graph_relations": []},
    ]
    result = publisher.publish_records_batch(records, batch_size=50)
    assert result["ok_count"] == 2
    assert "PoliticalPromise" in calls


def test_publish_record_rejects_missing_graph_payload_key():
    try:
        publisher.publish_record({
            "entity_type": "PoliticalPromise",
            "graph_payload": {"id": "promise:1", "properties": {}},
            "graph_relations": [],
        })
    except ValueError as exc:
        assert "graph_payload.key" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing graph_payload.key")


def test_publish_record_rejects_invalid_relation_payload(monkeypatch):
    calls = []

    def fake_cypher_query(query, params):
        calls.append((query, params))
        return [[params.get("node_value") or params.get("target_value")]], None

    monkeypatch.setattr(publisher.db, "cypher_query", fake_cypher_query)

    try:
        publisher.publish_record({
            "entity_type": "PoliticalPromise",
            "graph_payload": {
                "id": "promise:1",
                "key": "politicalPromiseId",
                "properties": {"title": "Promise 1"},
            },
            "graph_relations": [{
                "target_entity_type": "ManifestoDocument",
                "target_key": "manifestoDocumentId",
                "relation_type": "PROMISED_IN",
                "target_properties": {},
            }],
        })
    except ValueError as exc:
        assert "graph_relations[].target_id" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing graph_relations[].target_id")

    assert len(calls) == 1



def test_publish_record_requires_existing_target(monkeypatch):
    calls = []

    def fake_cypher_query(query, params):
        calls.append(query)
        return [[params.get("node_value") or params.get("target_value")]], None

    monkeypatch.setattr(publisher.db, "cypher_query", fake_cypher_query)

    result = publisher.publish_record({
        "entity_type": "AlignmentAssessment",
        "graph_payload": {
            "id": "alignment:1",
            "key": "alignmentAssessmentId",
            "properties": {"alignment_assessment_id": "alignment:1", "relation_type": "PARTIALLY_ALIGNS"},
        },
        "graph_relations": [{
            "target_entity_type": "AgendaItem",
            "target_key": "agendaItemId",
            "target_id": "agenda:1",
            "relation_type": "ASSESSES_AGENDA_ITEM",
            "target_properties": {"agendaItemId": "agenda:1"},
            "relationship_properties": {"confidence": 0.91},
            "require_existing_target": True,
        }],
    })

    assert result["ok"] is True
    assert len(calls) == 2
    assert "MATCH (t:`AgendaItem` {agendaItemId: $target_value})" in calls[1]
    assert "MERGE (t:`AgendaItem`" not in calls[1]



def test_publish_record_fails_when_required_existing_target_missing(monkeypatch):
    def fake_cypher_query(query, params):
        if "RETURN $node_value as node_id" in query:
            return [[params.get("node_value")]], None
        return [], None

    monkeypatch.setattr(publisher.db, "cypher_query", fake_cypher_query)

    try:
        publisher.publish_record({
            "entity_type": "AlignmentAssessment",
            "graph_payload": {
                "id": "alignment:1",
                "key": "alignmentAssessmentId",
                "properties": {"alignment_assessment_id": "alignment:1", "relation_type": "PARTIALLY_ALIGNS"},
            },
            "graph_relations": [{
                "target_entity_type": "PoliticalPromise",
                "target_key": "politicalPromiseId",
                "target_id": "promise:missing",
                "relation_type": "ASSESSES_POLITICAL_PROMISE",
                "target_properties": {"politicalPromiseId": "promise:missing"},
                "relationship_properties": {"confidence": 0.91},
                "require_existing_target": True,
            }],
        })
    except ValueError as exc:
        assert "target_id not found" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing required existing target")



def test_publish_record_supports_explicit_source_node_and_target_lookup(monkeypatch):
    calls = []

    def fake_cypher_query(query, params):
        calls.append((query, params))
        if "RETURN s.solutionPlanId AS target_id" in query:
            return [["solution:123"]], None
        return [[params.get("node_value") or params.get("target_value")]], None

    monkeypatch.setattr(publisher.db, "cypher_query", fake_cypher_query)

    result = publisher.publish_record({
        "entity_type": "AlignmentAssessment",
        "graph_payload": {
            "id": "alignment:1",
            "key": "alignmentAssessmentId",
            "properties": {"alignmentAssessmentId": "alignment:1"},
        },
        "graph_relations": [{
            "source_entity_type": "PoliticalPromise",
            "source_key": "politicalPromiseId",
            "source_id": "promise:1",
            "target_entity_type": "SolutionPlan",
            "target_key": "solutionPlanId",
            "relation_type": "ALIGNS_WITH_SOLUTION_PLAN",
            "target_lookup": {
                "cypher": "MATCH (a:AgendaItem {agendaItemId: $agenda_item_id})-[:HAS_SOLUTION_PLAN]->(s:SolutionPlan) RETURN s.solutionPlanId AS target_id LIMIT 1",
                "params": {"agenda_item_id": "agenda:1"},
            },
            "target_properties": {},
            "relationship_properties": {"alignmentAssessmentId": "alignment:1"},
            "require_existing_target": True,
        }],
    })

    assert result["ok"] is True
    assert any("RETURN s.solutionPlanId AS target_id" in query for query, _ in calls)
    merge_call = [query for query, _ in calls if "ALIGNS_WITH_SOLUTION_PLAN" in query][-1]
    assert "MATCH (s:`PoliticalPromise` {politicalPromiseId: $source_value})" in merge_call


def test_ensure_smart_constraints_includes_political_party(monkeypatch):
    statements = []

    def fake_cypher_query(query, _params=None):
        statements.append(query.strip())
        return [], None

    monkeypatch.setattr(publisher.db, "cypher_query", fake_cypher_query)

    publisher.ensure_smart_constraints()

    assert any("PoliticalParty" in stmt and "politicalPartyId" in stmt for stmt in statements)


def test_publish_record_political_party_with_manifesto_relation(monkeypatch):
    calls = []

    def fake_cypher_query(query, params):
        calls.append((query, params))
        return [[params.get("node_value") or params.get("target_value")]], None

    monkeypatch.setattr(publisher.db, "cypher_query", fake_cypher_query)

    result = publisher.publish_record({
        "entity_type": "ManifestoDocument",
        "graph_payload": {
            "id": "manifesto_document:1",
            "key": "manifestoDocumentId",
            "properties": {"manifesto_document_id": "manifesto_document:1", "name": "rsp_manifesto.csv"},
        },
        "graph_relations": [{
            "target_entity_type": "PoliticalParty",
            "target_key": "politicalPartyId",
            "target_id": "political_party:rsp",
            "relation_type": "ISSUED_BY",
            "target_properties": {
                "politicalPartyId": "political_party:rsp",
                "political_party_id": "political_party:rsp",
                "canonical_name": "Rastriya Swatantra Party",
                "short_name": "RSP",
            },
        }],
    })

    assert result["ok"] is True
    assert len(calls) == 2
    assert "MERGE (t:`PoliticalParty` {politicalPartyId: $target_value})" in calls[1][0]

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

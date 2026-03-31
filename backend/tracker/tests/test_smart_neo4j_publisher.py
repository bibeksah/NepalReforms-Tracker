import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import tracker.agents.smart_neo4j_publisher as publisher


def test_publish_project_records_batch_success(monkeypatch):
    def fake_cypher_query(_query, params):
        fingerprints = [row["fingerprint"] for row in params["rows"]]
        return [ [fingerprints] ], None

    monkeypatch.setattr(publisher.db, "cypher_query", fake_cypher_query)
    records = [
        {
            "title_ne": "सडक",
            "title_en": "Road",
            "budget": 1000,
            "fiscal_year": "2081/82",
            "gov_level": "federal",
            "province_name": "",
            "source_hash": "a1",
            "page_num": 1,
        },
        {
            "title_ne": "विद्यालय",
            "title_en": "School",
            "budget": 2000,
            "fiscal_year": "2081/82",
            "gov_level": "federal",
            "province_name": "",
            "source_hash": "a2",
            "page_num": 2,
        },
    ]
    result = publisher.publish_project_records_batch(records, batch_size=2)
    assert result["ok_count"] == 2
    assert not result["failed_fingerprints"]


def test_publish_project_records_batch_chunk_error(monkeypatch):
    def fake_cypher_query(_query, _params):
        raise RuntimeError("neo4j unavailable")

    monkeypatch.setattr(publisher.db, "cypher_query", fake_cypher_query)
    records = [
        {
            "title_ne": "सडक",
            "title_en": "Road",
            "budget": 1000,
            "fiscal_year": "2081/82",
            "gov_level": "federal",
            "province_name": "",
            "source_hash": "a1",
            "page_num": 1,
        }
    ]
    result = publisher.publish_project_records_batch(records, batch_size=1)
    assert result["ok_count"] == 0
    assert len(result["failed_fingerprints"]) == 1
    assert result["errors"]

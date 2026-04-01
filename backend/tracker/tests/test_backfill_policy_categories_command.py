import io
import json
import os

import django
from django.core.management import call_command

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from tracker.agents.schemas import stable_id


def test_backfill_policy_categories_dry_run(monkeypatch):
    from tracker.management.commands import backfill_policy_categories as command_module

    calls = []

    def fake_cypher_query(query, params=None):
        calls.append((query, params))
        if "RETURN {" in query:
            return [
                [
                    {
                        "entity_type": "AgendaItem",
                        "node_id": "agenda_item:1",
                        "category": "good governance",
                        "name": "",
                        "title": "Publish all tenders online",
                        "summary": "",
                        "description": "Procurement transparency with citizen oversight.",
                        "text": "",
                    }
                ],
                [
                    {
                        "entity_type": "PoliticalPromise",
                        "node_id": "political_promise:1",
                        "category": "",
                        "name": "",
                        "title": "Expand public hospitals and clinics",
                        "summary": "",
                        "description": "",
                        "text": "",
                    }
                ],
            ], None
        raise AssertionError("Dry-run should not execute mutation query")

    monkeypatch.setattr(command_module.db, "cypher_query", fake_cypher_query)

    out = io.StringIO()
    call_command("backfill_policy_categories", "--dry-run", stdout=out)
    payload = json.loads(out.getvalue())

    assert len(calls) == 1
    assert payload["status"] == "dry_run"
    assert payload["nodes_scanned"] == 2
    assert payload["nodes_processed"] == 2
    assert payload["category_updates"] == 2
    assert payload["category_links_merged"] == 0
    assert payload["categories"] == {"governance": 1, "health": 1}


def test_backfill_policy_categories_merges_shared_policy_category(monkeypatch):
    from tracker.management.commands import backfill_policy_categories as command_module

    write_calls = []

    def fake_cypher_query(query, params=None):
        if "RETURN {" in query:
            return [
                [
                    {
                        "entity_type": "PoliticalPromise",
                        "node_id": "political_promise:42",
                        "category": "Governance",
                        "name": "",
                        "title": "Mandatory public procurement disclosure",
                        "summary": "",
                        "description": "",
                        "text": "",
                    }
                ]
            ], None
        write_calls.append((query, params))
        return [[params["node_id"]]], None

    monkeypatch.setattr(command_module.db, "cypher_query", fake_cypher_query)

    out = io.StringIO()
    call_command("backfill_policy_categories", stdout=out)
    payload = json.loads(out.getvalue())

    assert payload["status"] == "completed"
    assert payload["nodes_processed"] == 1
    assert payload["category_links_merged"] == 1
    assert len(write_calls) == 1
    _query, params = write_calls[0]
    assert params["node_id"] == "political_promise:42"
    assert params["category_slug"] == "governance"
    assert params["category_name"] == "Governance"
    assert params["policy_category_id"] == stable_id("policy_category", "Governance")

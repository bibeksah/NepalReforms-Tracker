import io
import json
import os

import django
import pytest
from django.core.management import call_command

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()


@pytest.mark.django_db
def test_backfill_alignment_graph_links_dry_run(monkeypatch):
    from tracker.management.commands import backfill_alignment_graph_links as command_module

    def fake_cypher_query(query, params=None):
        if "MATCH (aa:AlignmentAssessment)" in query:
            return [[{
                "alignment_assessment_id": "alignment:1",
                "agenda_item_id": "agenda:1",
                "political_promise_id": "promise:1",
                "relation_type": "PARTIALLY_ALIGNS",
                "confidence": 0.62,
                "approval_state": "approved",
            }]], None
        if "count(t) AS count" in query:
            return [[0]], None
        raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(command_module.db, "cypher_query", fake_cypher_query)

    out = io.StringIO()
    call_command("backfill_alignment_graph_links", "--dry-run", stdout=out)
    payload = json.loads(out.getvalue())

    assert payload["status"] == "dry_run"
    assert payload["approved_alignments_scanned"] == 1
    assert payload["direct_relations_created"] >= 1


@pytest.mark.django_db
def test_backfill_alignment_graph_links_runs_publish_record(monkeypatch):
    from tracker.management.commands import backfill_alignment_graph_links as command_module

    published = []

    def fake_cypher_query(query, params=None):
        if "MATCH (aa:AlignmentAssessment)" in query:
            return [[{
                "alignment_assessment_id": "alignment:1",
                "agenda_item_id": "agenda:1",
                "political_promise_id": "promise:1",
                "relation_type": "PARTIALLY_ALIGNS",
                "confidence": 0.62,
                "approval_state": "approved",
            }]], None
        if "count(t) AS count" in query:
            return [[0]], None
        raise AssertionError(f"Unexpected query: {query}")

    def fake_publish_record(payload):
        published.append(payload)
        return {"ok": True, "node_id": payload["record_identity"]}

    monkeypatch.setattr(command_module.db, "cypher_query", fake_cypher_query)
    monkeypatch.setattr(command_module, "publish_record", fake_publish_record)

    out = io.StringIO()
    call_command("backfill_alignment_graph_links", stdout=out)
    payload = json.loads(out.getvalue())

    assert payload["status"] == "completed"
    assert payload["direct_relations_created"] >= 1
    assert published
    assert published[0]["graph_relations"][0]["source_entity_type"] == "PoliticalPromise"

import io
import json
import os

import django
import pytest
from django.core.management import call_command

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from tracker.models import ReviewQueueItem


@pytest.mark.django_db
def test_generate_alignment_review_candidates_dry_run(monkeypatch):
    from tracker.management.commands import generate_alignment_review_candidates as command_module

    calls = []

    def fake_cypher_query(query, params=None):
        calls.append((query, params))
        if "MATCH (a:AgendaItem)" in query:
            return [[{
                "agenda_item_id": "agenda:1",
                "title": "Publish all procurement contracts online",
                "description": "Tender awards and procurement contracts should be public.",
                "summary": "",
                "category": "Governance",
                "timeline": "100 Days",
                "responsible_entity": "Prime Minister Office",
                "problem": None,
                "solution": {"summary": "Publish tenders and awards in one place."},
                "implementation": {"steps": ["open tender portal"]},
                "performance_targets": ["All awards published"],
                "legal_foundation": "Public transparency act",
                "real_world_evidence": {"example": "Open contracting"},
            }]], None
        if "MATCH (p:PoliticalPromise)" in query:
            return [[{
                "political_promise_id": "promise:1",
                "title": "Publish procurement contracts and tender awards online",
                "summary": "Public procurement disclosure within 100 days.",
                "description": "",
                "category": "Governance",
                "timeline": "100 Days",
                "responsible_entity": "Prime Minister's Office",
            }]], None
        raise AssertionError("Unexpected query")

    monkeypatch.setattr(command_module.db, "cypher_query", fake_cypher_query)

    out = io.StringIO()
    call_command("generate_alignment_review_candidates", "--dry-run", stdout=out)
    payload = json.loads(out.getvalue())

    assert len(calls) == 2
    assert payload["status"] == "dry_run"
    assert payload["agenda_items_scanned"] == 1
    assert payload["political_promises_scanned"] == 1
    assert payload["candidate_pairs_scored"] == 1
    assert payload["candidates_selected"] == 1
    assert payload["created_review_items"] == 0
    assert payload["preview"][0]["agenda_item_id"] == "agenda:1"
    assert ReviewQueueItem.objects.count() == 0


@pytest.mark.django_db
def test_generate_alignment_review_candidates_creates_review_queue_items(monkeypatch):
    from tracker.management.commands import generate_alignment_review_candidates as command_module

    def fake_cypher_query(query, params=None):
        if "MATCH (a:AgendaItem)" in query:
            return [[{
                "agenda_item_id": "agenda:1",
                "title": "Publish all procurement contracts online",
                "description": "Tender awards and procurement contracts should be public.",
                "summary": "",
                "category": "Governance",
                "timeline": "100 Days",
                "responsible_entity": "Prime Minister Office",
                "problem": None,
                "solution": {"summary": "Publish tenders and awards in one place."},
                "implementation": {"steps": ["open tender portal"]},
                "performance_targets": ["All awards published"],
                "legal_foundation": "Public transparency act",
                "real_world_evidence": {"example": "Open contracting"},
            }]], None
        if "MATCH (p:PoliticalPromise)" in query:
            return [[{
                "political_promise_id": "promise:1",
                "title": "Publish procurement contracts and tender awards online",
                "summary": "Public procurement disclosure within 100 days.",
                "description": "",
                "category": "Governance",
                "timeline": "100 Days",
                "responsible_entity": "Prime Minister's Office",
            }]], None
        raise AssertionError("Unexpected query")

    monkeypatch.setattr(command_module.db, "cypher_query", fake_cypher_query)

    out = io.StringIO()
    call_command("generate_alignment_review_candidates", stdout=out)
    payload = json.loads(out.getvalue())

    assert payload["status"] == "completed"
    assert payload["created_review_items"] == 1
    item = ReviewQueueItem.objects.get()
    assert item.status == "pending_review"
    assert item.reason == "alignment_candidate_generated"
    assert item.entity_type == "AlignmentAssessment"
    assert item.proposed_payload["source_subtype"] == "agenda_promise_alignment_review"
    assert item.proposed_payload["graph_relations"][0]["require_existing_target"] is True
    assert item.provenance["candidate_generation_method"] == "deterministic_rules_v3"


@pytest.mark.django_db
def test_generate_alignment_review_candidates_skips_existing_open_item(monkeypatch):
    from tracker.management.commands import generate_alignment_review_candidates as command_module

    ReviewQueueItem.objects.create(
        status="pending_review",
        reason="alignment_candidate_generated",
        entity_type="AlignmentAssessment",
        fingerprint="alignment_review_candidate:6b0b7f646de4d775",
        proposed_payload={},
        provenance={},
    )

    def fake_stable_id(prefix, *parts):
        if prefix == "alignment_review_candidate":
            return "alignment_review_candidate:6b0b7f646de4d775"
        return f"{prefix}:x"

    def fake_cypher_query(query, params=None):
        if "MATCH (a:AgendaItem)" in query:
            return [[{
                "agenda_item_id": "agenda:1",
                "title": "Publish all procurement contracts online",
                "description": "Tender awards and procurement contracts should be public.",
                "summary": "",
                "category": "Governance",
                "timeline": "100 Days",
                "responsible_entity": "Prime Minister Office",
                "problem": None,
                "solution": {"summary": "Publish tenders and awards in one place."},
                "implementation": {"steps": ["open tender portal"]},
                "performance_targets": ["All awards published"],
                "legal_foundation": "Public transparency act",
                "real_world_evidence": {"example": "Open contracting"},
            }]], None
        if "MATCH (p:PoliticalPromise)" in query:
            return [[{
                "political_promise_id": "promise:1",
                "title": "Publish procurement contracts and tender awards online",
                "summary": "Public procurement disclosure within 100 days.",
                "description": "",
                "category": "Governance",
                "timeline": "100 Days",
                "responsible_entity": "Prime Minister's Office",
            }]], None
        raise AssertionError("Unexpected query")

    monkeypatch.setattr(command_module.db, "cypher_query", fake_cypher_query)
    monkeypatch.setattr(command_module, "stable_id", fake_stable_id)

    out = io.StringIO()
    call_command("generate_alignment_review_candidates", stdout=out)
    payload = json.loads(out.getvalue())

    assert payload["created_review_items"] == 0
    assert payload["skipped_existing"] == 1
    assert ReviewQueueItem.objects.count() == 1

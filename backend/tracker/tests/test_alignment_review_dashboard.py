import os

import django
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from tracker.agents.alignment_candidates import score_alignment_candidate
from tracker.models import ReviewQueueItem


def _make_candidate_item():
    candidate = score_alignment_candidate(
        {
            "agenda_item_id": "agenda:1",
            "title": "Publish all procurement contracts online",
            "description": "Open tender awards and contract records for public oversight.",
            "summary": "Transparency in procurement decisions.",
            "category": "Governance",
            "timeline": "100 Days",
            "responsible_entity": "Prime Minister Office",
        },
        {
            "political_promise_id": "promise:1",
            "title": "Publish procurement contracts and tender awards online",
            "summary": "Public procurement disclosure within 100 days.",
            "description": "Tender transparency and public contract visibility.",
            "category": "Governance",
            "timeline": "100 Days",
            "responsible_entity": "Prime Minister's Office",
        },
    )
    assert candidate is not None
    payload = candidate.to_review_queue_payload()
    return ReviewQueueItem.objects.create(
        status="pending_review",
        reason="alignment_candidate_generated",
        risk_level="medium",
        confidence=candidate.confidence,
        entity_type="AlignmentAssessment",
        record_key=payload["record_identity"],
        fingerprint="fp:1",
        proposed_payload=payload,
        provenance={
            "source_subtype": "agenda_promise_alignment_review",
            "candidate_generation_method": "deterministic_rules_v3",
            "score_breakdown": candidate.score_breakdown,
            "shared_tokens": candidate.shared_tokens,
            "review_context": payload["review_context"],
        },
    )


@pytest.mark.django_db
def test_alignment_review_dashboard_requires_staff():
    client = Client()
    response = client.get("/reviews/alignment/")
    assert response.status_code in {302, 301}


@pytest.mark.django_db
def test_alignment_review_dashboard_renders_candidate_details():
    User = get_user_model()
    user = User.objects.create_user(username="reviewer", password="secret", is_staff=True)
    item = _make_candidate_item()

    client = Client()
    assert client.login(username="reviewer", password="secret")

    response = client.get("/reviews/alignment/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Alignment Review Dashboard" in body
    assert item.record_key in body
    assert "Publish all procurement contracts online" in body
    assert "Publish procurement contracts and tender awards online" in body
    assert "deterministic_rules_v3" in body


@pytest.mark.django_db
def test_alignment_review_decision_updates_status_and_reviewer_notes():
    User = get_user_model()
    User.objects.create_user(username="reviewer", password="secret", is_staff=True)
    item = _make_candidate_item()

    client = Client()
    assert client.login(username="reviewer", password="secret")

    response = client.post(
        f"/reviews/alignment/{item.id}/decision/",
        {"decision": "approve", "reviewer_notes": "Looks like the same policy commitment."},
        follow=True,
    )
    item.refresh_from_db()

    assert response.status_code == 200
    assert item.status == "approved"
    assert item.reviewer == "reviewer"
    assert item.reviewer_notes == "Looks like the same policy commitment."
    assert item.reviewed_at is not None

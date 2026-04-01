import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from tracker.agents.alignment_candidates import build_alignment_candidates, score_alignment_candidate


def test_score_alignment_candidate_requires_strong_safe_signals():
    candidate = score_alignment_candidate(
        {
            "agenda_item_id": "agenda:1",
            "title": "Publish all public procurement contracts online",
            "description": "Open tender data and contract awards for citizen oversight.",
            "category": "Governance",
            "timeline": "100 Days",
            "responsible_entity": "Prime Minister Office",
        },
        {
            "political_promise_id": "promise:1",
            "title": "Publish procurement contracts and tender decisions online",
            "summary": "Citizen access to tender awards and procurement records.",
            "category": "Governance",
            "timeline": "100 Days",
            "responsible_entity": "Prime Minister's Office",
        },
    )

    assert candidate is not None
    assert candidate.confidence >= 0.78
    assert candidate.category_match is True
    assert candidate.timeline_match is True
    assert candidate.responsible_entity_match is True
    assert "procurement" in candidate.shared_tokens
    payload = candidate.to_review_queue_payload()
    assert payload["entity_type"] == "AlignmentAssessment"
    assert payload["source_subtype"] == "agenda_promise_alignment_review"
    assert payload["graph_relations"][0]["require_existing_target"] is True
    assert payload["graph_relations"][1]["require_existing_target"] is True


def test_score_alignment_candidate_rejects_category_only_match():
    candidate = score_alignment_candidate(
        {
            "agenda_item_id": "agenda:2",
            "title": "Reform procurement audit process",
            "description": "Audit tender compliance.",
            "category": "Governance",
        },
        {
            "political_promise_id": "promise:2",
            "title": "Expand telemedicine access in rural clinics",
            "summary": "Rural hospitals and mobile medical units.",
            "category": "Governance",
        },
    )

    assert candidate is None


def test_build_alignment_candidates_orders_by_confidence():
    candidates = build_alignment_candidates(
        [
            {
                "agenda_item_id": "agenda:1",
                "title": "Publish procurement contracts online",
                "description": "Tender award transparency and open contracting.",
                "category": "Governance",
                "timeline": "100 Days",
            },
            {
                "agenda_item_id": "agenda:2",
                "title": "Build hospitals and community clinics in underserved districts",
                "description": "Expand public hospital access and clinic capacity.",
                "category": "Health",
                "timeline": "3 Years",
            },
        ],
        [
            {
                "political_promise_id": "promise:1",
                "title": "Publish all tender and contract decisions online",
                "summary": "Open contracting and procurement transparency.",
                "category": "Governance",
                "timeline": "100 Days",
            },
            {
                "political_promise_id": "promise:2",
                "title": "Build more hospitals and community clinics",
                "summary": "Expand hospital and clinic access in rural municipalities.",
                "category": "Health",
                "timeline": "3 Years",
            },
        ],
    )

    assert len(candidates) >= 2
    assert candidates[0].confidence >= candidates[1].confidence

import io
import json
import os

import django
import pytest
from django.core.management import call_command

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from tracker.models import IngestionDocument, IngestionJob, ReviewQueueItem


@pytest.mark.django_db
def test_publish_review_command_publishes_non_project(monkeypatch):
    from tracker.management.commands import ingestion_publish_review as command_module

    job = IngestionJob.objects.create(name="review-job", status="review_hold")
    doc = IngestionDocument.objects.create(
        job=job,
        source_path="C:/tmp/rsp.csv",
        source_document="rsp.csv",
        source_type="manifesto",
        status="review_hold",
        held_count=1,
        payload_schema="rsp_manifesto_csv_v1",
    )
    item = ReviewQueueItem.objects.create(
        job=job,
        document=doc,
        status="approved",
        reason="manual_ok",
        entity_type="PoliticalPromise",
        fingerprint="promise:1",
        proposed_payload={
            "entity_type": "PoliticalPromise",
            "record_identity": "promise:1",
            "graph_payload": {
                "id": "promise:1",
                "key": "politicalPromiseId",
                "properties": {"political_promise_id": "promise:1", "title": "Promise title long enough", "source_reference": "rsp.csv"},
            },
            "graph_relations": [],
        },
    )

    monkeypatch.setattr(command_module, "ensure_smart_constraints", lambda: None)
    monkeypatch.setattr(command_module, "publish_record", lambda payload: {"ok": True, "node_id": payload["record_identity"]})

    out = io.StringIO()
    call_command("ingestion_publish_review", stdout=out)
    payload = json.loads(out.getvalue())

    item.refresh_from_db()
    doc.refresh_from_db()
    job.refresh_from_db()
    assert payload["published"] == 1
    assert item.status == "resolved"
    assert doc.published_count == 1
    assert doc.held_count == 0
    assert job.published_count == 1


@pytest.mark.django_db
def test_publish_review_command_blocks_unreviewed_rsp_bacha_patra_ocr_placeholder(monkeypatch):
    from tracker.management.commands import ingestion_publish_review as command_module

    job = IngestionJob.objects.create(name="bacha-review-job", status="review_hold")
    doc = IngestionDocument.objects.create(
        job=job,
        source_path="C:/tmp/bacha-patra.pdf",
        source_document="bacha-patra.pdf",
        source_type="manifesto",
        status="review_hold",
        held_count=1,
        payload_schema="rsp_bacha_patra_v1",
    )
    item = ReviewQueueItem.objects.create(
        job=job,
        document=doc,
        status="approved",
        reason="manual_ok",
        entity_type="ManifestoDocument",
        fingerprint="bacha:doc:1",
        proposed_payload={
            "entity_type": "ManifestoDocument",
            "record_identity": "bacha:doc:1",
            "source_subtype": "rsp_bacha_patra_pdf",
            "raw_payload": {
                "document_kind": "bacha_patra",
                "extraction_mode": "document_provenance_only",
                "ocr_workflow": {
                    "workflow_kind": "rsp_bacha_patra_ocr_review",
                    "structured_promises_status": "not_extracted",
                },
            },
            "graph_payload": {
                "id": "bacha:doc:1",
                "key": "manifestoDocumentId",
                "properties": {"manifesto_document_id": "bacha:doc:1", "title": "Bacha Patra", "source_reference": "bacha-patra.pdf"},
            },
            "graph_relations": [],
        },
    )

    monkeypatch.setattr(command_module, "ensure_smart_constraints", lambda: None)
    monkeypatch.setattr(command_module, "publish_record", lambda payload: {"ok": True, "node_id": payload["record_identity"]})

    out = io.StringIO()
    call_command("ingestion_publish_review", stdout=out)
    payload = json.loads(out.getvalue())

    item.refresh_from_db()
    doc.refresh_from_db()
    job.refresh_from_db()
    assert payload["published"] == 0
    assert payload["failed"] == 1
    assert payload["failures"][0]["reason"] == "ocr_review_incomplete"
    assert item.status == "approved"
    assert doc.published_count == 0
    assert doc.held_count == 1


@pytest.mark.django_db
def test_publish_review_command_publishes_reviewed_rsp_bacha_patra_structured_promise(monkeypatch):
    from tracker.management.commands import ingestion_publish_review as command_module

    job = IngestionJob.objects.create(name="bacha-reviewed-publish-job", status="review_hold")
    doc = IngestionDocument.objects.create(
        job=job,
        source_path="C:/tmp/bacha-patra.pdf",
        source_document="bacha-patra.pdf",
        source_type="manifesto",
        status="review_hold",
        held_count=1,
        payload_schema="rsp_bacha_patra_v1",
    )
    item = ReviewQueueItem.objects.create(
        job=job,
        document=doc,
        status="approved",
        reason="manual_ok",
        entity_type="PoliticalPromise",
        fingerprint="promise:reviewed:1",
        proposed_payload={
            "entity_type": "PoliticalPromise",
            "record_identity": "promise:reviewed:1",
            "source_subtype": "rsp_bacha_patra_pdf",
            "raw_payload": {
                "title": "Publish local spending reports every quarter",
                "source_excerpt": "??????? ???? ????? ???? ????????? ????????? ?????",
                "source_page": 3,
                "placeholder": False,
                "extraction_confidence": 0.91,
                "reviewer_status": "approved",
                "manifesto_document_id": "manifesto_document:abc",
                "extraction_mode": "reviewed_structured_promises",
            },
            "review_context": {
                "workflow": {
                    "workflow_kind": "rsp_bacha_patra_ocr_review",
                    "structured_promises_status": "reviewed_approved",
                    "ocr_text_review_status": "approved",
                }
            },
            "graph_payload": {
                "id": "promise:reviewed:1",
                "key": "politicalPromiseId",
                "properties": {
                    "political_promise_id": "promise:reviewed:1",
                    "title": "Publish local spending reports every quarter",
                    "source_reference": "bacha-patra.pdf",
                },
            },
            "graph_relations": [],
        },
    )

    monkeypatch.setattr(command_module, "ensure_smart_constraints", lambda: None)
    monkeypatch.setattr(command_module, "publish_record", lambda payload: {"ok": True, "node_id": payload["record_identity"]})

    out = io.StringIO()
    call_command("ingestion_publish_review", stdout=out)
    payload = json.loads(out.getvalue())

    item.refresh_from_db()
    doc.refresh_from_db()
    job.refresh_from_db()
    assert payload["published"] == 1
    assert payload["failed"] == 0
    assert item.status == "resolved"
    assert doc.published_count == 1
    assert doc.held_count == 0
    assert job.published_count == 1


@pytest.mark.django_db
def test_publish_review_command_blocks_incomplete_reviewed_rsp_bacha_patra_structured_promise(monkeypatch):
    from tracker.management.commands import ingestion_publish_review as command_module

    job = IngestionJob.objects.create(name="bacha-reviewed-block-job", status="review_hold")
    doc = IngestionDocument.objects.create(
        job=job,
        source_path="C:/tmp/bacha-patra.pdf",
        source_document="bacha-patra.pdf",
        source_type="manifesto",
        status="review_hold",
        held_count=1,
        payload_schema="rsp_bacha_patra_v1",
    )
    item = ReviewQueueItem.objects.create(
        job=job,
        document=doc,
        status="approved",
        reason="manual_ok",
        entity_type="PoliticalPromise",
        fingerprint="promise:reviewed:2",
        proposed_payload={
            "entity_type": "PoliticalPromise",
            "record_identity": "promise:reviewed:2",
            "source_subtype": "rsp_bacha_patra_pdf",
            "raw_payload": {
                "title": "Too weak confidence promise",
                "source_excerpt": "valid excerpt",
                "source_page": 3,
                "placeholder": False,
                "extraction_confidence": 0.45,
                "reviewer_status": "approved",
                "manifesto_document_id": "manifesto_document:abc",
                "extraction_mode": "reviewed_structured_promises",
            },
            "review_context": {
                "workflow": {
                    "workflow_kind": "rsp_bacha_patra_ocr_review",
                    "structured_promises_status": "reviewed_approved",
                    "ocr_text_review_status": "approved",
                }
            },
            "graph_payload": {
                "id": "promise:reviewed:2",
                "key": "politicalPromiseId",
                "properties": {
                    "political_promise_id": "promise:reviewed:2",
                    "title": "Too weak confidence promise",
                    "source_reference": "bacha-patra.pdf",
                },
            },
            "graph_relations": [],
        },
    )

    monkeypatch.setattr(command_module, "ensure_smart_constraints", lambda: None)
    monkeypatch.setattr(command_module, "publish_record", lambda payload: {"ok": True, "node_id": payload["record_identity"]})

    out = io.StringIO()
    call_command("ingestion_publish_review", stdout=out)
    payload = json.loads(out.getvalue())

    item.refresh_from_db()
    doc.refresh_from_db()
    assert payload["published"] == 0
    assert payload["failed"] == 1
    assert payload["failures"][0]["reason"] == "reviewed_ocr_payload_incomplete"
    assert item.status == "approved"
    assert doc.published_count == 0
    assert doc.held_count == 1



@pytest.mark.django_db
def test_publish_review_command_publishes_reviewed_alignment_assessment(monkeypatch):
    from tracker.management.commands import ingestion_publish_review as command_module

    job = IngestionJob.objects.create(name="alignment-review-job", status="review_hold")
    doc = IngestionDocument.objects.create(
        job=job,
        source_path="C:/tmp/nepalreforms_agenda.json",
        source_document="nepalreforms_agenda.json",
        source_type="manifesto",
        status="review_hold",
        held_count=1,
        payload_schema="nepalreforms_agenda_v1",
    )
    item = ReviewQueueItem.objects.create(
        job=job,
        document=doc,
        status="approved",
        reason="manual_ok",
        entity_type="AlignmentAssessment",
        fingerprint="alignment:reviewed:1",
        proposed_payload={
            "entity_type": "AlignmentAssessment",
            "record_identity": "alignment:reviewed:1",
            "source_subtype": "agenda_promise_alignment_review",
            "raw_payload": {
                "agenda_item_id": "agenda_item:abc",
                "political_promise_id": "political_promise:def",
                "relation_type": "PARTIALLY_ALIGNS",
                "confidence": 0.91,
                "approval_state": "approved",
                "notes": "Reviewed overlap.",
                "reviewer_status": "approved",
                "placeholder": False,
                "extraction_mode": "reviewed_alignment_assessments",
            },
            "review_context": {
                "workflow": {
                    "workflow_kind": "agenda_promise_alignment_review",
                    "reviewed_alignment_status": "reviewed_approved",
                }
            },
            "graph_payload": {
                "id": "alignment:reviewed:1",
                "key": "alignmentAssessmentId",
                "properties": {
                    "alignment_assessment_id": "alignment:reviewed:1",
                    "agenda_item_id": "agenda_item:abc",
                    "political_promise_id": "political_promise:def",
                    "relation_type": "PARTIALLY_ALIGNS",
                    "confidence": 0.91,
                    "approval_state": "approved",
                },
            },
            "graph_relations": [],
        },
    )

    monkeypatch.setattr(command_module, "ensure_smart_constraints", lambda: None)
    monkeypatch.setattr(command_module, "publish_record", lambda payload: {"ok": True, "node_id": payload["record_identity"]})

    out = io.StringIO()
    call_command("ingestion_publish_review", stdout=out)
    payload = json.loads(out.getvalue())

    item.refresh_from_db()
    doc.refresh_from_db()
    job.refresh_from_db()
    assert payload["published"] == 1
    assert payload["failed"] == 0
    assert item.status == "resolved"
    assert doc.published_count == 1
    assert doc.held_count == 0
    assert job.published_count == 1


@pytest.mark.django_db
def test_publish_review_command_blocks_incomplete_reviewed_alignment_assessment(monkeypatch):
    from tracker.management.commands import ingestion_publish_review as command_module

    job = IngestionJob.objects.create(name="alignment-review-block-job", status="review_hold")
    doc = IngestionDocument.objects.create(
        job=job,
        source_path="C:/tmp/nepalreforms_agenda.json",
        source_document="nepalreforms_agenda.json",
        source_type="manifesto",
        status="review_hold",
        held_count=1,
        payload_schema="nepalreforms_agenda_v1",
    )
    item = ReviewQueueItem.objects.create(
        job=job,
        document=doc,
        status="approved",
        reason="manual_ok",
        entity_type="AlignmentAssessment",
        fingerprint="alignment:reviewed:2",
        proposed_payload={
            "entity_type": "AlignmentAssessment",
            "record_identity": "alignment:reviewed:2",
            "source_subtype": "agenda_promise_alignment_review",
            "raw_payload": {
                "agenda_item_id": "agenda_item:abc",
                "political_promise_id": "",
                "relation_type": "PARTIALLY_ALIGNS",
                "confidence": 0.45,
                "approval_state": "approved",
                "notes": "Too weak.",
                "reviewer_status": "approved",
                "placeholder": False,
                "extraction_mode": "reviewed_alignment_assessments",
            },
            "review_context": {
                "workflow": {
                    "workflow_kind": "agenda_promise_alignment_review",
                    "reviewed_alignment_status": "reviewed_approved",
                }
            },
            "graph_payload": {
                "id": "alignment:reviewed:2",
                "key": "alignmentAssessmentId",
                "properties": {
                    "alignment_assessment_id": "alignment:reviewed:2",
                    "agenda_item_id": "agenda_item:abc",
                    "relation_type": "PARTIALLY_ALIGNS",
                    "confidence": 0.45,
                    "approval_state": "approved",
                },
            },
            "graph_relations": [],
        },
    )

    monkeypatch.setattr(command_module, "ensure_smart_constraints", lambda: None)
    monkeypatch.setattr(command_module, "publish_record", lambda payload: {"ok": True, "node_id": payload["record_identity"]})

    out = io.StringIO()
    call_command("ingestion_publish_review", stdout=out)
    payload = json.loads(out.getvalue())

    item.refresh_from_db()
    doc.refresh_from_db()
    assert payload["published"] == 0
    assert payload["failed"] == 1
    assert payload["failures"][0]["reason"] == "reviewed_alignment_payload_incomplete"
    assert item.status == "approved"
    assert doc.published_count == 0
    assert doc.held_count == 1

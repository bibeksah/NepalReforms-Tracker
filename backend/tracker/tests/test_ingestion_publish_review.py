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

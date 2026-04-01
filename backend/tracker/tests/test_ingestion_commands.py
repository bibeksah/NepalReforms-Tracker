import io
import json
import os
import tempfile
from pathlib import Path

import django
import pytest
from django.core.management import call_command

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import tracker.agents.smart_ingestion_engine as engine
from tracker.models import IngestionDocument, IngestionJob


@pytest.mark.django_db
def test_submit_command_queues_structured_agenda_document():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        agenda_path = Path(tmp_dir) / "nepalreforms_agenda.json"
        agenda_path.write_text('{"organization":"NepalReforms","items":[]}', encoding="utf-8")

        out = io.StringIO()
        call_command(
            "ingestion_submit",
            "--document",
            str(agenda_path),
            "--name",
            "agenda-submit-job",
            "--requested-by",
            "pytest",
            stdout=out,
        )
        payload = json.loads(out.getvalue())

        job = IngestionJob.objects.get(id=payload["job_id"])
        document = job.documents.get()
        assert payload["status"] == "queued"
        assert payload["documents_created"] == 1
        assert job.name == "agenda-submit-job"
        assert job.requested_by == "pytest"
        assert document.source_type == "manifesto"
        assert document.source_document == "nepalreforms_agenda.json"
        assert document.status == "queued"


@pytest.mark.django_db
def test_run_command_executes_latest_job(monkeypatch):
    job = IngestionJob.objects.create(name="run-job", status="queued")
    IngestionDocument.objects.create(
        job=job,
        source_path="C:/tmp/nepalreforms_agenda.json",
        source_document="nepalreforms_agenda.json",
        source_type="manifesto",
        status="queued",
    )

    captured = {}

    def fake_run_job(job_arg, *, max_workers, adaptive, publish_threshold):
        captured.update(
            job_id=str(job_arg.id),
            max_workers=max_workers,
            adaptive=adaptive,
            publish_threshold=publish_threshold,
        )
        return {
            "job_id": str(job_arg.id),
            "status": "completed",
            "workers_used": 2,
            "processed": 1,
            "published_count": 3,
            "held_count": 0,
            "failed_count": 0,
        }

    monkeypatch.setattr(engine, "run_job", fake_run_job)
    from tracker.management.commands import ingestion_run as command_module
    monkeypatch.setattr(command_module, "run_job", fake_run_job)

    out = io.StringIO()
    call_command(
        "ingestion_run",
        "--job-id",
        "latest",
        "--max-workers",
        "2",
        "--publish-threshold",
        "0.91",
        stdout=out,
    )
    payload = json.loads(out.getvalue())

    assert captured == {
        "job_id": str(job.id),
        "max_workers": 2,
        "adaptive": True,
        "publish_threshold": 0.91,
    }
    assert payload["status"] == "completed"
    assert payload["published_count"] == 3


@pytest.mark.django_db
def test_submit_command_queues_bacha_patra_pdf_as_manifesto():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        pdf_path = Path(tmp_dir) / "वाचा पत्र .pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%stub\n")

        out = io.StringIO()
        call_command(
            "ingestion_submit",
            "--document",
            str(pdf_path),
            "--name",
            "bacha-submit-job",
            "--requested-by",
            "pytest",
            stdout=out,
        )
        payload = json.loads(out.getvalue())

        job = IngestionJob.objects.get(id=payload["job_id"])
        document = job.documents.get()
        assert document.source_type == "manifesto"
        assert document.source_document == "वाचा पत्र .pdf"

import os
from pathlib import Path
from types import SimpleNamespace
import tempfile

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import tracker.agents.smart_ingestion_engine as engine
from tracker.agents.smart_neo4j_publisher import compute_project_fingerprint


def test_detect_source_type():
    assert engine.detect_source_type("C:/x/LalKitab/Federal/Redbook_2081_82.pdf") == "lal_kitab"
    assert engine.detect_source_type("C:/x/RSP_manifesto_2027.pdf") == "manifesto"
    assert engine.detect_source_type("C:/x/RSPdocs/rsp_commitments.csv") == "manifesto"
    assert engine.detect_source_type("C:/x/RSPdocs/वाचा पत्र .pdf") == "manifesto"
    assert engine.detect_source_type("C:/x/citizen_report.json") == "citizen"
    assert engine.detect_source_type("C:/x/random.txt") == "other"


def test_source_subtype_detection():
    assert engine._source_subtype(SimpleNamespace(source_path="C:/x/nepalreforms_agenda.json", source_document="nepalreforms_agenda.json", source_type="manifesto")) == "nepalreforms_agenda_json"
    assert engine._source_subtype(SimpleNamespace(source_path="C:/x/RSPdocs/rsp_commitments.csv", source_document="rsp_commitments.csv", source_type="manifesto")) == "rsp_manifesto_csv"
    assert engine._source_subtype(SimpleNamespace(source_path="C:/x/RSPdocs/???? ???? .pdf", source_document="???? ???? .pdf", source_type="manifesto")) == "rsp_bacha_patra_pdf"
    assert engine._source_subtype(SimpleNamespace(source_path="C:/x/RSP_manifesto_2027.pdf", source_document="RSP_manifesto_2027.pdf", source_type="manifesto")) == "manifesto_pdf"


def test_adaptive_worker_count():
    assert engine._adaptive_worker_count(total_docs=2, requested=8, adaptive=True) == 1
    assert engine._adaptive_worker_count(total_docs=5, requested=8, adaptive=True) == 2
    assert engine._adaptive_worker_count(total_docs=10, requested=8, adaptive=True) == 3
    assert engine._adaptive_worker_count(total_docs=20, requested=8, adaptive=True) == 4
    assert engine._adaptive_worker_count(total_docs=20, requested=2, adaptive=False) == 2


def test_compute_project_fingerprint_is_stable():
    record = {
        "title_ne": "Road Expansion Plan Nepali",
        "title_en": "Road Expansion Plan",
        "budget": 1000000,
        "fiscal_year": "2081/82",
        "gov_level": "provincial",
        "province_name": "Bagmati",
        "source_hash": "abc123",
        "page_num": 12,
    }
    fp1 = compute_project_fingerprint(record)
    fp2 = compute_project_fingerprint(record)
    assert fp1 == fp2
    assert len(fp1) == 64


def test_plan_document_strategy_fallback(monkeypatch):
    monkeypatch.setattr(engine.router, "query_reasoning", lambda _prompt: "not-json")
    monkeypatch.setattr(engine, "get_lal_kitab_page_count", lambda _path: 120)
    monkeypatch.setattr(engine, "_ingest_lal_kitab", lambda *_args, **_kwargs: {"raw_projects": [], "garbled_pages": [1, 2, 3, 4]})
    doc = SimpleNamespace(source_type="lal_kitab", source_tier="A", source_document="Redbook_2081_82.pdf", source_path="C:/x/LalKitab/Federal/Redbook_2081_82.pdf")
    plan = engine.plan_document_strategy(doc)
    assert plan["strategy"] in {"vision", "hybrid"}
    assert plan["requires_vision"] is True


def test_extract_lal_kitab_vision_strategy_uses_all_pages(monkeypatch):
    captured_kwargs = {}

    def fake_ingest(_source_path, **kwargs):
        captured_kwargs.update(kwargs)
        return {"raw_projects": [{"title_ne": "Nepali title", "budget": "1000", "page_num": 1}], "garbled_pages": []}

    monkeypatch.setattr(engine, "get_lal_kitab_page_count", lambda _path: 3)
    monkeypatch.setattr(engine, "_ingest_lal_kitab", fake_ingest)
    monkeypatch.setattr(engine, "clean_and_validate", lambda _state: {"cleaned_projects": [{"title_ne": "Nepali title", "budget": 1000, "page_num": 1, "budget_source": "vision", "budget_hash": "x"}]})
    monkeypatch.setattr(engine, "validate_project_batch", lambda projects: (projects, []))
    monkeypatch.setattr(engine, "normalize_translate", lambda _state: {"translated_projects": [{"title_ne": "Nepali title", "title_en": "Road", "budget": 1000, "page_num": 1, "budget_source": "vision", "budget_hash": "x", "translation_confidence": 0.98, "translation_flag": "ok"}]})
    doc = SimpleNamespace(source_path="C:/x/LalKitab/Federal/Redbook_2081_82.pdf", source_document="Redbook_2081_82.pdf", source_hash="abc123", source_type="lal_kitab", gov_level="federal", province_name="", fiscal_year="2081/82", id="doc-1")

    records = engine._extract_lal_kitab(doc, {"strategy": "vision"})
    assert captured_kwargs["vision_page_numbers"] == [1, 2, 3]
    assert records[0]["confidence"] >= 0.75
    assert len(records[0]["fingerprint"]) == 64
    assert records[0]["record_identity"] == records[0]["fingerprint"]


def test_extract_nepalreforms_agenda_json():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        agenda_path = Path(tmp_dir) / "nepalreforms_agenda.json"
        agenda_path.write_text('{"organization":"NepalReforms","version":"2026 Baseline","effective_from":"2026-01-01","items":[{"id":"A-1","title":"Fix procurement transparency","description":"Open budgets and tenders","category":"Governance","timeline":"2026 Q2","priority":"high"}]}', encoding="utf-8")
        doc = SimpleNamespace(source_path=str(agenda_path), source_document=agenda_path.name, source_hash="hash-agenda", source_type="manifesto")

        records = engine._extract_nepalreforms_agenda_json(doc)
        assert [record["entity_type"] for record in records] == ["ManifestoDocument", "AgendaVersion", "AgendaItem"]
        assert records[1]["graph_relations"][0]["target_entity_type"] == "ManifestoDocument"
        assert any(rel["target_entity_type"] == "AgendaVersion" for rel in records[2]["graph_relations"])
        assert any(rel["target_entity_type"] == "PolicyCategory" for rel in records[2]["graph_relations"])


def test_extract_rsp_manifesto_csv():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        csv_path = Path(tmp_dir) / "rsp_manifesto.csv"
        csv_path.write_text("Category,Specific_Promise,Target_Deadline,Responsible_Entity\nGovernance,Publish all budget decisions within 48 hours,100 Days,Prime Minister's Office\n", encoding="utf-8")
        doc = SimpleNamespace(source_path=str(csv_path), source_document=csv_path.name, source_hash="hash-rsp", source_type="manifesto")

        records = engine._extract_rsp_manifesto_csv(doc)
        assert [record["entity_type"] for record in records] == ["ManifestoDocument", "PoliticalPromise"]
        promise = records[1]
        assert any(rel["target_entity_type"] == "PolicyCategory" for rel in promise["graph_relations"])
        assert any(rel["target_entity_type"] == "TimelineTarget" for rel in promise["graph_relations"])
        assert any(rel["target_entity_type"] == "ResponsibleEntity" for rel in promise["graph_relations"])


def test_extract_rsp_bacha_patra_pdf_sets_explicit_ocr_review_workflow():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        pdf_path = Path(tmp_dir) / "bacha patra.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%stub\n")
        doc = SimpleNamespace(source_path=str(pdf_path), source_document=pdf_path.name, source_hash="hash-bacha", source_type="manifesto")

        records = engine._extract_rsp_bacha_patra_pdf(doc)

        assert len(records) == 1
        record = records[0]
        assert record["entity_type"] == "ManifestoDocument"
        assert record["raw_payload"]["extraction_mode"] == "document_provenance_only"
        workflow = record["raw_payload"]["ocr_workflow"]
        assert workflow["workflow_kind"] == "rsp_bacha_patra_ocr_review"
        assert workflow["ocr_status"] == "not_run"
        assert workflow["structured_promises_status"] == "not_extracted"
        assert workflow["review_required_for_structured_promises"] is True
        assert record["review_context"]["workflow"]["publishable_record_kind"] == "document_provenance_only"



def test_extract_reviewed_rsp_bacha_patra_structured_promises_requires_reviewed_bundle():
    doc = SimpleNamespace(
        source_path="C:/x/bacha-patra.pdf",
        source_document="bacha-patra.pdf",
        source_hash="hash-bacha",
        source_type="manifesto",
        extra_metadata={},
    )

    assert engine._extract_reviewed_rsp_bacha_patra_structured_promises(doc) == []


def test_extract_reviewed_rsp_bacha_patra_structured_promises_builds_safe_political_promise_records():
    doc = SimpleNamespace(
        source_path="C:/x/bacha-patra.pdf",
        source_document="bacha-patra.pdf",
        source_hash="hash-bacha",
        source_type="manifesto",
        extra_metadata={
            "reviewed_structured_promise_bundle": {
                "manifesto_document_id": "manifesto_document:abc",
                "source_reference": "C:/x/bacha-patra.pdf",
                "source_subtype": "rsp_bacha_patra_pdf",
                "extraction_mode": "reviewed_structured_promises",
                "ocr_artifact_reference": "artifact://bacha-ocr-v1.json",
                "ocr_text_review_status": "approved",
                "structured_promises_status": "reviewed_approved",
                "reviewed_structured_promises": [
                    {
                        "title": "Publish local spending reports every quarter",
                        "summary": "Quarterly public reporting on local spending.",
                        "category": "Governance",
                        "timeline": "Quarterly",
                        "responsible_entity": "Local Governments",
                        "language": "ne",
                        "source_page": 3,
                        "source_excerpt": "??????? ???? ????? ???? ????????? ????????? ?????",
                        "extraction_confidence": 0.91,
                        "reviewer_status": "approved",
                        "placeholder": False,
                    },
                    {
                        "title": "Placeholder should never publish",
                        "summary": "",
                        "category": "",
                        "timeline": "",
                        "responsible_entity": "",
                        "language": "ne",
                        "source_page": 4,
                        "source_excerpt": "placeholder excerpt",
                        "extraction_confidence": 0.99,
                        "reviewer_status": "approved",
                        "placeholder": True,
                    },
                    {
                        "title": "Low confidence should stay out of publish path",
                        "summary": "",
                        "category": "",
                        "timeline": "",
                        "responsible_entity": "",
                        "language": "ne",
                        "source_page": 5,
                        "source_excerpt": "low confidence excerpt",
                        "extraction_confidence": 0.55,
                        "reviewer_status": "approved",
                        "placeholder": False,
                    },
                ],
            }
        },
    )

    records = engine._extract_reviewed_rsp_bacha_patra_structured_promises(doc)

    assert len(records) == 1
    record = records[0]
    assert record["entity_type"] == "PoliticalPromise"
    assert record["source_subtype"] == "rsp_bacha_patra_pdf"
    assert record["confidence"] == pytest.approx(0.91)
    assert record["raw_payload"]["manifesto_document_id"] == "manifesto_document:abc"
    assert record["raw_payload"]["extraction_mode"] == "reviewed_structured_promises"
    assert record["graph_payload"]["properties"]["derived_from_document_id"] == "manifesto_document:abc"
    assert any(rel["relation_type"] == "PROMISED_IN" and rel["target_entity_type"] == "ManifestoDocument" for rel in record["graph_relations"])
    assert any(rel["target_entity_type"] == "PolicyCategory" for rel in record["graph_relations"])
    assert any(rel["target_entity_type"] == "TimelineTarget" for rel in record["graph_relations"])
    assert any(rel["target_entity_type"] == "ResponsibleEntity" for rel in record["graph_relations"])


def test_run_with_retry_retries_transient(monkeypatch):
    attempts = {"n": 0}
    monkeypatch.setattr(engine.time, "sleep", lambda _delay: None)
    monkeypatch.setattr(engine.random, "uniform", lambda _a, _b: 0.0)

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("service unavailable 503")
        return "ok"

    result = engine._run_with_retry("test_op", flaky)
    assert result == "ok"
    assert attempts["n"] == 3

@pytest.mark.django_db(transaction=True)
def test_run_job_publishes_deterministic_agenda_records(monkeypatch):
    from tracker.models import IngestionDocument, IngestionJob, ReviewQueueItem

    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        agenda_path = Path(tmp_dir) / "nepalreforms_agenda.json"
        agenda_path.write_text(
            '{"organization":"NepalReforms","version":"2026 Baseline","effective_from":"2026-01-01","items":[{"id":"A-1","title":"Fix procurement transparency","description":"Open budgets and tenders","category":"Governance","timeline":"2026 Q2","priority":"high"}]}',
            encoding="utf-8",
        )
        job = IngestionJob.objects.create(name="agenda-job", status="queued")
        document = IngestionDocument.objects.create(
            job=job,
            source_path=str(agenda_path),
            source_document=agenda_path.name,
            source_hash="hash-agenda",
            source_type="manifesto",
            status="queued",
        )

        published = []
        monkeypatch.setattr(engine, "ensure_smart_constraints", lambda: None)
        monkeypatch.setattr(engine, "publish_record", lambda record: published.append(record["entity_type"]) or {"ok": True, "node_id": record["record_identity"]})
        monkeypatch.setattr(engine, "publish_records_batch", lambda records, batch_size=200: {"ok_count": 0, "published_ids": [], "failed_ids": [], "errors": []})

        result = engine.run_job(job, max_workers=1, adaptive=False, publish_threshold=0.75)

        document.refresh_from_db()
        job.refresh_from_db()
        assert result["status"] == "completed"
        assert result["processed"] == 1
        assert result["published_count"] == 3
        assert result["held_count"] == 0
        assert published == ["ManifestoDocument", "AgendaVersion", "AgendaItem"]
        assert document.status == "published"
        assert document.payload_schema == "nepalreforms_agenda_v1"
        assert document.extracted_count == 3
        assert document.published_count == 3
        assert document.held_count == 0
        assert document.extra_metadata["source_subtype"] == "nepalreforms_agenda_json"
        assert job.documents.count() == 1
        assert ReviewQueueItem.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_run_job_holds_low_confidence_non_project_records(monkeypatch):
    from tracker.models import IngestionDocument, IngestionJob, ReviewQueueItem

    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        csv_path = Path(tmp_dir) / "rsp_manifesto.csv"
        csv_path.write_text(
            "Category,Specific_Promise,Target_Deadline,Responsible_Entity\nGovernance,Publish all budget decisions within 48 hours,100 Days,Prime Minister's Office\n",
            encoding="utf-8",
        )
        job = IngestionJob.objects.create(name="rsp-job", status="queued")
        document = IngestionDocument.objects.create(
            job=job,
            source_path=str(csv_path),
            source_document=csv_path.name,
            source_hash="hash-rsp",
            source_type="manifesto",
            status="queued",
        )

        monkeypatch.setattr(engine, "ensure_smart_constraints", lambda: None)
        monkeypatch.setattr(engine, "publish_record", lambda record: {"ok": True, "node_id": record["record_identity"]})
        monkeypatch.setattr(engine, "publish_records_batch", lambda records, batch_size=200: {"ok_count": 0, "published_ids": [], "failed_ids": [], "errors": []})

        result = engine.run_job(job, max_workers=1, adaptive=False, publish_threshold=1.0)

        document.refresh_from_db()
        job.refresh_from_db()
        review_items = list(ReviewQueueItem.objects.order_by("created_at"))
        assert result["status"] == "review_hold"
        assert result["processed"] == 1
        assert result["published_count"] == 0
        assert result["held_count"] == 2
        assert document.status == "review_hold"
        assert document.payload_schema == "rsp_manifesto_csv_v1"
        assert document.extracted_count == 2
        assert document.published_count == 0
        assert document.held_count == 2
        assert len(review_items) == 2
        assert {item.entity_type for item in review_items} == {"ManifestoDocument", "PoliticalPromise"}
        assert all(item.status == "pending_review" for item in review_items)


@pytest.mark.django_db(transaction=True)
def test_run_job_holds_rsp_bacha_patra_for_review(monkeypatch):
    from tracker.models import IngestionDocument, IngestionJob, ReviewQueueItem

    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        pdf_path = Path(tmp_dir) / "bacha patra.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%stub\n")
        job = IngestionJob.objects.create(name="bacha-job", status="queued")
        document = IngestionDocument.objects.create(
            job=job,
            source_path=str(pdf_path),
            source_document=pdf_path.name,
            source_hash="hash-bacha",
            source_type="manifesto",
            status="queued",
        )

        monkeypatch.setattr(engine, "ensure_smart_constraints", lambda: None)
        monkeypatch.setattr(engine, "publish_record", lambda record: {"ok": True, "node_id": record["record_identity"]})
        monkeypatch.setattr(engine, "publish_records_batch", lambda records, batch_size=200: {"ok_count": 0, "published_ids": [], "failed_ids": [], "errors": []})
        monkeypatch.setattr(engine, "_extract_rsp_bacha_patra_pdf", lambda _doc: [{
            "entity_type": "ManifestoDocument",
            "record_identity": "bacha:doc:1",
            "confidence": 0.40,
            "risk_flags": ["source_native_scanned_manifesto", "ocr_review_required"],
            "graph_payload": {"id": "bacha:doc:1", "key": "manifestoDocumentId", "properties": {"manifesto_document_id": "bacha:doc:1", "document_kind": "bacha_patra", "source_reference": str(pdf_path)}},
            "graph_relations": [],
            "raw_payload": {"document_kind": "bacha_patra", "ocr_workflow": {"workflow_kind": "rsp_bacha_patra_ocr_review", "structured_promises_status": "not_extracted"}},
            "review_context": {"workflow": {"workflow_kind": "rsp_bacha_patra_ocr_review"}},
            "source_type": "manifesto",
            "source_subtype": "rsp_bacha_patra_pdf",
            "source_document": pdf_path.name,
            "source_path": str(pdf_path),
            "source_hash": "hash-bacha",
        }])

        result = engine.run_job(job, max_workers=1, adaptive=False, publish_threshold=0.75)

        document.refresh_from_db()
        review_items = list(ReviewQueueItem.objects.order_by("created_at"))
        assert result["status"] == "review_hold"
        assert result["processed"] == 1
        assert result["published_count"] == 0
        assert result["held_count"] == 1
        assert document.status == "review_hold"
        assert document.payload_schema == "rsp_bacha_patra_v1"
        assert document.extracted_count == 1
        assert document.published_count == 0
        assert document.held_count == 1
        assert len(review_items) == 1
        assert review_items[0].entity_type == "ManifestoDocument"
        assert review_items[0].proposed_payload["source_subtype"] == "rsp_bacha_patra_pdf"
        assert review_items[0].provenance["source_subtype"] == "rsp_bacha_patra_pdf"
        assert review_items[0].provenance["review_context"]["workflow"]["workflow_kind"] == "rsp_bacha_patra_ocr_review"
        assert document.extra_metadata["ocr_workflow"]["structured_promises_status"] == "not_extracted"


@pytest.mark.django_db(transaction=True)
def test_run_job_publishes_reviewed_rsp_bacha_patra_structured_promises(monkeypatch):
    from tracker.models import IngestionDocument, IngestionJob, ReviewQueueItem

    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        pdf_path = Path(tmp_dir) / "bacha patra.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%stub\n")
        job = IngestionJob.objects.create(name="bacha-reviewed-job", status="queued")
        document = IngestionDocument.objects.create(
            job=job,
            source_path=str(pdf_path),
            source_document=pdf_path.name,
            source_hash="hash-bacha-reviewed",
            source_type="manifesto",
            status="queued",
            extra_metadata={
                "reviewed_structured_promise_bundle": {
                    "manifesto_document_id": "manifesto_document:abc",
                    "source_reference": str(pdf_path),
                    "source_subtype": "rsp_bacha_patra_pdf",
                    "extraction_mode": "reviewed_structured_promises",
                    "ocr_artifact_reference": "artifact://bacha-ocr-v1.json",
                    "ocr_text_review_status": "approved",
                    "structured_promises_status": "reviewed_approved",
                    "reviewed_structured_promises": [
                        {
                            "title": "Publish local spending reports every quarter",
                            "summary": "Quarterly public reporting on local spending.",
                            "category": "Governance",
                            "timeline": "Quarterly",
                            "responsible_entity": "Local Governments",
                            "language": "ne",
                            "source_page": 3,
                            "source_excerpt": "??????? ???? ????? ???? ????????? ????????? ?????",
                            "extraction_confidence": 0.91,
                            "reviewer_status": "approved",
                            "placeholder": False,
                        }
                    ],
                }
            },
        )

        published = []
        monkeypatch.setattr(engine, "ensure_smart_constraints", lambda: None)
        monkeypatch.setattr(engine, "publish_record", lambda record: published.append(record) or {"ok": True, "node_id": record["record_identity"]})
        monkeypatch.setattr(engine, "publish_records_batch", lambda records, batch_size=200: {"ok_count": 0, "published_ids": [], "failed_ids": [], "errors": []})

        result = engine.run_job(job, max_workers=1, adaptive=False, publish_threshold=0.75)

        document.refresh_from_db()
        job.refresh_from_db()
        assert result["status"] == "completed"
        assert result["published_count"] == 1
        assert result["held_count"] == 0
        assert len(published) == 1
        assert published[0]["entity_type"] == "PoliticalPromise"
        assert published[0]["source_subtype"] == "rsp_bacha_patra_pdf"
        assert document.status == "published"
        assert document.extra_metadata["ocr_workflow"]["structured_promises_status"] == "reviewed_approved"
        assert document.extra_metadata["ocr_workflow"]["ocr_status"] == "reviewed_artifact_supplied"
        assert ReviewQueueItem.objects.count() == 0



def test_extract_nepalreforms_agenda_json_preserves_nested_structures_in_raw_payload():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp_dir:
        agenda_path = Path(tmp_dir) / "nepalreforms_agenda.json"
        agenda_path.write_text('{"organization":"NepalReforms","version":"2026 Baseline","effective_from":"2026-01-01","items":[{"id":"A-1","title":"Fix procurement transparency","description":"Open budgets and tenders","category":"Governance","timeline":"2026 Q2","priority":"high","problem":{"short":"bad","long":"worse"},"solution":{"short":["one"],"long":{"phases":[{"phase":"1"}]}}}]}', encoding="utf-8")
        doc = SimpleNamespace(source_path=str(agenda_path), source_document=agenda_path.name, source_hash="hash-agenda", source_type="manifesto")

        records = engine._extract_nepalreforms_agenda_json(doc)
        agenda_item = records[2]
        assert isinstance(agenda_item["raw_payload"]["problem"], dict)
        assert isinstance(agenda_item["raw_payload"]["solution"], dict)

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
    assert engine.detect_source_type("C:/x/citizen_report.json") == "citizen"
    assert engine.detect_source_type("C:/x/random.txt") == "other"


def test_source_subtype_detection():
    assert engine._source_subtype(SimpleNamespace(source_path="C:/x/nepalreforms_agenda.json", source_document="nepalreforms_agenda.json", source_type="manifesto")) == "nepalreforms_agenda_json"
    assert engine._source_subtype(SimpleNamespace(source_path="C:/x/RSPdocs/rsp_commitments.csv", source_document="rsp_commitments.csv", source_type="manifesto")) == "rsp_manifesto_csv"
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

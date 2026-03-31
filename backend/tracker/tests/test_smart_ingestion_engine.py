import os
from types import SimpleNamespace

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import tracker.agents.smart_ingestion_engine as engine
from tracker.agents.smart_neo4j_publisher import compute_project_fingerprint


def test_detect_source_type():
    assert engine.detect_source_type("C:/x/LalKitab/Federal/Redbook_2081_82.pdf") == "lal_kitab"
    assert engine.detect_source_type("C:/x/RSP_manifesto_2027.pdf") == "manifesto"
    assert engine.detect_source_type("C:/x/citizen_report.json") == "citizen"
    assert engine.detect_source_type("C:/x/random.txt") == "other"


def test_adaptive_worker_count():
    assert engine._adaptive_worker_count(total_docs=2, requested=8, adaptive=True) == 1
    assert engine._adaptive_worker_count(total_docs=5, requested=8, adaptive=True) == 2
    assert engine._adaptive_worker_count(total_docs=10, requested=8, adaptive=True) == 3
    assert engine._adaptive_worker_count(total_docs=20, requested=8, adaptive=True) == 4
    assert engine._adaptive_worker_count(total_docs=20, requested=2, adaptive=False) == 2


def test_compute_project_fingerprint_is_stable():
    record = {
        "title_ne": " सडक विस्तार योजना ",
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
    # Force planner JSON parse failure so fallback heuristic is used.
    monkeypatch.setattr(engine.router, "query_reasoning", lambda _prompt: "not-json")
    monkeypatch.setattr(engine, "get_lal_kitab_page_count", lambda _path: 120)
    monkeypatch.setattr(
        engine,
        "_ingest_lal_kitab",
        lambda *_args, **_kwargs: {"raw_projects": [], "garbled_pages": [1, 2, 3, 4]},
    )
    doc = SimpleNamespace(
        source_type="lal_kitab",
        source_tier="A",
        source_document="Redbook_2081_82.pdf",
        source_path="C:/x/LalKitab/Federal/Redbook_2081_82.pdf",
    )
    plan = engine.plan_document_strategy(doc)
    assert plan["strategy"] in {"vision", "hybrid"}
    assert plan["requires_vision"] is True


def test_extract_lal_kitab_vision_strategy_uses_all_pages(monkeypatch):
    captured_kwargs = {}

    def fake_ingest(_source_path, **kwargs):
        captured_kwargs.update(kwargs)
        return {"raw_projects": [{"title_ne": "सडक", "budget": "1000", "page_num": 1}], "garbled_pages": []}

    monkeypatch.setattr(engine, "get_lal_kitab_page_count", lambda _path: 3)
    monkeypatch.setattr(engine, "_ingest_lal_kitab", fake_ingest)
    monkeypatch.setattr(engine, "clean_and_validate", lambda _state: {"cleaned_projects": [{"title_ne": "सडक", "budget": 1000, "page_num": 1, "budget_source": "vision", "budget_hash": "x"}]})
    monkeypatch.setattr(engine, "validate_project_batch", lambda projects: (projects, []))
    monkeypatch.setattr(
        engine,
        "normalize_translate",
        lambda _state: {
            "translated_projects": [
                {
                    "title_ne": "सडक",
                    "title_en": "Road",
                    "budget": 1000,
                    "page_num": 1,
                    "budget_source": "vision",
                    "budget_hash": "x",
                    "translation_confidence": 0.98,
                    "translation_flag": "ok",
                }
            ]
        },
    )
    doc = SimpleNamespace(
        source_path="C:/x/LalKitab/Federal/Redbook_2081_82.pdf",
        source_document="Redbook_2081_82.pdf",
        source_hash="abc123",
        source_type="lal_kitab",
        gov_level="federal",
        province_name="",
        fiscal_year="2081/82",
        id="doc-1",
    )

    records = engine._extract_lal_kitab(doc, {"strategy": "vision"})
    assert captured_kwargs["vision_page_numbers"] == [1, 2, 3]
    assert records[0]["confidence"] >= 0.75
    assert len(records[0]["fingerprint"]) == 64


def test_extract_manifesto_like_applies_english_preprocess(monkeypatch):
    source_path = "C:/virtual/sample_manifesto.txt"
    monkeypatch.setattr(engine.Path, "read_text", lambda _self, **_kwargs: "texto en espanol sobre politica publica")

    monkeypatch.setattr(
        engine,
        "ensure_english_text",
        lambda _text: {
            "success": True,
            "source_language": "es",
            "language_detection_confidence": 0.93,
            "language_detector": "heuristic",
            "translation_applied": True,
            "translation_status": "translated",
            "translation_confidence": 0.90,
            "translation_method": "llm_translation",
            "translation_error": "",
            "translated_text": "public policy commitments for roads and schools",
        },
    )
    monkeypatch.setattr(
        engine.router,
        "query_reasoning",
        lambda _prompt: '{"items":[{"promise_text":"Build roads and schools in all wards","category":"infrastructure","actor":"government","timeline":"2027","confidence":0.8}]}',
    )
    doc = SimpleNamespace(
        id="doc-manifesto-1",
        source_path=source_path,
        source_document="sample_manifesto.txt",
        source_hash="hash-1",
        extra_metadata={},
    )

    records = engine._extract_manifesto_like(doc)
    assert len(records) == 1
    assert records[0]["source_language"] == "es"
    assert records[0]["translation_applied"] is True
    assert doc.extra_metadata["translation_status"] == "translated"


def test_extract_manifesto_like_raises_when_translation_fails(monkeypatch):
    source_path = "C:/virtual/sample_manifesto_fail.txt"
    monkeypatch.setattr(engine.Path, "read_text", lambda _self, **_kwargs: "contenido no ingles")

    monkeypatch.setattr(
        engine,
        "ensure_english_text",
        lambda _text: {
            "success": False,
            "source_language": "es",
            "language_detection_confidence": 0.82,
            "language_detector": "heuristic",
            "translation_applied": True,
            "translation_status": "failed",
            "translation_confidence": 0.2,
            "translation_method": "llm_translation",
            "translation_error": "empty_translation_response",
            "translated_text": "",
        },
    )
    doc = SimpleNamespace(
        id="doc-manifesto-2",
        source_path=source_path,
        source_document="sample_manifesto_fail.txt",
        source_hash="hash-2",
        extra_metadata={},
    )

    with pytest.raises(engine.LanguagePreprocessError):
        engine._extract_manifesto_like(doc)
    assert doc.extra_metadata["translation_status"] == "failed"


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

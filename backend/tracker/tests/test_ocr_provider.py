import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import tracker.agents.ocr_provider as ocr_provider


def test_vision_ocr_provider_parses_projects(monkeypatch):
    monkeypatch.setattr(
        ocr_provider.router,
        "query_vision",
        lambda _img, _prompt: '[{"title_ne":"सडक योजना","budget":"1200000"}]',
    )
    provider = ocr_provider.VisionOCRProvider()
    rows = provider.extract_projects(b"img", page_num=1, log_context="test")
    assert len(rows) == 1
    assert rows[0]["ocr_provider"] == "vision"
    assert rows[0]["budget_source"] == "vision"


def test_get_ocr_provider_forced_vision(monkeypatch):
    monkeypatch.setenv("TRACKER_OCR_PROVIDER", "vision")
    provider = ocr_provider.get_ocr_provider()
    assert getattr(provider, "name", "") == "vision"

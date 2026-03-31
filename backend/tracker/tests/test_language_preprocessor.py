import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import tracker.agents.language_preprocessor as lp


def test_detect_language_identifies_devanagari():
    text = "\u0938\u0930\u0915\u093e\u0930\u0940 \u092f\u094b\u091c\u0928\u093e \u092c\u091c\u0947\u091f"
    result = lp.detect_language(text)
    assert result["language_code"] == "ne"
    assert result["confidence"] >= 0.8


def test_ensure_english_text_passthrough_for_english():
    result = lp.ensure_english_text("This is an English policy summary.")
    assert result["success"] is True
    assert result["source_language"] == "en"
    assert result["translation_applied"] is False


def test_ensure_english_text_reports_translation_failure(monkeypatch):
    monkeypatch.setattr(
        lp,
        "detect_language",
        lambda _text: {"language_code": "es", "confidence": 0.95, "detector": "test"},
    )
    monkeypatch.setattr(
        lp,
        "translate_to_english",
        lambda _text, _lang: {
            "success": False,
            "translated_text": "",
            "confidence": 0.0,
            "method": "test",
            "error": "forced_failure",
        },
    )
    result = lp.ensure_english_text("texto")
    assert result["success"] is False
    assert result["translation_status"] == "failed"
    assert result["translation_error"] == "forced_failure"

"""
Language preprocessing utilities for smart ingestion.

Goal:
  - Detect likely source language
  - Force English normalization for non-English inputs
  - Return structured lineage metadata for audit and retry
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from .router import router

LANG_DETECTION_CONFIDENCE_MIN = float(os.getenv("TRACKER_LANG_DETECTION_MIN_CONF", "0.70"))
TRANSLATION_CONFIDENCE_MIN = float(os.getenv("TRACKER_TRANSLATION_MIN_CONF", "0.70"))
MAX_DETECTION_CHARS = int(os.getenv("TRACKER_LANG_DETECTION_MAX_CHARS", "4000"))
MAX_TRANSLATION_CHARS = int(os.getenv("TRACKER_TRANSLATION_MAX_CHARS", "18000"))


def _strip_json_fence(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    return cleaned


def _safe_json_loads(text: str, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(_strip_json_fence(text))
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return fallback


def _heuristic_detect_language(sample: str) -> dict[str, Any]:
    if not sample.strip():
        return {"language_code": "en", "confidence": 1.0, "detector": "heuristic_empty"}

    devanagari_count = len(re.findall(r"[\u0900-\u097F]", sample))
    latin_count = len(re.findall(r"[A-Za-z]", sample))
    alpha_count = sum(1 for ch in sample if ch.isalpha())

    if devanagari_count >= 6 and devanagari_count > latin_count:
        return {"language_code": "ne", "confidence": 0.98, "detector": "heuristic_script"}

    if alpha_count == 0:
        return {"language_code": "unknown", "confidence": 0.20, "detector": "heuristic_low_alpha"}

    latin_ratio = latin_count / max(1, alpha_count)
    if latin_ratio >= 0.85:
        return {"language_code": "en", "confidence": 0.85, "detector": "heuristic_latin"}

    return {"language_code": "unknown", "confidence": 0.40, "detector": "heuristic_mixed"}


def detect_language(text: str) -> dict[str, Any]:
    sample = (text or "")[:MAX_DETECTION_CHARS]
    heuristic = _heuristic_detect_language(sample)

    if heuristic["confidence"] >= 0.85:
        return heuristic

    prompt = f"""
Detect the primary language of this text.
Return strict JSON with keys: language_code, confidence.
Use ISO 639-1 language code where possible.

Text:
{sample}
"""
    ai = _safe_json_loads(router.query_reasoning(prompt), fallback={})
    code = str(ai.get("language_code", "")).strip().lower()
    conf = float(ai.get("confidence", 0.0) or 0.0)
    if not code:
        return heuristic
    return {
        "language_code": code,
        "confidence": max(0.0, min(1.0, conf)),
        "detector": "ai",
    }


def translate_to_english(text: str, source_lang: str) -> dict[str, Any]:
    sample = (text or "")[:MAX_TRANSLATION_CHARS]
    if not sample.strip():
        return {
            "success": True,
            "translated_text": "",
            "confidence": 1.0,
            "method": "empty_passthrough",
            "error": "",
        }

    lang = (source_lang or "unknown").lower()
    if lang in {"en", "eng", "english"}:
        return {
            "success": True,
            "translated_text": text,
            "confidence": 1.0,
            "method": "passthrough_english",
            "error": "",
        }

    prompt = f"""
Translate the following text to English.
Preserve meaning, numbers, bullet order, and line structure.
Return only translated English text.

Source language hint: {lang}

Text:
{sample}
"""
    translated = (router.query_fast(prompt, max_tokens=3500) or "").strip()
    if not translated or translated in {"[]", "{}"}:
        return {
            "success": False,
            "translated_text": "",
            "confidence": 0.0,
            "method": "llm_translation",
            "error": "empty_translation_response",
        }

    residual_devanagari = len(re.findall(r"[\u0900-\u097F]", translated))
    confidence = 0.88 if residual_devanagari == 0 else 0.55
    return {
        "success": True,
        "translated_text": translated,
        "confidence": confidence,
        "method": "llm_translation",
        "error": "",
    }


def ensure_english_text(text: str) -> dict[str, Any]:
    detection = detect_language(text or "")
    source_language = detection.get("language_code", "unknown")
    detection_confidence = float(detection.get("confidence", 0.0) or 0.0)
    detector = detection.get("detector", "unknown")

    if source_language in {"en", "eng", "english"} and detection_confidence >= LANG_DETECTION_CONFIDENCE_MIN:
        return {
            "success": True,
            "source_language": "en",
            "language_detection_confidence": detection_confidence,
            "language_detector": detector,
            "translation_applied": False,
            "translation_status": "not_required",
            "translation_confidence": 1.0,
            "translation_method": "passthrough_english",
            "translation_error": "",
            "translated_text": text or "",
        }

    translation = translate_to_english(text or "", source_language)
    if not translation.get("success"):
        return {
            "success": False,
            "source_language": source_language,
            "language_detection_confidence": detection_confidence,
            "language_detector": detector,
            "translation_applied": True,
            "translation_status": "failed",
            "translation_confidence": float(translation.get("confidence", 0.0) or 0.0),
            "translation_method": translation.get("method", "llm_translation"),
            "translation_error": translation.get("error", "translation_failed"),
            "translated_text": "",
        }

    translation_confidence = float(translation.get("confidence", 0.0) or 0.0)
    if translation_confidence < TRANSLATION_CONFIDENCE_MIN:
        return {
            "success": False,
            "source_language": source_language,
            "language_detection_confidence": detection_confidence,
            "language_detector": detector,
            "translation_applied": True,
            "translation_status": "failed",
            "translation_confidence": translation_confidence,
            "translation_method": translation.get("method", "llm_translation"),
            "translation_error": "translation_low_confidence",
            "translated_text": "",
        }

    return {
        "success": True,
        "source_language": source_language,
        "language_detection_confidence": detection_confidence,
        "language_detector": detector,
        "translation_applied": True,
        "translation_status": "translated",
        "translation_confidence": translation_confidence,
        "translation_method": translation.get("method", "llm_translation"),
        "translation_error": "",
        "translated_text": translation.get("translated_text", ""),
    }

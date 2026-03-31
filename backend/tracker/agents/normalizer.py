"""
Label / Normalize Agent — Translation with back-translation verification.

For a democracy accountability graph, a mistranslated project title can
link the wrong budget line to the wrong promise. This agent:
  1. Forward translates (NE → EN) via GPT-4o
  2. Back-translates (EN → NE) via GPT-4o
  3. Compares original vs back-translated Nepali (character-level similarity)
  4. Flags uncertain translations for human review
"""

import logging
from difflib import SequenceMatcher

from .router import router
from .schemas import TranslatedProject
from tracker.models import TranslationCache

logger = logging.getLogger(__name__)

BATCH_SIZE = 25
BACK_TRANSLATION_THRESHOLD = 0.60  # below this = "uncertain"


def normalize_translate(state: dict) -> dict:
    """
    Translate Nepali → English with back-translation verification.

    Input  state keys: cleaned_projects
    Output state keys: translated_projects
    """
    cleaned = state.get("cleaned_projects", [])
    translated = []
    to_translate = []

    if not cleaned:
        return {"translated_projects": []}

    # Prefetch cache in one query to avoid per-project DB round trips.
    all_titles = list(dict.fromkeys(p["title_ne"] for p in cleaned if p.get("title_ne")))
    cached_rows = TranslationCache.objects.filter(original_text__in=all_titles).only(
        "original_text", "translated_text", "category"
    )
    cache_map = {row.original_text: row for row in cached_rows}

    # Phase 1: resolve from cache (cached = already verified)
    for proj in cleaned:
        title_ne = proj["title_ne"]
        cached = cache_map.get(title_ne)
        if cached:
            proj["title_en"] = cached.translated_text
            proj["translation_confidence"] = 1.0
            proj["back_translated_ne"] = cached.category or ""
            proj["translation_flag"] = "ok"
            # Validate through schema
            try:
                validated = TranslatedProject(**proj)
                translated.append(validated.model_dump())
            except ValueError as e:
                logger.warning("Cached translation failed schema: %s — %s", title_ne[:40], e)
                proj["translation_flag"] = "failed"
                translated.append(proj)
        else:
            to_translate.append(proj)

    logger.info(
        "Translation: %d cached, %d need translation",
        len(translated), len(to_translate),
    )

    # Phase 2: batch-translate + back-translate uncached
    if to_translate:
        unique_titles = list(dict.fromkeys(p["title_ne"] for p in to_translate))
        translation_map = _batch_translate_with_verification(unique_titles)

        for proj in to_translate:
            entry = translation_map.get(proj["title_ne"], {})
            proj["title_en"] = entry.get("title_en", proj["title_ne"])
            proj["translation_confidence"] = entry.get("confidence", 0.0)
            proj["back_translated_ne"] = entry.get("back_translated_ne", "")
            proj["translation_flag"] = entry.get("flag", "failed")
            # Validate through schema
            try:
                validated = TranslatedProject(**proj)
                translated.append(validated.model_dump())
            except ValueError as e:
                logger.warning("Translation failed schema: %s — %s", proj["title_ne"][:40], e)
                proj["translation_flag"] = "failed"
                translated.append(proj)

    uncertain = sum(1 for p in translated if p.get("translation_flag") == "uncertain")
    if uncertain:
        logger.warning(
            "%d translations flagged as UNCERTAIN — will require human review",
            uncertain,
        )

    return {"translated_projects": translated}


# ── Core: Forward + Back Translation ──────────────────────────────────


def _batch_translate_with_verification(titles: list) -> dict:
    """
    Forward translate, then back-translate and verify.
    Returns dict: {title_ne: {title_en, back_translated_ne, confidence, flag}}
    """
    result = {}
    cache_rows = []

    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i : i + BATCH_SIZE]

        # Step 1: Forward NE → EN
        fwd_prompt = _build_translate_prompt(batch, direction="ne_to_en")
        fwd_response = router.query_fast(fwd_prompt, max_tokens=3000)
        fwd_map = _parse_numbered_response(fwd_response, batch)

        # Step 2: Back-translate EN → NE
        en_titles = [fwd_map.get(ne, ne) for ne in batch]
        back_prompt = _build_translate_prompt(en_titles, direction="en_to_ne")
        back_response = router.query_fast(back_prompt, max_tokens=3000)
        back_map = _parse_numbered_response(back_response, en_titles)

        # Step 3: Compare + score
        for title_ne, title_en in fwd_map.items():
            back_ne = back_map.get(title_en, "")
            confidence = _compute_similarity(title_ne, back_ne)

            if confidence >= BACK_TRANSLATION_THRESHOLD:
                flag = "ok"
            else:
                flag = "uncertain"
                logger.warning(
                    "Uncertain translation (%.0f%%): '%s' → '%s' → '%s'",
                    confidence * 100, title_ne[:40], title_en[:40], back_ne[:40],
                )

            result[title_ne] = {
                "title_en": title_en,
                "back_translated_ne": back_ne,
                "confidence": round(confidence, 3),
                "flag": flag,
            }

            cache_rows.append(
                TranslationCache(
                    original_text=title_ne,
                    translated_text=title_en,
                    category=f"back:{back_ne[:200]}",
                )
            )

    if cache_rows:
        # ignore_conflicts preserves correctness under concurrent ingestion workers.
        TranslationCache.objects.bulk_create(
            cache_rows,
            batch_size=500,
            ignore_conflicts=True,
        )

    return result


# ── Private helpers ────────────────────────────────────────────────────


def _build_translate_prompt(items: list, direction: str) -> str:
    if direction == "ne_to_en":
        header = (
            "Translate the following Nepali government project titles to English.\n"
            "Return ONLY a numbered list matching the exact input order.\n"
            "Preserve proper nouns (place names, rivers, districts).\n"
        )
    else:
        header = (
            "Translate the following English government project titles to Nepali.\n"
            "Return ONLY a numbered list matching the exact input order.\n"
            "Preserve proper nouns.\n"
        )

    lines = [header]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {item}")
    return "\n".join(lines)


def _parse_numbered_response(response: str, originals: list) -> dict:
    """Parse numbered LLM response into {original: translation} map."""
    result = {}
    parsed_lines = []
    for line in response.split("\n"):
        line = line.strip()
        if line and "." in line:
            text = line.split(".", 1)[-1].strip()
            if text:
                parsed_lines.append(text)

    for i, original in enumerate(originals):
        if i < len(parsed_lines):
            result[original] = parsed_lines[i]
        else:
            logger.warning("Missing translation at index %d", i)
            result[original] = original
    return result


def _compute_similarity(original_ne: str, back_ne: str) -> float:
    """Character-level similarity between original and back-translated Nepali."""
    if not original_ne or not back_ne:
        return 0.0
    return SequenceMatcher(None, original_ne.strip(), back_ne.strip()).ratio()

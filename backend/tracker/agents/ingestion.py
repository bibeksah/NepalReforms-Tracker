"""
Ingestion Agent — Entry point for the data pipeline.

Reads source documents (Lal Kitab PDFs) and produces cleaned, validated
project records.  Vision fallback is used for garbled PDF pages.
"""

import os
import logging

from .parsers import (
    parse_lal_kitab_tables,
    extract_garbled_pages_as_images,
    get_pdf_page_count,
)
from .cleaner import clean_cid_text, normalize_budget
from .ocr_provider import get_ocr_provider
from .schemas import RawProject, CleanedProject, compute_budget_hash

logger = logging.getLogger(__name__)
MAX_VISION_PAGES = int(os.getenv("TRACKER_MAX_VISION_PAGES", "0"))
VISION_EMPTY_STREAK_STOP = int(os.getenv("TRACKER_VISION_EMPTY_STREAK_STOP", "0"))

# OCR prompt now lives in OCR provider module.
# ── LangGraph node functions ──────────────────────────────────────────


def ingest_source(state: dict) -> dict:
    """
    Extract raw project data from a source document.

    Input  state keys: source_path, source_type, province, fiscal_year
    Output state keys: raw_projects, garbled_pages
    """
    source_path = state.get("source_path")
    source_type = state.get("source_type", "lal_kitab")

    if source_type == "lal_kitab":
        return _ingest_lal_kitab(source_path)

    logger.warning("Unsupported source type: %s", source_type)
    return {"raw_projects": [], "garbled_pages": []}


def clean_and_validate(state: dict) -> dict:
    """
    Clean CID artifacts, normalize budgets, filter noise.

    Every project is validated through Pydantic schemas:
      1. RawProject validates extracted text
      2. CleanedProject validates cleaned + typed data
    Invalid records are logged and dropped — never silently passed.

    Input  state keys: raw_projects
    Output state keys: cleaned_projects
    """
    raw = state.get("raw_projects", [])
    cleaned = []
    rejected = 0

    for proj in raw:
        # Step 1: Validate raw extraction through RawProject schema
        try:
            raw_validated = RawProject(
                title_ne=proj.get("title_ne", ""),
                budget=str(proj.get("budget", "0")),
                page_num=proj.get("page_num", 0),
            )
        except ValueError as e:
            rejected += 1
            logger.warning("RawProject validation failed: %s — %s", proj.get("title_ne", "?")[:40], e)
            continue

        # Step 2: Clean and normalize
        title_cleaned = clean_cid_text(raw_validated.title_ne)
        budget_int = normalize_budget(raw_validated.budget)
        budget_source = proj.get("budget_source", "deterministic")

        # Step 3: Validate cleaned data through CleanedProject schema
        try:
            cleaned_validated = CleanedProject(
                title_ne=title_cleaned,
                budget=budget_int,
                page_num=raw_validated.page_num,
                budget_source=budget_source,
                budget_hash=compute_budget_hash(raw_validated.budget, raw_validated.page_num),
            )
        except ValueError as e:
            rejected += 1
            logger.warning("CleanedProject validation failed: %s — %s", title_cleaned[:40], e)
            continue

        # Convert validated model to dict for pipeline compatibility
        clean_record = cleaned_validated.model_dump()
        clean_record["raw_budget_str"] = raw_validated.budget
        cleaned.append(clean_record)

    logger.info(
        "Cleaned: %d raw → %d valid, %d rejected by schema",
        len(raw), len(cleaned), rejected,
    )
    return {"cleaned_projects": cleaned}


# ── Private helpers ────────────────────────────────────────────────────


def get_lal_kitab_page_count(source_path: str) -> int:
    """Expose page count utility for orchestrator chunk planning."""
    return get_pdf_page_count(source_path)


def recover_lal_kitab_pages_via_vision(
    source_path: str,
    garbled_pages: list[int],
    log_context: str = "",
) -> list[dict]:
    """Expose vision-only recovery for orchestrator merged chunk mode."""
    return _extract_via_vision(source_path, garbled_pages, log_context=log_context)


def _ingest_lal_kitab(
    source_path: str,
    log_context: str = "",
    page_start: int = 1,
    page_end: int | None = None,
    enable_vision: bool = True,
    vision_page_numbers: list[int] | None = None,
) -> dict:
    prefix = f"[{log_context}] " if log_context else ""
    if not source_path:
        source_path = os.path.join(
            "..", "sources", "LalKitab", "Federal", "Redbook_2081_82.pdf"
        )
    source_name = os.path.basename(source_path)
    logger.info(
        "%sExtract start source=%s pages=%s-%s",
        prefix,
        source_name,
        page_start,
        page_end if page_end is not None else "end",
    )

    # Step 1: deterministic extraction
    raw_projects, garbled_pages = parse_lal_kitab_tables(
        source_path,
        page_start=page_start,
        page_end=page_end,
    )
    logger.info(
        "%sParsed %d raw rows, %d garbled pages (pages %s-%s)",
        prefix,
        len(raw_projects),
        len(garbled_pages),
        page_start,
        page_end if page_end is not None else "end",
    )

    # Step 2: vision fallback for garbled pages
    if enable_vision:
        if vision_page_numbers is not None:
            vision_targets = sorted({int(p) for p in vision_page_numbers if int(p) > 0})
        else:
            vision_targets = garbled_pages

        if vision_targets:
            logger.info(
                "%sVision target pages=%d mode=%s",
                prefix,
                len(vision_targets),
                "explicit" if vision_page_numbers is not None else "garbled_only",
            )
            vision_projects = _extract_via_vision(source_path, vision_targets, log_context=log_context)
        else:
            vision_projects = []

        raw_projects.extend(vision_projects)
        logger.info("%sVision recovered %d additional projects", prefix, len(vision_projects))

    logger.info(
        "%sExtract end source=%s raw=%d garbled=%d pages=%s-%s",
        prefix,
        source_name,
        len(raw_projects),
        len(garbled_pages),
        page_start,
        page_end if page_end is not None else "end",
    )

    return {"raw_projects": raw_projects, "garbled_pages": garbled_pages}


def _extract_via_vision(pdf_path: str, page_numbers: list, log_context: str = "") -> list:
    prefix = f"[{log_context}] " if log_context else ""
    ocr_provider = get_ocr_provider()
    logger.info("%sOCR provider=%s", prefix, getattr(ocr_provider, "name", "unknown"))
    if MAX_VISION_PAGES > 0:
        limited_pages = page_numbers[:MAX_VISION_PAGES]
    else:
        limited_pages = list(page_numbers)

    if MAX_VISION_PAGES > 0 and len(page_numbers) > len(limited_pages):
        logger.warning(
            "%sVision page limit reached: processing %d/%d garbled pages",
            prefix,
            len(limited_pages), len(page_numbers),
        )

    page_images = extract_garbled_pages_as_images(pdf_path, limited_pages)
    recovered = []
    empty_streak = 0

    for page_num, image_bytes in page_images:
        logger.info("%sVision extracting garbled page %d...", prefix, page_num)
        try:
            projects = ocr_provider.extract_projects(image_bytes, page_num, log_context=log_context)
        except Exception as exc:
            logger.warning(
                "%sOCR provider failed on page=%d: %s: %s",
                prefix,
                page_num,
                type(exc).__name__,
                exc,
            )
            projects = []
        if not projects:
            empty_streak += 1
            if VISION_EMPTY_STREAK_STOP > 0 and empty_streak >= VISION_EMPTY_STREAK_STOP and not recovered:
                logger.warning(
                    "%sVision returned empty for %d pages; stopping OCR fallback early",
                    prefix,
                    VISION_EMPTY_STREAK_STOP,
                )
                break
        else:
            empty_streak = 0

        for p in projects:
            p["page_num"] = page_num
            p["budget_source"] = p.get("budget_source", "vision")
        recovered.extend(projects)

    return recovered


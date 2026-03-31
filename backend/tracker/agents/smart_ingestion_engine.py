"""
Centralized smart ingestion engine.

Responsibilities:
  - AI-first strategy planning per document
  - source-aware extraction contracts
  - confidence gating (publish vs review hold)
  - direct Neo4j publishing with dedup fingerprints
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pdfplumber
from django.db import close_old_connections
from django.db.models import Sum
from django.utils import timezone

from tracker.models import (
    FailedIngestionItem,
    IngestionDocument,
    IngestionJob,
    ReviewQueueItem,
)
from .ingestion import _ingest_lal_kitab, clean_and_validate, get_lal_kitab_page_count
from .language_preprocessor import ensure_english_text
from .normalizer import normalize_translate
from .router import router
from .schemas import ManifestoCommitment
from .smart_neo4j_publisher import (
    compute_project_fingerprint,
    ensure_smart_constraints,
    publish_project_records_batch,
)
from .validators import validate_project_batch

logger = logging.getLogger(__name__)
PIPELINE_MAX_RETRIES = max(0, int(os.getenv("TRACKER_PIPELINE_MAX_RETRIES", "2")))
PIPELINE_RETRY_BASE_SEC = float(os.getenv("TRACKER_PIPELINE_RETRY_BASE_SEC", "0.8"))
PIPELINE_RETRY_MAX_SEC = float(os.getenv("TRACKER_PIPELINE_RETRY_MAX_SEC", "12"))
NEO4J_BATCH_SIZE = max(1, int(os.getenv("TRACKER_NEO4J_BATCH_SIZE", "200")))


class LanguagePreprocessError(RuntimeError):
    def __init__(self, reason: str, metadata: dict[str, Any]):
        super().__init__(reason)
        self.reason = reason
        self.metadata = metadata


def _merge_document_extra_metadata(document: IngestionDocument, patch: dict[str, Any]) -> None:
    current = document.extra_metadata or {}
    merged = dict(current)
    merged.update(patch)
    document.extra_metadata = merged
    try:
        document.save(update_fields=["extra_metadata", "updated_at"])
    except TypeError:
        document.save(update_fields=["extra_metadata"])
    except AttributeError:
        # Unit tests may pass a lightweight stand-in object without .save()
        return


def infer_scope_from_path(source_path: str) -> tuple[str, str]:
    parts = [part.lower() for part in Path(source_path).parts]
    if "federal" in parts:
        return "federal", ""
    if "provincial" in parts:
        return "provincial", Path(source_path).parent.name
    return "unknown", ""


def infer_fiscal_year(filename: str) -> str:
    match = re.search(r"(\d{4})[_-](\d{2})", filename)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return "unknown"


def detect_source_type(source_path: str) -> str:
    lower = source_path.lower()
    if "lalkitab" in lower or "redbook" in lower:
        return "lal_kitab"
    if "manifesto" in lower:
        return "manifesto"
    if "citizen" in lower:
        return "citizen"
    if "media" in lower or "news" in lower:
        return "media"
    return "other"


def hash_file(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return ""
    h = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


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


def _is_transient_error(exc: Exception) -> bool:
    text = str(exc).lower()
    transient_markers = [
        "timeout",
        "temporarily unavailable",
        "connection reset",
        "connection aborted",
        "connection refused",
        "rate limit",
        "too many requests",
        "service unavailable",
        "429",
        "502",
        "503",
        "504",
    ]
    return any(marker in text for marker in transient_markers)


def _run_with_retry(operation: str, fn):
    last_exc = None
    attempts = PIPELINE_MAX_RETRIES + 1
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except LanguagePreprocessError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts or not _is_transient_error(exc):
                raise
            delay = min(PIPELINE_RETRY_MAX_SEC, PIPELINE_RETRY_BASE_SEC * (2 ** (attempt - 1)))
            delay = min(PIPELINE_RETRY_MAX_SEC, delay + random.uniform(0.0, 0.25))
            logger.warning(
                "Transient failure during %s attempt=%d/%d delay=%.2fs error=%s: %s",
                operation,
                attempt,
                attempts,
                delay,
                type(exc).__name__,
                exc,
            )
            time.sleep(delay)
    raise last_exc  # pragma: no cover


def plan_document_strategy(document: IngestionDocument) -> dict[str, Any]:
    """
    AI-first document strategy planner with deterministic fallback.
    """
    source_path = document.source_path
    page_count = 0
    sample_raw = 0
    sample_garbled = 0
    if document.source_type == "lal_kitab":
        page_count = get_lal_kitab_page_count(source_path)
        try:
            sample_state = _ingest_lal_kitab(
                source_path,
                log_context=f"planner|{Path(source_path).name}",
                page_start=1,
                page_end=min(5, page_count if page_count > 0 else 5),
                enable_vision=False,
            )
            sample_raw = len(sample_state.get("raw_projects", []))
            sample_garbled = len(sample_state.get("garbled_pages", []))
        except Exception:
            sample_raw = 0
            sample_garbled = 0

    prompt = f"""
You are a document ingestion planner for Nepal civic accountability graph.
Return STRICT JSON only with keys:
strategy, confidence, requires_ocr, requires_vision, fields_to_extract, reason.

strategy must be one of: deterministic, ocr, vision, hybrid
source_type: {document.source_type}
source_tier: {document.source_tier}
source_document: {document.source_document}
page_count: {page_count}
sample_raw_rows: {sample_raw}
sample_garbled_pages: {sample_garbled}
goal: maximize recall while preserving auditability.
"""
    raw_response = router.query_reasoning(prompt)
    ai_plan = _safe_json_loads(
        raw_response,
        fallback={},
    )

    if ai_plan:
        strategy = ai_plan.get("strategy", "")
        if strategy in {"deterministic", "ocr", "vision", "hybrid"}:
            return {
                "strategy": strategy,
                "confidence": float(ai_plan.get("confidence", 0.7)),
                "requires_ocr": bool(ai_plan.get("requires_ocr", strategy in {"ocr", "hybrid"})),
                "requires_vision": bool(ai_plan.get("requires_vision", strategy in {"vision", "hybrid"})),
                "fields_to_extract": ai_plan.get("fields_to_extract", []),
                "reason": ai_plan.get("reason", "AI planner selected strategy."),
                "estimated_pages": page_count,
            }

    # Deterministic fallback planning.
    sample_pages = max(1, min(5, page_count or 5))
    garbled_ratio = sample_garbled / sample_pages
    rows_per_sample_page = sample_raw / sample_pages
    if document.source_type == "lal_kitab":
        if sample_raw == 0 or rows_per_sample_page < 1.0 or garbled_ratio >= 0.4:
            strategy = "vision"
        elif rows_per_sample_page < 3.0 or (page_count > 80 and garbled_ratio > 0.1):
            strategy = "hybrid"
        else:
            strategy = "deterministic"
        return {
            "strategy": strategy,
            "confidence": 0.62,
            "requires_ocr": strategy in {"ocr", "hybrid"},
            "requires_vision": strategy in {"vision", "hybrid"},
            "fields_to_extract": ["title_ne", "title_en", "budget", "fiscal_year", "scope", "page_num"],
            "reason": "Fallback heuristic planner selected strategy.",
            "estimated_pages": page_count,
        }

    # Non LalKitab documents default to hybrid text/OCR.
    return {
        "strategy": "hybrid",
        "confidence": 0.55,
        "requires_ocr": True,
        "requires_vision": False,
        "fields_to_extract": ["entity_text", "claims", "evidence_refs"],
        "reason": "Default non-budget planner strategy.",
        "estimated_pages": page_count,
    }


def _extract_lal_kitab(document: IngestionDocument, plan: dict[str, Any]) -> list[dict[str, Any]]:
    strategy = plan.get("strategy", "deterministic")
    enable_vision = strategy in {"vision", "hybrid", "ocr"}
    vision_page_numbers: list[int] | None = None
    if strategy == "vision":
        total_pages = get_lal_kitab_page_count(document.source_path)
        if total_pages > 0:
            vision_page_numbers = list(range(1, total_pages + 1))

    raw_state = _ingest_lal_kitab(
        document.source_path,
        log_context=(
            f"smart|{document.source_type}|{document.gov_level or 'unknown'}"
            f"|{document.province_name or '-'}|{document.source_document}"
        ),
        enable_vision=enable_vision,
        vision_page_numbers=vision_page_numbers,
    )
    cleaned_state = clean_and_validate(raw_state)
    cleaned_projects = cleaned_state.get("cleaned_projects", [])
    valid_projects, flagged_projects = validate_project_batch(cleaned_projects)
    translated_state = normalize_translate({"cleaned_projects": valid_projects + flagged_projects})
    translated = translated_state.get("translated_projects", [])

    gov_level = document.gov_level or infer_scope_from_path(document.source_path)[0]
    province = document.province_name or infer_scope_from_path(document.source_path)[1]
    fiscal_year = document.fiscal_year or infer_fiscal_year(document.source_document)

    output = []
    for proj in translated:
        risk_flags: list[str] = []
        translation_flag = proj.get("translation_flag", "ok")
        if translation_flag in {"failed", "uncertain"}:
            risk_flags.append("translation_uncertain")
        if proj.get("budget_anomaly_flag"):
            risk_flags.append("budget_anomaly")
        if proj.get("budget_source") == "vision":
            risk_flags.append("vision_budget")

        confidence = 0.90
        if proj.get("budget_source") == "vision":
            confidence -= 0.12
        if translation_flag == "uncertain":
            confidence -= 0.25
        elif translation_flag == "failed":
            confidence -= 0.50
        if proj.get("budget_anomaly_flag"):
            confidence -= 0.20
        confidence = max(0.05, min(0.99, confidence))

        record = {
            "entity_type": "Project",
            "source_type": "lal_kitab",
            "title_ne": proj.get("title_ne", ""),
            "title_en": proj.get("title_en", ""),
            "budget": int(proj.get("budget", 0)),
            "budget_source": proj.get("budget_source", "deterministic"),
            "budget_hash": proj.get("budget_hash", ""),
            "page_num": int(proj.get("page_num", 0)),
            "translation_confidence": float(proj.get("translation_confidence", 1.0)),
            "translation_flag": proj.get("translation_flag", "ok"),
            "fiscal_year": fiscal_year,
            "gov_level": gov_level,
            "province_name": province,
            "source_document": document.source_document,
            "source_path": document.source_path,
            "source_hash": document.source_hash,
            "confidence": confidence,
            "risk_flags": risk_flags,
            "raw_payload": proj,
        }
        record["fingerprint"] = compute_project_fingerprint(record)
        output.append(record)
    return output


def _extract_manifesto_like(document: IngestionDocument) -> list[dict[str, Any]]:
    text = ""
    source_path = Path(document.source_path)
    if source_path.suffix.lower() == ".pdf":
        try:
            with pdfplumber.open(str(source_path)) as pdf:
                chunks = []
                for page in pdf.pages[: min(40, len(pdf.pages))]:
                    chunks.append(page.extract_text() or "")
                text = "\n".join(chunks)
        except Exception:
            text = ""
    else:
        try:
            text = source_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""

    if not text.strip():
        return []

    preprocessed = ensure_english_text(text)
    translation_meta = {
        "source_language": preprocessed.get("source_language", "unknown"),
        "language_detection_confidence": float(preprocessed.get("language_detection_confidence", 0.0) or 0.0),
        "language_detector": preprocessed.get("language_detector", "unknown"),
        "translation_applied": bool(preprocessed.get("translation_applied", False)),
        "translation_status": preprocessed.get("translation_status", "failed"),
        "translation_confidence": float(preprocessed.get("translation_confidence", 0.0) or 0.0),
        "translation_method": preprocessed.get("translation_method", ""),
        "translation_error": preprocessed.get("translation_error", ""),
    }
    _merge_document_extra_metadata(document, translation_meta)
    logger.info(
        json.dumps(
            {
                "event": "language_preprocessed",
                "document_id": str(document.id),
                "source_document": document.source_document,
                **translation_meta,
            }
        )
    )

    if not preprocessed.get("success"):
        raise LanguagePreprocessError(
            "translation_failed_pre_ingestion",
            {
                **translation_meta,
                "text_preview": text[:700],
            },
        )

    normalized_text = preprocessed.get("translated_text", "") or text

    prompt = f"""
Extract manifesto-style commitments as JSON array with keys:
  promise_text, category, actor, timeline, confidence
Return strict JSON only.
Source excerpt:
{normalized_text[:18000]}
"""
    response = router.query_reasoning(prompt)
    parsed = _safe_json_loads(response, fallback={"items": []})
    items = parsed if isinstance(parsed, list) else parsed.get("items", [])
    if not isinstance(items, list):
        items = []

    output = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            validated = ManifestoCommitment(**item)
        except Exception:
            continue
        promise_text = validated.promise_text.strip()
        confidence = float(validated.confidence)
        output.append(
            {
                "entity_type": "ManifestoPromise",
                "source_type": "manifesto",
                "promise_text": promise_text,
                "category": validated.category.strip(),
                "actor": validated.actor.strip(),
                "timeline": validated.timeline.strip(),
                "confidence": max(0.05, min(0.99, confidence)),
                "risk_flags": [] if confidence >= 0.7 else ["low_confidence"],
                "source_language": translation_meta.get("source_language", "unknown"),
                "translation_applied": translation_meta.get("translation_applied", False),
                "translation_confidence": translation_meta.get("translation_confidence", 0.0),
                "translation_method": translation_meta.get("translation_method", ""),
                "source_document": document.source_document,
                "source_path": document.source_path,
                "source_hash": document.source_hash,
                "raw_payload": item,
            }
        )
    return output


def extract_records(document: IngestionDocument, plan: dict[str, Any]) -> list[dict[str, Any]]:
    if document.source_type == "lal_kitab":
        return _extract_lal_kitab(document, plan)
    if document.source_type in {"manifesto", "media", "citizen", "other"}:
        return _extract_manifesto_like(document)
    return []


def _hold_for_review(
    *,
    job: IngestionJob,
    document: IngestionDocument,
    record: dict[str, Any],
    reason: str,
) -> None:
    ReviewQueueItem.objects.create(
        **_review_item_kwargs(job=job, document=document, record=record, reason=reason)
    )


def _review_item_kwargs(
    *,
    job: IngestionJob,
    document: IngestionDocument,
    record: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "job": job,
        "document": document,
        "status": "pending_review",
        "reason": reason,
        "risk_level": "high" if record.get("confidence", 0.0) < 0.45 else "medium",
        "confidence": float(record.get("confidence", 0.0)),
        "entity_type": record.get("entity_type", "Unknown"),
        "record_key": f"{document.source_document}:{record.get('page_num', 0)}",
        "fingerprint": record.get("fingerprint", "") or record.get("source_hash", ""),
        "proposed_payload": record,
        "provenance": {
            "source_path": document.source_path,
            "source_document": document.source_document,
            "source_hash": document.source_hash,
            "page_num": record.get("page_num"),
        },
    }


def _hold_many_for_review(
    *,
    job: IngestionJob,
    document: IngestionDocument,
    review_records: list[tuple[dict[str, Any], str]],
) -> int:
    if not review_records:
        return 0
    rows = [
        ReviewQueueItem(**_review_item_kwargs(job=job, document=document, record=record, reason=reason))
        for record, reason in review_records
    ]
    ReviewQueueItem.objects.bulk_create(rows, batch_size=500)
    return len(rows)


def _record_failure(document: IngestionDocument, reason: str, detail: str, stage: str = "smart_ingestion") -> None:
    FailedIngestionItem.objects.create(
        source_type=document.source_type,
        source_path=document.source_path,
        source_document=document.source_document,
        source_hash=document.source_hash,
        stage=stage,
        failure_reason=reason,
        failure_detail=detail[:4000],
        status="pending_retry",
        extra_metadata={"job_id": str(document.job_id), "document_id": str(document.id)},
    )


def _process_document(document_id: str, publish_threshold: float) -> dict[str, Any]:
    close_old_connections()
    document = IngestionDocument.objects.select_related("job").get(id=document_id)
    job = document.job
    now = timezone.now()

    document.status = "planning"
    document.attempt_count += 1
    document.last_attempt_at = now
    if not document.source_document:
        document.source_document = Path(document.source_path).name
    if not document.source_hash:
        document.source_hash = hash_file(document.source_path)
    if not document.source_type:
        document.source_type = detect_source_type(document.source_path)
    if not document.gov_level or not document.province_name:
        gov, province = infer_scope_from_path(document.source_path)
        document.gov_level = document.gov_level or gov
        document.province_name = document.province_name or province
    if not document.fiscal_year:
        document.fiscal_year = infer_fiscal_year(document.source_document)
    document.save()
    scope = f"{document.gov_level or 'unknown'}"
    if document.province_name:
        scope = f"{scope}/{document.province_name}"
    logger.info(
        json.dumps(
            {
                "event": "document_started",
                "job_id": str(job.id),
                "document_id": str(document.id),
                "source_type": document.source_type,
                "scope": scope,
                "source_document": document.source_document,
                "source_path": document.source_path,
            }
        )
    )

    if not Path(document.source_path).exists():
        detail = "Source file not found."
        document.status = "failed"
        document.error_detail = detail
        document.save(update_fields=["status", "error_detail", "updated_at"])
        _record_failure(document, "source_file_missing", detail)
        return {"published": 0, "held": 0, "failed": True}

    plan = plan_document_strategy(document)
    document.plan_strategy = plan.get("strategy", "")
    document.plan_confidence = float(plan.get("confidence", 0.0))
    document.plan_reason = plan.get("reason", "")
    document.requires_ocr = bool(plan.get("requires_ocr", False))
    document.requires_vision = bool(plan.get("requires_vision", False))
    document.estimated_pages = int(plan.get("estimated_pages", 0))
    document.payload_schema = "budget_project_v1" if document.source_type == "lal_kitab" else "evidence_claim_v1"
    document.status = "extracting"
    document.save()
    logger.info(
        json.dumps(
            {
                "event": "document_planned",
                "job_id": str(job.id),
                "document_id": str(document.id),
                "source_document": document.source_document,
                "strategy": document.plan_strategy,
                "requires_ocr": document.requires_ocr,
                "requires_vision": document.requires_vision,
                "estimated_pages": document.estimated_pages,
                "plan_confidence": document.plan_confidence,
            }
        )
    )

    try:
        records = _run_with_retry(
            operation="extract_records",
            fn=lambda: extract_records(document, plan),
        )
    except LanguagePreprocessError as exc:
        detail = exc.metadata.get("translation_error", "") or exc.reason
        _hold_for_review(
            job=job,
            document=document,
            record={
                "entity_type": "Document",
                "confidence": 0.0,
                "risk_flags": ["translation_failed_pre_ingestion"],
                "source_document": document.source_document,
                "source_path": document.source_path,
                "source_hash": document.source_hash,
                "raw_payload": exc.metadata,
            },
            reason=exc.reason,
        )
        _record_failure(
            document,
            reason=exc.reason,
            detail=detail,
            stage="language_preprocess",
        )
        document.extracted_count = 0
        document.published_count = 0
        document.held_count = max(document.held_count, 1)
        document.status = "review_hold"
        document.error_detail = f"{exc.reason}: {detail}"
        document.save(
            update_fields=[
                "extracted_count",
                "published_count",
                "held_count",
                "status",
                "error_detail",
                "updated_at",
            ]
        )
        logger.warning(
            json.dumps(
                {
                    "event": "language_preprocess_failed",
                    "job_id": str(job.id),
                    "document_id": str(document.id),
                    "source_document": document.source_document,
                    "reason": exc.reason,
                    "translation_error": detail,
                }
            )
        )
        return {"published": 0, "held": 1, "failed": False}

    document.extracted_count = len(records)
    document.status = "publishing"
    document.save(update_fields=["extracted_count", "status", "updated_at"])
    logger.info(
        json.dumps(
            {
                "event": "document_extracted",
                "job_id": str(job.id),
                "document_id": str(document.id),
                "source_document": document.source_document,
                "extracted_count": len(records),
            }
        )
    )

    ensure_smart_constraints()

    published = 0
    held = 0
    to_publish: list[dict[str, Any]] = []
    to_hold: list[tuple[dict[str, Any], str]] = []
    for record in records:
        confidence = float(record.get("confidence", 0.0))
        risk_flags = record.get("risk_flags", [])
        high_risk_flags = {"translation_uncertain", "budget_anomaly"}
        high_risk = any(flag in high_risk_flags for flag in risk_flags)
        should_hold = confidence < publish_threshold or high_risk
        if should_hold:
            hold_reason = "low_confidence_or_risk_flags"
            if risk_flags:
                hold_reason = f"risk:{','.join(risk_flags)}"
            to_hold.append((record, hold_reason))
            continue

        if record.get("entity_type") == "Project":
            to_publish.append(record)
        else:
            # Manifesto/media/citizen entities default to review hold in V1.
            to_hold.append((record, "unsupported_direct_entity_publish_v1"))

    if to_publish:
        batch_result = _run_with_retry(
            operation="neo4j_batch_publish",
            fn=lambda: publish_project_records_batch(to_publish, batch_size=NEO4J_BATCH_SIZE),
        )
        published_fingerprints = set(batch_result.get("published_fingerprints", []))
        published += int(batch_result.get("ok_count", 0))
        for record in to_publish:
            fingerprint = record.get("fingerprint", "") or compute_project_fingerprint(record)
            if fingerprint not in published_fingerprints:
                to_hold.append((record, "neo4j_publish_failed"))

    held += _hold_many_for_review(job=job, document=document, review_records=to_hold)

    if records:
        budget_sources: dict[str, int] = {}
        for record in records:
            source_key = str(record.get("budget_source", "unknown"))
            budget_sources[source_key] = budget_sources.get(source_key, 0) + 1
        _merge_document_extra_metadata(
            document,
            {
                "record_budget_sources": budget_sources,
                "pipeline_retries_config": {
                    "max_retries": PIPELINE_MAX_RETRIES,
                    "retry_base_sec": PIPELINE_RETRY_BASE_SEC,
                    "retry_max_sec": PIPELINE_RETRY_MAX_SEC,
                },
            },
        )

    document.published_count = published
    document.held_count = held
    if published > 0 and held == 0:
        document.status = "published"
    elif published > 0 and held > 0:
        document.status = "review_hold"
    elif published == 0 and held > 0:
        document.status = "review_hold"
    else:
        document.status = "failed"
        _record_failure(
            document,
            reason="no_records_published",
            detail="No records could be published and no review items were created.",
        )
    document.save()
    logger.info(
        json.dumps(
            {
                "event": "document_finished",
                "job_id": str(job.id),
                "document_id": str(document.id),
                "source_document": document.source_document,
                "status": document.status,
                "published_count": published,
                "held_count": held,
            }
        )
    )
    return {"published": published, "held": held, "failed": document.status == "failed"}


def _adaptive_worker_count(total_docs: int, requested: int, adaptive: bool) -> int:
    requested = max(1, int(requested))
    if not adaptive:
        return max(1, min(total_docs, requested))
    if total_docs <= 2:
        return 1
    if total_docs <= 6:
        return min(2, requested)
    if total_docs <= 12:
        return min(3, requested)
    return min(4, requested)


def refresh_job_rollup(job: IngestionJob) -> IngestionJob:
    docs = job.documents.all()
    source_count = docs.count()
    processed_count = docs.exclude(status="queued").count()
    published_count = docs.aggregate(total=Sum("published_count")).get("total") or 0
    held_count = docs.aggregate(total=Sum("held_count")).get("total") or 0
    failed_count = docs.filter(status="failed").count()

    job.source_count = source_count
    job.processed_count = processed_count
    job.published_count = int(published_count)
    job.held_count = int(held_count)
    job.failed_count = failed_count

    has_pending = docs.filter(status__in=["queued", "planning", "extracting", "publishing"]).exists()
    if has_pending:
        job.status = "running"
    elif failed_count > 0:
        job.status = "failed"
    elif held_count > 0:
        job.status = "review_hold"
    elif published_count > 0:
        job.status = "completed"
    else:
        job.status = "dead_letter"

    if not has_pending:
        job.completed_at = timezone.now()
    job.save()
    return job


def run_job(job: IngestionJob, *, max_workers: int = 4, adaptive: bool = True, publish_threshold: float = 0.75) -> dict:
    if job.started_at is None:
        job.started_at = timezone.now()
    job.status = "running"
    job.save(update_fields=["started_at", "status"])

    docs = list(job.documents.filter(status="queued").values_list("id", flat=True))
    if not docs:
        job = refresh_job_rollup(job)
        return {
            "job_id": str(job.id),
            "status": job.status,
            "processed": 0,
            "published_count": job.published_count,
            "held_count": job.held_count,
            "failed_count": job.failed_count,
        }

    workers = _adaptive_worker_count(len(docs), max_workers, adaptive)
    logger.info(
        json.dumps(
            {
                "event": "job_started",
                "job_id": str(job.id),
                "job_name": job.name,
                "queued_documents": len(docs),
                "workers_used": workers,
                "adaptive": adaptive,
                "publish_threshold": publish_threshold,
            }
        )
    )
    results = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="smart-ingest") as executor:
        future_map = {
            executor.submit(_process_document, str(doc_id), publish_threshold): doc_id
            for doc_id in docs
        }
        for future in as_completed(future_map):
            doc_id = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                logger.exception("Smart ingestion doc failed: %s", exc)
                document = IngestionDocument.objects.get(id=doc_id)
                document.status = "failed"
                document.error_detail = f"{type(exc).__name__}: {exc}"
                document.save(update_fields=["status", "error_detail", "updated_at"])
                _record_failure(
                    document,
                    reason="unhandled_exception",
                    detail=f"{type(exc).__name__}: {exc}",
                )
                results.append({"published": 0, "held": 0, "failed": True})

    job = refresh_job_rollup(job)
    summary = {
        "job_id": str(job.id),
        "status": job.status,
        "workers_used": workers,
        "processed": len(results),
        "published_count": job.published_count,
        "held_count": job.held_count,
        "failed_count": job.failed_count,
    }
    logger.info(json.dumps({"event": "job_finished", **summary}))
    return summary

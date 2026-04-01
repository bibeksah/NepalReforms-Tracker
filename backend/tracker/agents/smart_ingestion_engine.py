"""Centralized smart ingestion engine with source-native deterministic flows."""

from __future__ import annotations

import csv
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

from tracker.models import FailedIngestionItem, IngestionDocument, IngestionJob, ReviewQueueItem
from .ingestion import _ingest_lal_kitab, clean_and_validate, get_lal_kitab_page_count
from .language_preprocessor import ensure_english_text
from .normalizer import normalize_translate
from .router import router
from .schemas import (
    AgendaItemRecord,
    AgendaVersionRecord,
    AlignmentAssessmentRecord,
    ManifestoCommitment,
    ManifestoDocumentRecord,
    PoliticalPromiseRecord,
    ReviewedAlignmentAssessmentBundle,
    ReviewedOCRPromiseBundle,
    stable_id,
)
from .smart_neo4j_publisher import (
    compute_project_fingerprint,
    ensure_smart_constraints,
    publish_record,
    publish_records_batch,
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
        return


def infer_scope_from_path(source_path: str) -> tuple[str, str]:
    parts = [part.lower() for part in Path(source_path).parts]
    if "federal" in parts:
        return "federal", ""
    if "provincial" in parts or "province" in parts:
        return "provincial", Path(source_path).parent.name
    return "unknown", ""


def infer_fiscal_year(filename: str) -> str:
    match = re.search(r"(\d{4})[_-](\d{2})", filename or "")
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return "unknown"


def detect_source_type(source_path: str) -> str:
    lower = source_path.lower()
    suffix = Path(source_path).suffix.lower()
    manifesto_markers = [
        "manifesto",
        "वाचा",
        "वाचा पत्र",
        "वाचापत्र",
        "बाचा",
        "बाचा पत्र",
        "बाचापत्र",
        "bacha patra",
        "bacha_patra",
        "vacha patra",
        "vacha_patra",
    ]
    if "lalkitab" in lower or "redbook" in lower:
        return "lal_kitab"
    if any(marker in lower for marker in manifesto_markers) or ("rsp" in lower and suffix == ".csv"):
        return "manifesto"
    if "agenda" in lower and suffix == ".json":
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
    return (text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()


def _safe_json_loads(text: str, fallback: Any):
    try:
        return json.loads(_strip_json_fence(text))
    except Exception:
        return fallback


def _is_transient_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in [
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
    )


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
            logger.warning("Transient failure during %s attempt=%d/%d delay=%.2fs error=%s", operation, attempt, attempts, delay, exc)
            time.sleep(delay)
    raise last_exc


def _source_subtype(document: IngestionDocument | Any) -> str:
    source_path = getattr(document, "source_path", "")
    source_document = getattr(document, "source_document", "")
    lower = f"{source_path} {source_document}".lower()
    suffix = Path(source_path or source_document).suffix.lower()
    source_type = getattr(document, "source_type", "")
    if "agenda" in lower and suffix == ".json":
        return "nepalreforms_agenda_json"
    if "rsp" in lower and suffix == ".csv":
        return "rsp_manifesto_csv"
    if suffix == ".pdf" and source_type == "manifesto":
        if any(marker in lower for marker in [
            "????",
            "???? ????",
            "bacha patra",
            "bacha_patra",
            "vacha patra",
            "vacha_patra",
            "वाचा पत्र",
            "वाचापत्र",
            "बाचा पत्र",
            "बाचापत्र",
        ]):
            return "rsp_bacha_patra_pdf"
        return "manifesto_pdf"
    return getattr(document, "source_type", "other")


def plan_document_strategy(document: IngestionDocument) -> dict[str, Any]:
    subtype = _source_subtype(document)
    if subtype in {"nepalreforms_agenda_json", "rsp_manifesto_csv"}:
        return {
            "strategy": "deterministic",
            "confidence": 0.98,
            "requires_ocr": False,
            "requires_vision": False,
            "fields_to_extract": ["structured_records"],
            "reason": f"Deterministic structured ingestion for {subtype}.",
            "estimated_pages": 0,
        }
    if subtype == "rsp_bacha_patra_pdf":
        return {
            "strategy": "hybrid",
            "confidence": 0.45,
            "requires_ocr": True,
            "requires_vision": False,
            "fields_to_extract": ["manifesto_document"],
            "reason": "RSP bacha patra is a source-native scanned manifesto PDF; ingest document provenance deterministically and hold for OCR/review.",
            "estimated_pages": 0,
        }
    if subtype == "manifesto_pdf":
        return {
            "strategy": "hybrid",
            "confidence": 0.72,
            "requires_ocr": True,
            "requires_vision": False,
            "fields_to_extract": ["manifesto_commitments"],
            "reason": "Manifesto PDF requires text extraction + LLM parsing.",
            "estimated_pages": 0,
        }

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
source_subtype: {subtype}
source_tier: {document.source_tier}
source_document: {document.source_document}
page_count: {page_count}
sample_raw_rows: {sample_raw}
sample_garbled_pages: {sample_garbled}
goal: maximize recall while preserving auditability.
"""
    ai_plan = _safe_json_loads(router.query_reasoning(prompt), fallback={})
    if isinstance(ai_plan, dict):
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

    sample_pages = max(1, min(5, page_count or 5))
    garbled_ratio = sample_garbled / sample_pages
    rows_per_sample_page = sample_raw / sample_pages
    if document.source_type == "lal_kitab":
        strategy = "deterministic"
        if sample_raw == 0 or rows_per_sample_page < 1.0 or garbled_ratio >= 0.4:
            strategy = "vision"
        elif rows_per_sample_page < 3.0 or (page_count > 80 and garbled_ratio > 0.1):
            strategy = "hybrid"
        return {
            "strategy": strategy,
            "confidence": 0.62,
            "requires_ocr": strategy in {"ocr", "hybrid"},
            "requires_vision": strategy in {"vision", "hybrid"},
            "fields_to_extract": ["title_ne", "title_en", "budget", "fiscal_year", "scope", "page_num"],
            "reason": "Fallback heuristic planner selected strategy.",
            "estimated_pages": page_count,
        }
    return {
        "strategy": "hybrid",
        "confidence": 0.55,
        "requires_ocr": True,
        "requires_vision": False,
        "fields_to_extract": ["entity_text", "claims", "evidence_refs"],
        "reason": "Default non-budget planner strategy.",
        "estimated_pages": page_count,
    }


def _manifesto_document_record(document: IngestionDocument | Any, *, owner_type: str, owner_name: str, language: str = "en") -> dict[str, Any]:
    subtype = _source_subtype(document)
    manifesto_document_id = stable_id("manifesto_document", owner_type, owner_name, getattr(document, "source_hash", ""), subtype)
    validated = ManifestoDocumentRecord(
        manifesto_document_id=manifesto_document_id,
        owner_type=owner_type,
        owner_name=owner_name,
        name=getattr(document, "source_document", Path(getattr(document, "source_path", "document")).name),
        language=language,
        source_reference=getattr(document, "source_path", ""),
    )
    props = validated.model_dump()
    return {
        "entity_type": "ManifestoDocument",
        "record_identity": validated.manifesto_document_id,
        "confidence": 0.99,
        "risk_flags": [],
        "graph_payload": {
            "id": validated.manifesto_document_id,
            "key": "manifestoDocumentId",
            "properties": props,
        },
        "graph_relations": [],
        "raw_payload": props,
        "source_type": getattr(document, "source_type", "manifesto"),
        "source_subtype": subtype,
        "source_document": getattr(document, "source_document", ""),
        "source_path": getattr(document, "source_path", ""),
        "source_hash": getattr(document, "source_hash", ""),
    }


def _make_related_node(*, relation_type: str, target_entity_type: str, target_key: str, target_id: str, target_properties: dict[str, Any], relationship_properties: dict[str, Any] | None = None, require_existing_target: bool = False) -> dict[str, Any]:
    return {
        "relation_type": relation_type,
        "target_entity_type": target_entity_type,
        "target_key": target_key,
        "target_id": target_id,
        "target_properties": target_properties,
        "relationship_properties": relationship_properties or {},
        "require_existing_target": require_existing_target,
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
        record["record_identity"] = record["fingerprint"]
        output.append(record)
    return output

def _extract_nepalreforms_agenda_json(document: IngestionDocument | Any) -> list[dict[str, Any]]:
    raw = _safe_json_loads(Path(document.source_path).read_text(encoding="utf-8"), fallback={})
    owner_name = raw.get("owner_name") or raw.get("organization") or "NepalReforms"
    language = raw.get("language") or "en"
    version_name = raw.get("version") or raw.get("name") or Path(document.source_path).stem
    effective_from = raw.get("effective_from") or raw.get("published_at") or ""
    items = raw.get("items") or raw.get("agenda_items") or []
    records: list[dict[str, Any]] = []

    manifesto_record = _manifesto_document_record(document, owner_type="civic_platform", owner_name=owner_name, language=language)
    records.append(manifesto_record)

    agenda_version_id = stable_id("agenda_version", manifesto_record["record_identity"], version_name, effective_from)
    version = AgendaVersionRecord(
        agenda_version_id=agenda_version_id,
        name=version_name,
        baseline_count=len(items),
        effective_from=effective_from,
        status=raw.get("status") or "baseline",
        source_reference=document.source_path,
    )
    version_props = version.model_dump()
    records.append(
        {
            "entity_type": "AgendaVersion",
            "record_identity": version.agenda_version_id,
            "confidence": 0.99,
            "risk_flags": [],
            "graph_payload": {"id": version.agenda_version_id, "key": "agendaVersionId", "properties": version_props},
            "graph_relations": [
                _make_related_node(
                    relation_type="DOCUMENTED_IN",
                    target_entity_type="ManifestoDocument",
                    target_key="manifestoDocumentId",
                    target_id=manifesto_record["record_identity"],
                    target_properties=manifesto_record["graph_payload"]["properties"],
                )
            ],
            "raw_payload": version_props,
            "source_type": "manifesto",
            "source_subtype": "nepalreforms_agenda_json",
            "source_document": document.source_document,
            "source_path": document.source_path,
            "source_hash": document.source_hash,
        }
    )

    for idx, item in enumerate(items, start=1):
        source_item_id = str(item.get("source_item_id") or item.get("id") or idx)
        title = item.get("title") or item.get("name") or f"Agenda Item {idx}"
        agenda_item_id = stable_id("agenda_item", agenda_version_id, source_item_id, title)
        validated = AgendaItemRecord(
            agenda_item_id=agenda_item_id,
            source_item_id=source_item_id,
            title=title,
            description=item.get("description") or item.get("summary") or "",
            language=item.get("language") or language,
            active=bool(item.get("active", True)),
            source_reference=document.source_path,
            category=item.get("category") or "",
            priority=item.get("priority") or "",
            timeline=item.get("timeline") or "",
            legal_foundation=item.get("legal_foundation") or "",
            performance_targets=list(item.get("performance_targets") or []),
            problem=dict(item.get("problem") or {}),
            solution=dict(item.get("solution") or {}),
            implementation=dict(item.get("implementation") or {}),
            real_world_evidence=dict(item.get("real_world_evidence") or {}),
        )
        props = validated.model_dump()
        relations = [
            _make_related_node(
                relation_type="PART_OF_VERSION",
                target_entity_type="AgendaVersion",
                target_key="agendaVersionId",
                target_id=agenda_version_id,
                target_properties=version_props,
            )
        ]
        if validated.category:
            category_id = stable_id("policy_category", validated.category)
            relations.append(_make_related_node(
                relation_type="IN_CATEGORY",
                target_entity_type="PolicyCategory",
                target_key="policyCategoryId",
                target_id=category_id,
                target_properties={"policyCategoryId": category_id, "name": validated.category},
            ))
        if validated.timeline:
            timeline_id = stable_id("timeline_target", validated.timeline)
            relations.append(_make_related_node(
                relation_type="HAS_TIMELINE_TARGET",
                target_entity_type="TimelineTarget",
                target_key="timelineTargetId",
                target_id=timeline_id,
                target_properties={"timelineTargetId": timeline_id, "name": validated.timeline},
            ))
        records.append(
            {
                "entity_type": "AgendaItem",
                "record_identity": validated.agenda_item_id,
                "confidence": 0.99,
                "risk_flags": [],
                "graph_payload": {"id": validated.agenda_item_id, "key": "agendaItemId", "properties": props},
                "graph_relations": relations,
                "raw_payload": props,
                "source_type": "manifesto",
                "source_subtype": "nepalreforms_agenda_json",
                "source_document": document.source_document,
                "source_path": document.source_path,
                "source_hash": document.source_hash,
            }
        )
    return records


def _extract_rsp_manifesto_csv(document: IngestionDocument | Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    manifesto_record = _manifesto_document_record(document, owner_type="political_party", owner_name="Rastriya Swatantra Party", language="en")
    records.append(manifesto_record)
    with Path(document.source_path).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for idx, row in enumerate(reader, start=1):
            title = (row.get("Specific_Promise") or "").strip()
            if not title:
                continue
            category = (row.get("Category") or "").strip()
            timeline = (row.get("Target_Deadline") or "").strip()
            responsible_entity = (row.get("Responsible_Entity") or "").strip()
            promise_id = stable_id("political_promise", manifesto_record["record_identity"], idx, title)
            validated = PoliticalPromiseRecord(
                political_promise_id=promise_id,
                title=title,
                summary=title,
                language="en",
                promise_scope="national",
                source_reference=document.source_path,
                category=category,
                timeline=timeline,
                responsible_entity=responsible_entity,
            )
            props = validated.model_dump()
            relations = [
                _make_related_node(
                    relation_type="PROMISED_IN",
                    target_entity_type="ManifestoDocument",
                    target_key="manifestoDocumentId",
                    target_id=manifesto_record["record_identity"],
                    target_properties=manifesto_record["graph_payload"]["properties"],
                )
            ]
            if category:
                category_id = stable_id("policy_category", category)
                relations.append(_make_related_node(
                    relation_type="IN_CATEGORY",
                    target_entity_type="PolicyCategory",
                    target_key="policyCategoryId",
                    target_id=category_id,
                    target_properties={"policyCategoryId": category_id, "name": category},
                ))
            if timeline:
                timeline_id = stable_id("timeline_target", timeline)
                relations.append(_make_related_node(
                    relation_type="HAS_TIMELINE_TARGET",
                    target_entity_type="TimelineTarget",
                    target_key="timelineTargetId",
                    target_id=timeline_id,
                    target_properties={"timelineTargetId": timeline_id, "name": timeline},
                ))
            if responsible_entity:
                entity_id = stable_id("responsible_entity", responsible_entity)
                relations.append(_make_related_node(
                    relation_type="ASSIGNED_TO",
                    target_entity_type="ResponsibleEntity",
                    target_key="responsibleEntityId",
                    target_id=entity_id,
                    target_properties={"responsibleEntityId": entity_id, "name": responsible_entity},
                ))
            records.append(
                {
                    "entity_type": "PoliticalPromise",
                    "record_identity": validated.political_promise_id,
                    "confidence": 0.99,
                    "risk_flags": [],
                    "graph_payload": {"id": validated.political_promise_id, "key": "politicalPromiseId", "properties": props},
                    "graph_relations": relations,
                    "raw_payload": props,
                    "source_type": "manifesto",
                    "source_subtype": "rsp_manifesto_csv",
                    "source_document": document.source_document,
                    "source_path": document.source_path,
                    "source_hash": document.source_hash,
                }
            )
    return records

def _extract_reviewed_rsp_bacha_patra_structured_promises(document: IngestionDocument | Any) -> list[dict[str, Any]]:
    metadata = getattr(document, "extra_metadata", None) or {}
    reviewed_bundle = metadata.get("reviewed_structured_promise_bundle")
    if not isinstance(reviewed_bundle, dict):
        return []

    validated_bundle = ReviewedOCRPromiseBundle(**reviewed_bundle)
    if validated_bundle.source_subtype != "rsp_bacha_patra_pdf":
        return []
    if validated_bundle.structured_promises_status != "reviewed_approved":
        return []
    if validated_bundle.ocr_text_review_status != "approved":
        return []

    records: list[dict[str, Any]] = []
    for idx, item in enumerate(validated_bundle.reviewed_structured_promises, start=1):
        if item.reviewer_status != "approved":
            continue
        if item.placeholder:
            continue
        if item.extraction_confidence < 0.70:
            continue

        promise_id = stable_id(
            "political_promise",
            validated_bundle.manifesto_document_id,
            item.source_page,
            item.title,
        )
        promise = PoliticalPromiseRecord(
            political_promise_id=promise_id,
            title=item.title,
            summary=item.summary.strip() or item.title,
            language=item.language.strip() or "ne",
            promise_scope="national",
            source_reference=validated_bundle.source_reference,
            category=item.category.strip(),
            timeline=item.timeline.strip(),
            responsible_entity=item.responsible_entity.strip(),
        )
        props = promise.model_dump()
        props.update({
            "source_subtype": "rsp_bacha_patra_pdf",
            "source_page": item.source_page,
            "source_excerpt": item.source_excerpt.strip(),
            "ocr_artifact_reference": validated_bundle.ocr_artifact_reference,
            "derived_from_document_id": validated_bundle.manifesto_document_id,
            "extraction_mode": validated_bundle.extraction_mode,
        })

        relations = [
            _make_related_node(
                relation_type="PROMISED_IN",
                target_entity_type="ManifestoDocument",
                target_key="manifestoDocumentId",
                target_id=validated_bundle.manifesto_document_id,
                target_properties={"manifestoDocumentId": validated_bundle.manifesto_document_id},
                relationship_properties={
                    "source_page": item.source_page,
                    "source_excerpt": item.source_excerpt.strip(),
                    "ocr_artifact_reference": validated_bundle.ocr_artifact_reference,
                    "derivation_method": "reviewed_ocr_structured_extraction",
                },
            )
        ]
        if promise.category:
            category_id = stable_id("policy_category", promise.category)
            relations.append(_make_related_node(
                relation_type="IN_CATEGORY",
                target_entity_type="PolicyCategory",
                target_key="policyCategoryId",
                target_id=category_id,
                target_properties={"policyCategoryId": category_id, "name": promise.category},
            ))
        if promise.timeline:
            timeline_id = stable_id("timeline_target", promise.timeline)
            relations.append(_make_related_node(
                relation_type="HAS_TIMELINE_TARGET",
                target_entity_type="TimelineTarget",
                target_key="timelineTargetId",
                target_id=timeline_id,
                target_properties={"timelineTargetId": timeline_id, "name": promise.timeline},
            ))
        if promise.responsible_entity:
            entity_id = stable_id("responsible_entity", promise.responsible_entity)
            relations.append(_make_related_node(
                relation_type="ASSIGNED_TO",
                target_entity_type="ResponsibleEntity",
                target_key="responsibleEntityId",
                target_id=entity_id,
                target_properties={"responsibleEntityId": entity_id, "name": promise.responsible_entity},
            ))

        raw_payload = item.model_dump()
        raw_payload.update({
            "source_subtype": "rsp_bacha_patra_pdf",
            "manifesto_document_id": validated_bundle.manifesto_document_id,
            "ocr_artifact_reference": validated_bundle.ocr_artifact_reference,
            "extraction_mode": validated_bundle.extraction_mode,
        })
        records.append({
            "entity_type": "PoliticalPromise",
            "record_identity": promise.political_promise_id,
            "confidence": float(item.extraction_confidence),
            "risk_flags": [],
            "graph_payload": {"id": promise.political_promise_id, "key": "politicalPromiseId", "properties": props},
            "graph_relations": relations,
            "raw_payload": raw_payload,
            "review_context": {
                "workflow": {
                    "workflow_kind": "rsp_bacha_patra_ocr_review",
                    "review_status": "structured_promises_reviewed",
                    "ocr_text_review_status": validated_bundle.ocr_text_review_status,
                    "structured_promises_status": validated_bundle.structured_promises_status,
                    "manifesto_document_id": validated_bundle.manifesto_document_id,
                },
            },
            "source_type": "manifesto",
            "source_subtype": "rsp_bacha_patra_pdf",
            "source_document": document.source_document,
            "source_path": document.source_path,
            "source_hash": document.source_hash,
        })
    return records


def _extract_reviewed_alignment_assessments(document: IngestionDocument | Any) -> list[dict[str, Any]]:
    metadata = getattr(document, "extra_metadata", None) or {}
    reviewed_bundle = metadata.get("reviewed_alignment_assessment_bundle")
    if not isinstance(reviewed_bundle, dict):
        return []

    validated_bundle = ReviewedAlignmentAssessmentBundle(**reviewed_bundle)
    if validated_bundle.source_subtype != "agenda_promise_alignment_review":
        return []
    if validated_bundle.reviewed_alignment_status != "reviewed_approved":
        return []

    records: list[dict[str, Any]] = []
    for item in validated_bundle.reviewed_alignment_assessments:
        if item.reviewer_status != "approved":
            continue
        if item.placeholder:
            continue
        if item.confidence < 0.70:
            continue
        if item.approval_state != "approved":
            continue

        assessment_id = stable_id(
            "alignment_assessment",
            item.agenda_item_id,
            item.political_promise_id,
            item.relation_type,
            item.notes,
        )
        assessment = AlignmentAssessmentRecord(
            alignment_assessment_id=assessment_id,
            relation_type=item.relation_type,
            confidence=float(item.confidence),
            approval_state=item.approval_state,
            notes=item.notes.strip(),
            agenda_item_id=item.agenda_item_id.strip(),
            political_promise_id=item.political_promise_id.strip(),
        )
        props = assessment.model_dump()
        props.update({
            "source_subtype": validated_bundle.source_subtype,
            "extraction_mode": validated_bundle.extraction_mode,
        })
        raw_payload = item.model_dump()
        raw_payload.update({
            "source_subtype": validated_bundle.source_subtype,
            "extraction_mode": validated_bundle.extraction_mode,
        })
        relations = [
            _make_related_node(
                relation_type="ASSESSES_AGENDA_ITEM",
                target_entity_type="AgendaItem",
                target_key="agendaItemId",
                target_id=assessment.agenda_item_id,
                target_properties={"agendaItemId": assessment.agenda_item_id},
                relationship_properties={
                    "relation_type": assessment.relation_type,
                    "confidence": assessment.confidence,
                    "approval_state": assessment.approval_state,
                },
                require_existing_target=True,
            ),
            _make_related_node(
                relation_type="ASSESSES_POLITICAL_PROMISE",
                target_entity_type="PoliticalPromise",
                target_key="politicalPromiseId",
                target_id=assessment.political_promise_id,
                target_properties={"politicalPromiseId": assessment.political_promise_id},
                relationship_properties={
                    "relation_type": assessment.relation_type,
                    "confidence": assessment.confidence,
                    "approval_state": assessment.approval_state,
                },
                require_existing_target=True,
            ),
        ]
        records.append({
            "entity_type": "AlignmentAssessment",
            "record_identity": assessment.alignment_assessment_id,
            "confidence": float(item.confidence),
            "risk_flags": [],
            "graph_payload": {"id": assessment.alignment_assessment_id, "key": "alignmentAssessmentId", "properties": props},
            "graph_relations": relations,
            "raw_payload": raw_payload,
            "review_context": {
                "workflow": {
                    "workflow_kind": "agenda_promise_alignment_review",
                    "reviewed_alignment_status": validated_bundle.reviewed_alignment_status,
                },
            },
            "source_type": getattr(document, "source_type", "manifesto"),
            "source_subtype": validated_bundle.source_subtype,
            "source_document": getattr(document, "source_document", ""),
            "source_path": getattr(document, "source_path", ""),
            "source_hash": getattr(document, "source_hash", ""),
        })
    return records


def _extract_rsp_bacha_patra_pdf(document: IngestionDocument | Any) -> list[dict[str, Any]]:
    page_count = 0
    source_path = Path(document.source_path)
    try:
        import fitz  # type: ignore
        with fitz.open(str(source_path)) as pdf:
            page_count = pdf.page_count
            embedded_text_chars = sum(len(pdf.load_page(i).get_text("text") or "") for i in range(min(3, pdf.page_count)))
    except Exception:
        embedded_text_chars = 0
    record = _manifesto_document_record(document, owner_type="political_party", owner_name="Rastriya Swatantra Party", language="ne")
    record["confidence"] = 0.40 if embedded_text_chars == 0 else 0.55
    record["risk_flags"] = ["source_native_scanned_manifesto", "ocr_review_required"]
    record["source_subtype"] = "rsp_bacha_patra_pdf"
    ocr_workflow = {
        "workflow_kind": "rsp_bacha_patra_ocr_review",
        "review_status": "ocr_pending_review",
        "ocr_status": "not_run",
        "ocr_artifact_available": False,
        "structured_promises_status": "not_extracted",
        "review_required_for_structured_promises": True,
        "publishable_record_kind": "document_provenance_only",
        "notes": (
            "This record captures source provenance only. "
            "Any OCR-derived structured promises must be introduced later as separate reviewed records."
        ),
    }
    raw_payload = dict(record.get("raw_payload") or {})
    raw_payload.update({
        "document_kind": "bacha_patra",
        "page_count": page_count,
        "embedded_text_chars_first_pages": embedded_text_chars,
        "extraction_mode": "document_provenance_only",
        "ocr_workflow": ocr_workflow,
    })
    record["raw_payload"] = raw_payload
    graph_payload = dict(record.get("graph_payload") or {})
    graph_properties = dict(graph_payload.get("properties") or {})
    graph_properties.update({
        "document_kind": "bacha_patra",
        "page_count": page_count,
        "source_subtype": "rsp_bacha_patra_pdf",
    })
    graph_payload["properties"] = graph_properties
    record["graph_payload"] = graph_payload
    record["review_context"] = {
        "workflow": ocr_workflow,
        "suggested_reviewer_actions": [
            "confirm document provenance",
            "attach OCR artifact when available",
            "create separately reviewed PoliticalPromise records from OCR output",
        ],
    }
    return [record]


def _extract_manifesto_pdf(document: IngestionDocument | Any) -> list[dict[str, Any]]:
    text = ""
    source_path = Path(document.source_path)
    if source_path.suffix.lower() == ".pdf":
        try:
            with pdfplumber.open(str(source_path)) as pdf:
                text = "\n".join((page.extract_text() or "") for page in pdf.pages[: min(40, len(pdf.pages))])
        except Exception:
            text = ""
    else:
        text = source_path.read_text(encoding="utf-8", errors="ignore")
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
    if not preprocessed.get("success"):
        raise LanguagePreprocessError("translation_failed_pre_ingestion", {**translation_meta, "text_preview": text[:700]})
    normalized_text = preprocessed.get("translated_text", "") or text
    parsed = _safe_json_loads(
        router.query_reasoning(
            f"Extract manifesto-style commitments as JSON array with keys: promise_text, category, actor, timeline, confidence. Return strict JSON only.\nSource excerpt:\n{normalized_text[:18000]}"
        ),
        fallback={"items": []},
    )
    items = parsed if isinstance(parsed, list) else parsed.get("items", [])
    if not isinstance(items, list):
        items = []
    records = []
    manifesto_record = _manifesto_document_record(document, owner_type="political_party", owner_name=Path(document.source_document).stem, language="en")
    records.append(manifesto_record)
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        try:
            validated = ManifestoCommitment(**item)
        except Exception:
            continue
        promise_id = stable_id("political_promise", manifesto_record["record_identity"], idx, validated.promise_text)
        promise = PoliticalPromiseRecord(
            political_promise_id=promise_id,
            title=validated.promise_text,
            summary=validated.promise_text,
            language="en",
            promise_scope="national",
            source_reference=document.source_path,
            category=validated.category.strip(),
            timeline=validated.timeline.strip(),
            responsible_entity=validated.actor.strip(),
        )
        risk_flags = [] if validated.confidence >= 0.7 else ["low_confidence"]
        records.append(
            {
                "entity_type": "PoliticalPromise",
                "record_identity": promise.political_promise_id,
                "confidence": max(0.05, min(0.99, float(validated.confidence))),
                "risk_flags": risk_flags,
                "graph_payload": {"id": promise.political_promise_id, "key": "politicalPromiseId", "properties": promise.model_dump()},
                "graph_relations": [
                    _make_related_node(
                        relation_type="PROMISED_IN",
                        target_entity_type="ManifestoDocument",
                        target_key="manifestoDocumentId",
                        target_id=manifesto_record["record_identity"],
                        target_properties=manifesto_record["graph_payload"]["properties"],
                    )
                ],
                "raw_payload": item,
                "source_type": "manifesto",
                "source_subtype": "manifesto_pdf",
                "source_document": document.source_document,
                "source_path": document.source_path,
                "source_hash": document.source_hash,
            }
        )
    return records


def extract_records(document: IngestionDocument, plan: dict[str, Any]) -> list[dict[str, Any]]:
    subtype = _source_subtype(document)
    if document.source_type == "lal_kitab":
        records = _extract_lal_kitab(document, plan)
    elif subtype == "nepalreforms_agenda_json":
        records = _extract_nepalreforms_agenda_json(document)
    elif subtype == "rsp_manifesto_csv":
        records = _extract_rsp_manifesto_csv(document)
    elif subtype == "rsp_bacha_patra_pdf":
        reviewed_records = _extract_reviewed_rsp_bacha_patra_structured_promises(document)
        records = reviewed_records if reviewed_records else _extract_rsp_bacha_patra_pdf(document)
    elif subtype == "manifesto_pdf":
        records = _extract_manifesto_pdf(document)
    elif document.source_type in {"manifesto", "media", "citizen", "other"}:
        records = _extract_manifesto_pdf(document)
    else:
        records = []

    reviewed_alignment_records = _extract_reviewed_alignment_assessments(document)
    if reviewed_alignment_records:
        records.extend(reviewed_alignment_records)
    return records


def _hold_for_review(*, job: IngestionJob, document: IngestionDocument, record: dict[str, Any], reason: str) -> None:
    ReviewQueueItem.objects.create(**_review_item_kwargs(job=job, document=document, record=record, reason=reason))


def _review_item_kwargs(*, job: IngestionJob, document: IngestionDocument, record: dict[str, Any], reason: str) -> dict[str, Any]:
    record_identity = record.get("record_identity") or record.get("fingerprint") or record.get("source_hash", "")
    return {
        "job": job,
        "document": document,
        "status": "pending_review",
        "reason": reason,
        "risk_level": "high" if record.get("confidence", 0.0) < 0.45 or any(flag in {"translation_uncertain", "budget_anomaly"} for flag in record.get("risk_flags", [])) else "medium",
        "confidence": float(record.get("confidence", 0.0)),
        "entity_type": record.get("entity_type", "Unknown"),
        "record_key": str(record_identity or f"{document.source_document}:{record.get('page_num', 0)}"),
        "fingerprint": str(record_identity or ""),
        "proposed_payload": record,
        "provenance": {
            "source_path": document.source_path,
            "source_document": document.source_document,
            "source_hash": document.source_hash,
            "page_num": record.get("page_num"),
            "source_subtype": _source_subtype(document),
            "review_context": record.get("review_context") or {},
        },
    }


def _hold_many_for_review(*, job: IngestionJob, document: IngestionDocument, review_records: list[tuple[dict[str, Any], str]]) -> int:
    if not review_records:
        return 0
    rows = [ReviewQueueItem(**_review_item_kwargs(job=job, document=document, record=record, reason=reason)) for record, reason in review_records]
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

    if not Path(document.source_path).exists():
        detail = "Source file not found."
        document.status = "failed"
        document.error_detail = detail
        document.save(update_fields=["status", "error_detail", "updated_at"])
        _record_failure(document, "source_file_missing", detail)
        return {"published": 0, "held": 0, "failed": True}

    plan = plan_document_strategy(document)
    subtype = _source_subtype(document)
    schema_map = {
        "lal_kitab": "budget_project_v1",
        "nepalreforms_agenda_json": "nepalreforms_agenda_v1",
        "rsp_manifesto_csv": "rsp_manifesto_csv_v1",
        "rsp_bacha_patra_pdf": "rsp_bacha_patra_v1",
        "manifesto_pdf": "manifesto_like_v1",
    }
    document.plan_strategy = plan.get("strategy", "")
    document.plan_confidence = float(plan.get("confidence", 0.0))
    document.plan_reason = plan.get("reason", "")
    document.requires_ocr = bool(plan.get("requires_ocr", False))
    document.requires_vision = bool(plan.get("requires_vision", False))
    document.estimated_pages = int(plan.get("estimated_pages", 0))
    document.payload_schema = schema_map.get(subtype, "manifesto_like_v1")
    document.status = "extracting"
    document.save()

    try:
        records = _run_with_retry("extract_records", lambda: extract_records(document, plan))
    except LanguagePreprocessError as exc:
        detail = exc.metadata.get("translation_error", "") or exc.reason
        _hold_for_review(job=job, document=document, record={"entity_type": "Document", "confidence": 0.0, "risk_flags": ["translation_failed_pre_ingestion"], "record_identity": document.source_hash or str(document.id), "source_document": document.source_document, "source_path": document.source_path, "source_hash": document.source_hash, "raw_payload": exc.metadata}, reason=exc.reason)
        _record_failure(document, reason=exc.reason, detail=detail, stage="language_preprocess")
        document.extracted_count = 0
        document.published_count = 0
        document.held_count = max(document.held_count, 1)
        document.status = "review_hold"
        document.error_detail = f"{exc.reason}: {detail}"
        document.save(update_fields=["extracted_count", "published_count", "held_count", "status", "error_detail", "updated_at"])
        return {"published": 0, "held": 1, "failed": False}

    document.extracted_count = len(records)
    alignment_record_count = sum(1 for record in records if record.get("entity_type") == "AlignmentAssessment")
    document.status = "publishing"
    document.save(update_fields=["extracted_count", "status", "updated_at"])
    ensure_smart_constraints()

    published = 0
    held = 0
    to_hold: list[tuple[dict[str, Any], str]] = []
    project_records: list[dict[str, Any]] = []
    direct_records: list[dict[str, Any]] = []
    for record in records:
        confidence = float(record.get("confidence", 0.0))
        risk_flags = record.get("risk_flags", [])
        high_risk = any(flag in {"translation_uncertain", "budget_anomaly"} for flag in risk_flags)
        if confidence < publish_threshold or high_risk:
            reason = f"risk:{','.join(risk_flags)}" if risk_flags else "low_confidence_or_risk_flags"
            to_hold.append((record, reason))
            continue
        if record.get("entity_type") == "Project":
            project_records.append(record)
        else:
            direct_records.append(record)

    if project_records:
        batch_result = _run_with_retry("neo4j_batch_publish", lambda: publish_records_batch(project_records, batch_size=NEO4J_BATCH_SIZE))
        published_ids = set(batch_result.get("published_ids", []) or batch_result.get("published_fingerprints", []))
        published += int(batch_result.get("ok_count", 0))
        for record in project_records:
            identity = record.get("record_identity") or record.get("fingerprint") or compute_project_fingerprint(record)
            if identity not in published_ids:
                to_hold.append((record, "neo4j_publish_failed"))

    for record in direct_records:
        try:
            result = _run_with_retry("neo4j_publish", lambda rec=record: publish_record(rec))
            if result.get("ok", True):
                published += 1
            else:
                to_hold.append((record, "neo4j_publish_failed"))
        except Exception:
            to_hold.append((record, "neo4j_publish_failed"))

    held += _hold_many_for_review(job=job, document=document, review_records=to_hold)
    if records:
        metadata_patch = {
            "source_subtype": subtype,
            "pipeline_retries_config": {
                "max_retries": PIPELINE_MAX_RETRIES,
                "retry_base_sec": PIPELINE_RETRY_BASE_SEC,
                "retry_max_sec": PIPELINE_RETRY_MAX_SEC,
            },
        }
        if subtype == "rsp_bacha_patra_pdf":
            reviewed_bundle = (document.extra_metadata or {}).get("reviewed_structured_promise_bundle") or {}
            has_reviewed_bundle = isinstance(reviewed_bundle, dict) and bool(reviewed_bundle.get("reviewed_structured_promises"))
            metadata_patch["ocr_workflow"] = {
                "workflow_kind": "rsp_bacha_patra_ocr_review",
                "review_status": "structured_promises_reviewed" if has_reviewed_bundle and held == 0 and published > 0 else ("ocr_pending_review" if held > 0 else "provenance_published"),
                "ocr_status": "reviewed_artifact_supplied" if has_reviewed_bundle else "not_run",
                "structured_promises_status": "reviewed_approved" if has_reviewed_bundle and held == 0 and published > 0 else "not_extracted",
                "document_record_published": published > 0 and not has_reviewed_bundle,
                "review_queue_count": held,
            }
        reviewed_alignment_bundle = (document.extra_metadata or {}).get("reviewed_alignment_assessment_bundle") or {}
        has_reviewed_alignment_bundle = isinstance(reviewed_alignment_bundle, dict) and bool(reviewed_alignment_bundle.get("reviewed_alignment_assessments"))
        if has_reviewed_alignment_bundle or alignment_record_count:
            metadata_patch["alignment_workflow"] = {
                "workflow_kind": "agenda_promise_alignment_review",
                "reviewed_alignment_status": "reviewed_approved" if has_reviewed_alignment_bundle and alignment_record_count > 0 and held == 0 else "pending_review",
                "alignment_records_extracted": alignment_record_count,
                "review_queue_count": held,
            }
        _merge_document_extra_metadata(document, metadata_patch)
    document.published_count = published
    document.held_count = held
    if published > 0 and held == 0:
        document.status = "published"
    elif held > 0:
        document.status = "review_hold"
    else:
        document.status = "failed"
        _record_failure(document, reason="no_records_published", detail="No records could be published and no review items were created.")
    document.save()
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
        return {"job_id": str(job.id), "status": job.status, "processed": 0, "published_count": job.published_count, "held_count": job.held_count, "failed_count": job.failed_count}
    workers = _adaptive_worker_count(len(docs), max_workers, adaptive)
    results = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="smart-ingest") as executor:
        future_map = {executor.submit(_process_document, str(doc_id), publish_threshold): doc_id for doc_id in docs}
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
                _record_failure(document, reason="unhandled_exception", detail=f"{type(exc).__name__}: {exc}")
                results.append({"published": 0, "held": 0, "failed": True})
    job = refresh_job_rollup(job)
    return {"job_id": str(job.id), "status": job.status, "workers_used": workers, "processed": len(results), "published_count": job.published_count, "held_count": job.held_count, "failed_count": job.failed_count}

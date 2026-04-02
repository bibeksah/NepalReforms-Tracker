"""Phase 1 source-native ingestion contracts and lightweight validation schemas."""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, Field, field_validator

MAX_BUDGET_NPR = 5_000_000_000_000
MIN_TITLE_LENGTH = 5


class RawProject(BaseModel):
    title_ne: str
    budget: str
    page_num: int = 0

    @field_validator("title_ne")
    @classmethod
    def title_ne_not_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title_ne cannot be empty")
        return value


class CleanedProject(BaseModel):
    title_ne: str = Field(min_length=MIN_TITLE_LENGTH)
    budget: int = Field(ge=1, le=MAX_BUDGET_NPR)
    page_num: int = 0
    budget_source: str = Field(default="deterministic")
    budget_hash: str = Field(default="")

    @field_validator("title_ne")
    @classmethod
    def not_numeric_only(cls, value: str) -> str:
        if value.strip().isdigit():
            raise ValueError(f"Title is numeric only (likely page number): {value}")
        return value


class TranslatedProject(CleanedProject):
    title_en: str = Field(min_length=3)
    translation_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    back_translated_ne: str = Field(default="")
    translation_flag: str = Field(default="ok")


class ManifestoDocumentRecord(BaseModel):
    manifesto_document_id: str
    owner_type: str
    owner_name: str
    name: str
    language: str = "en"
    source_reference: str
    published_at: str = ""


class AgendaVersionRecord(BaseModel):
    agenda_version_id: str
    name: str
    baseline_count: int
    effective_from: str
    status: str = "baseline"
    source_reference: str


class AgendaItemRecord(BaseModel):
    agenda_item_id: str
    source_item_id: str
    title: str = Field(min_length=3)
    description: str | None = None
    language: str = "en"
    active: bool | None = None
    source_reference: str
    category: str | None = None
    priority: str | None = None
    timeline: str | None = None
    legal_foundation: str | None = None
    performance_targets: list[str] | None = None
    problem: dict[str, Any] | None = None
    solution: dict[str, Any] | None = None
    implementation: dict[str, Any] | None = None
    real_world_evidence: dict[str, Any] | None = None


class PoliticalPromiseRecord(BaseModel):
    political_promise_id: str
    title: str = Field(min_length=10)
    summary: str = ""
    language: str = "en"
    promise_scope: str = "national"
    source_reference: str
    category: str = ""
    timeline: str = ""
    responsible_entity: str = ""


class PoliticalPartyRecord(BaseModel):
    political_party_id: str
    canonical_name: str = Field(min_length=2)
    short_name: str = ""
    country: str = "Nepal"
    scope: str = "national"
    party_type: str = "political_party"
    source_reference: str
    election_symbol: str = ""
    description: str = ""


class ReviewedOCRPoliticalPromiseInput(BaseModel):
    title: str = Field(min_length=10)
    summary: str = ""
    category: str = ""
    timeline: str = ""
    responsible_entity: str = ""
    language: str = "ne"
    source_page: int = Field(ge=1)
    source_excerpt: str = Field(min_length=5)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reviewer_status: str = "approved"
    placeholder: bool = False


class ReviewedOCRPromiseBundle(BaseModel):
    manifesto_document_id: str = Field(min_length=3)
    source_reference: str = Field(min_length=3)
    source_subtype: str = "rsp_bacha_patra_pdf"
    extraction_mode: str = "reviewed_structured_promises"
    ocr_artifact_reference: str = ""
    ocr_text_review_status: str = "approved"
    structured_promises_status: str = "reviewed_approved"
    review_required_for_structured_promises: bool = True
    reviewed_structured_promises: list[ReviewedOCRPoliticalPromiseInput] = Field(default_factory=list)


class ReviewedAlignmentAssessmentInput(BaseModel):
    agenda_item_id: str = Field(min_length=3)
    political_promise_id: str = Field(min_length=3)
    relation_type: str = "PARTIALLY_ALIGNS"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    approval_state: str = "approved"
    notes: str = ""
    reviewer_status: str = "approved"
    placeholder: bool = False


class ReviewedAlignmentAssessmentBundle(BaseModel):
    source_subtype: str = "agenda_promise_alignment_review"
    extraction_mode: str = "reviewed_alignment_assessments"
    reviewed_alignment_status: str = "reviewed_approved"
    review_required_for_alignment: bool = True
    reviewed_alignment_assessments: list[ReviewedAlignmentAssessmentInput] = Field(default_factory=list)


class AlignmentAssessmentRecord(BaseModel):
    alignment_assessment_id: str
    relation_type: str = "NO_DIRECT_MATCH"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    approval_state: str = "pending_review"
    notes: str = ""
    agenda_item_id: str = ""
    political_promise_id: str = ""


class ManifestoCommitment(BaseModel):
    promise_text: str = Field(min_length=10)
    category: str = Field(default="")
    actor: str = Field(default="")
    timeline: str = Field(default="")
    confidence: float = Field(default=0.55, ge=0.0, le=1.0)


def stable_id(prefix: str, *parts: Any) -> str:
    payload = "|".join(str(part or "").strip().lower() for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def canonical_fiscal_year_id(label: str) -> str:
    normalized = " ".join((label or "").strip().split()) or "unknown"
    return stable_id("fiscal_year", normalized)


def compute_budget_hash(raw_budget_str: str, page_num: int) -> str:
    payload = f"{raw_budget_str.strip()}|page:{page_num}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


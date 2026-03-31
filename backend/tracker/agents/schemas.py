"""Pydantic schemas for smart-ingestion pipeline boundaries."""

import hashlib

from pydantic import BaseModel, Field, field_validator

# Budget safety bounds.
MAX_BUDGET_NPR = 500_000_000_000
MIN_TITLE_LENGTH = 5


class RawProject(BaseModel):
    """Validated output from PDF parser: raw extracted row."""

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
    """Validated output after cleaning and budget normalization."""

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

    @field_validator("budget")
    @classmethod
    def budget_sanity(cls, value: int) -> int:
        if value > MAX_BUDGET_NPR:
            raise ValueError(
                f"Budget {value:,} exceeds max sanity bound of {MAX_BUDGET_NPR:,} NPR"
            )
        return value


class TranslatedProject(CleanedProject):
    """Validated output after translation."""

    title_en: str = Field(min_length=3)
    translation_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    back_translated_ne: str = Field(default="")
    translation_flag: str = Field(default="ok")


class ManifestoCommitment(BaseModel):
    """Validated non-budget commitment extraction payload."""

    promise_text: str = Field(min_length=10)
    category: str = Field(default="")
    actor: str = Field(default="")
    timeline: str = Field(default="")
    confidence: float = Field(default=0.55, ge=0.0, le=1.0)


def compute_budget_hash(raw_budget_str: str, page_num: int) -> str:
    """SHA-256 hash of raw budget cell plus page context."""

    payload = f"{raw_budget_str.strip()}|page:{page_num}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

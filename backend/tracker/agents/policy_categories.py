"""Deterministic policy-category classification for agenda/promise records."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class PolicyCategoryClassification:
    slug: str
    display_name: str
    source: str  # normalized | inferred | fallback


POLICY_CATEGORY_CHOICES: tuple[tuple[str, str], ...] = (
    ("education", "Education"),
    ("finance", "Finance"),
    ("governance", "Governance"),
    ("health", "Health"),
    ("infrastructure", "Infrastructure"),
    ("agriculture", "Agriculture"),
    ("employment", "Employment"),
    ("social_protection", "Social Protection"),
    ("environment", "Environment"),
    ("technology", "Technology"),
    ("justice", "Justice"),
    ("federalism_local_governance", "Federalism & Local Governance"),
    ("energy", "Energy"),
    ("transport", "Transport"),
    ("tourism", "Tourism"),
    ("housing_urban_development", "Housing & Urban Development"),
    ("security", "Security"),
    ("other", "Other"),
)

_DISPLAY_BY_SLUG = {slug: display for slug, display in POLICY_CATEGORY_CHOICES}
_CATEGORY_ORDER = [slug for slug, _display in POLICY_CATEGORY_CHOICES]
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _normalize_text(value: str) -> str:
    normalized = (value or "").strip().lower()
    normalized = normalized.replace("&", " and ")
    normalized = normalized.replace("/", " ")
    normalized = normalized.replace("_", " ")
    normalized = normalized.replace("-", " ")
    normalized = _NON_ALNUM_RE.sub(" ", normalized)
    return " ".join(normalized.split())


_ALIASES_BY_SLUG: dict[str, tuple[str, ...]] = {
    "education": (
        "education",
        "school",
        "schools",
        "higher education",
        "learning",
    ),
    "finance": (
        "finance",
        "fiscal",
        "budget",
        "economy",
        "economic policy",
        "public finance",
    ),
    "governance": (
        "governance",
        "good governance",
        "public administration",
        "anti corruption",
        "transparency",
        "accountability",
    ),
    "health": (
        "health",
        "healthcare",
        "public health",
        "medical",
    ),
    "infrastructure": (
        "infrastructure",
        "public infrastructure",
        "basic infrastructure",
    ),
    "agriculture": (
        "agriculture",
        "farming",
        "farmers",
        "agri",
        "agro",
    ),
    "employment": (
        "employment",
        "jobs",
        "job creation",
        "labor",
        "labour",
        "livelihood",
    ),
    "social_protection": (
        "social protection",
        "social welfare",
        "welfare",
        "social security",
    ),
    "environment": (
        "environment",
        "environmental",
        "climate",
        "conservation",
    ),
    "technology": (
        "technology",
        "digital",
        "ict",
        "innovation",
    ),
    "justice": (
        "justice",
        "judiciary",
        "legal",
        "law and justice",
    ),
    "federalism_local_governance": (
        "federalism",
        "local governance",
        "federalism and local governance",
        "federalism local governance",
        "decentralization",
    ),
    "energy": (
        "energy",
        "power",
        "electricity",
        "hydropower",
    ),
    "transport": (
        "transport",
        "transportation",
        "transit",
        "mobility",
    ),
    "tourism": (
        "tourism",
        "tourist",
        "hospitality",
    ),
    "housing_urban_development": (
        "housing",
        "urban development",
        "urban planning",
        "city development",
        "settlement",
    ),
    "security": (
        "security",
        "public safety",
        "defense",
        "defence",
    ),
    "other": (
        "other",
        "misc",
        "miscellaneous",
        "general",
    ),
}

_NORMALIZED_ALIAS_TO_SLUG: dict[str, str] = {}
for slug, display in POLICY_CATEGORY_CHOICES:
    base_aliases = {slug, slug.replace("_", " "), display}
    base_aliases.update(_ALIASES_BY_SLUG.get(slug, ()))
    for alias in base_aliases:
        normalized_alias = _normalize_text(alias)
        if normalized_alias:
            _NORMALIZED_ALIAS_TO_SLUG.setdefault(normalized_alias, slug)


_KEYWORDS_BY_SLUG: dict[str, tuple[str, ...]] = {
    "education": ("education", "school", "teacher", "student", "university", "scholarship", "curriculum", "literacy"),
    "finance": ("budget", "tax", "fiscal", "revenue", "bank", "banking", "treasury", "monetary", "inflation", "public spending"),
    "governance": ("governance", "transparency", "accountability", "procurement", "anti corruption", "civil service", "public service delivery"),
    "health": ("health", "hospital", "clinic", "doctor", "nurse", "medicine", "vaccination", "insurance"),
    "infrastructure": ("infrastructure", "drinking water", "water supply", "sanitation", "sewer", "construction", "public works"),
    "agriculture": ("agriculture", "farmer", "farming", "irrigation", "crop", "livestock", "seed", "fertilizer", "dairy", "fisheries"),
    "employment": ("employment", "job", "jobs", "job creation", "unemployment", "skills training", "vocational", "labor", "labour"),
    "social_protection": ("social protection", "social security", "welfare", "pension", "disability", "elderly", "child protection", "safety net"),
    "environment": ("environment", "climate", "pollution", "biodiversity", "conservation", "forest", "waste management", "emissions"),
    "technology": ("technology", "digital", "internet", "broadband", "innovation", "ai", "data governance", "cybersecurity", "e governance"),
    "justice": ("justice", "court", "judiciary", "legal aid", "prosecution", "prison", "human rights"),
    "federalism_local_governance": ("federalism", "local government", "municipality", "province", "provincial", "ward", "decentralization", "intergovernmental"),
    "energy": ("energy", "electricity", "power", "hydropower", "solar", "grid", "transmission"),
    "transport": ("transport", "transit", "mobility", "road", "highway", "rail", "railway", "bus", "airport", "aviation", "logistics"),
    "tourism": ("tourism", "tourist", "hospitality", "trekking", "destination", "heritage site"),
    "housing_urban_development": ("housing", "urban", "city planning", "affordable housing", "land use", "zoning", "urban development"),
    "security": ("security", "police", "policing", "defense", "defence", "military", "border security", "national security"),
}


def _match_known_category(raw_category: str) -> str | None:
    normalized = _normalize_text(raw_category)
    if not normalized:
        return None
    return _NORMALIZED_ALIAS_TO_SLUG.get(normalized)


def _iter_non_empty(values: Iterable[str]) -> list[str]:
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]


def _keyword_score(text: str, keyword: str) -> int:
    if " " in keyword:
        return 3 if keyword in text else 0
    pattern = rf"\b{re.escape(keyword)}(?:s|es)?\b"
    return 1 if re.search(pattern, text) else 0


def _infer_category_from_text(*parts: str) -> str | None:
    text = " ".join(_iter_non_empty(parts))
    normalized_text = _normalize_text(text)
    if not normalized_text:
        return None

    best_slug: str | None = None
    best_score = 0
    for slug in _CATEGORY_ORDER:
        keywords = _KEYWORDS_BY_SLUG.get(slug, ())
        score = sum(_keyword_score(normalized_text, _normalize_text(keyword)) for keyword in keywords if keyword)
        if score > best_score:
            best_slug = slug
            best_score = score

    if best_score <= 0:
        return None
    return best_slug


def classify_policy_category(
    *,
    raw_category: str = "",
    title: str = "",
    summary: str = "",
    description: str = "",
    text: str = "",
) -> PolicyCategoryClassification:
    normalized_slug = _match_known_category(raw_category)
    if normalized_slug:
        return PolicyCategoryClassification(
            slug=normalized_slug,
            display_name=_DISPLAY_BY_SLUG[normalized_slug],
            source="normalized",
        )

    inferred_slug = _infer_category_from_text(raw_category, title, summary, description, text)
    if inferred_slug:
        return PolicyCategoryClassification(
            slug=inferred_slug,
            display_name=_DISPLAY_BY_SLUG[inferred_slug],
            source="inferred",
        )

    return PolicyCategoryClassification(
        slug="other",
        display_name=_DISPLAY_BY_SLUG["other"],
        source="fallback",
    )

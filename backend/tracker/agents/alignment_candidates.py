from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from tracker.agents.schemas import stable_id

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into", "is", "it", "of", "on", "or", "that", "the", "their", "this", "to", "with",
    "will", "would", "can", "could", "should", "our", "we", "your", "within", "across", "all", "every", "through", "about",
}
_MIN_TOKEN_LEN = 3
_MIN_SHARED_TOKENS = 3
_DEFAULT_APPROVAL_THRESHOLD = 0.78
_DEFAULT_REVIEW_THRESHOLD = 0.66


@dataclass(frozen=True)
class AlignmentCandidateMatch:
    agenda_item_id: str
    political_promise_id: str
    relation_type: str
    confidence: float
    notes: str
    score_breakdown: dict[str, float]
    shared_tokens: list[str]
    category_match: bool
    responsible_entity_match: bool
    timeline_match: bool
    agenda_category: str
    promise_category: str

    def to_review_queue_payload(self) -> dict[str, Any]:
        assessment_id = stable_id("alignment_assessment", self.agenda_item_id, self.political_promise_id, self.relation_type, self.notes)
        graph_properties = {
            "alignment_assessment_id": assessment_id,
            "agenda_item_id": self.agenda_item_id,
            "political_promise_id": self.political_promise_id,
            "relation_type": self.relation_type,
            "confidence": self.confidence,
            "approval_state": "approved",
            "notes": self.notes,
            "source_subtype": "agenda_promise_alignment_review",
            "extraction_mode": "reviewed_alignment_assessments",
        }
        return {
            "entity_type": "AlignmentAssessment",
            "record_identity": assessment_id,
            "confidence": self.confidence,
            "risk_flags": ["candidate_generated", "human_review_required"],
            "graph_payload": {"id": assessment_id, "key": "alignmentAssessmentId", "properties": graph_properties},
            "graph_relations": [
                {
                    "relation_type": "ASSESSES_AGENDA_ITEM",
                    "target_entity_type": "AgendaItem",
                    "target_key": "agendaItemId",
                    "target_id": self.agenda_item_id,
                    "target_properties": {"agendaItemId": self.agenda_item_id},
                    "relationship_properties": {"relation_type": self.relation_type, "confidence": self.confidence, "approval_state": "approved"},
                    "require_existing_target": True,
                },
                {
                    "relation_type": "ASSESSES_POLITICAL_PROMISE",
                    "target_entity_type": "PoliticalPromise",
                    "target_key": "politicalPromiseId",
                    "target_id": self.political_promise_id,
                    "target_properties": {"politicalPromiseId": self.political_promise_id},
                    "relationship_properties": {"relation_type": self.relation_type, "confidence": self.confidence, "approval_state": "approved"},
                    "require_existing_target": True,
                },
            ],
            "raw_payload": {
                "agenda_item_id": self.agenda_item_id,
                "political_promise_id": self.political_promise_id,
                "relation_type": self.relation_type,
                "confidence": self.confidence,
                "approval_state": "approved",
                "notes": self.notes,
                "reviewer_status": "approved",
                "placeholder": False,
                "extraction_mode": "reviewed_alignment_assessments",
            },
            "review_context": {"workflow": {"workflow_kind": "agenda_promise_alignment_review", "reviewed_alignment_status": "reviewed_approved", "candidate_generation_method": "deterministic_rules_v1", "score_breakdown": self.score_breakdown, "shared_tokens": self.shared_tokens, "category_match": self.category_match, "responsible_entity_match": self.responsible_entity_match, "timeline_match": self.timeline_match}},
            "source_type": "manifesto",
            "source_subtype": "agenda_promise_alignment_review",
        }


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_text(value: Any) -> str:
    return _clean_text(value).lower()


def tokenize_text(*parts: Any) -> list[str]:
    text = normalize_text(" ".join(_clean_text(part) for part in parts if part))
    tokens = re.findall(r"[a-z0-9]+", text)
    seen: set[str] = set()
    result: list[str] = []
    for token in tokens:
        if len(token) < _MIN_TOKEN_LEN or token in _STOPWORDS or token.isdigit():
            continue
        if token not in seen:
            seen.add(token)
            result.append(token)
    return result


def normalize_category(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize_text(value)).strip()


def _token_jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _contains_any(haystack: str, needles: set[str]) -> bool:
    return any(needle and needle in haystack for needle in needles)


def score_alignment_candidate(agenda: dict[str, Any], promise: dict[str, Any], *, approval_threshold: float = _DEFAULT_APPROVAL_THRESHOLD, review_threshold: float = _DEFAULT_REVIEW_THRESHOLD) -> AlignmentCandidateMatch | None:
    agenda_id = str(agenda.get("agenda_item_id") or "").strip()
    promise_id = str(promise.get("political_promise_id") or "").strip()
    if not agenda_id or not promise_id:
        return None

    agenda_category = normalize_category(agenda.get("category") or agenda.get("policy_category") or "")
    promise_category = normalize_category(promise.get("category") or promise.get("policy_category") or "")
    category_match = bool(agenda_category and promise_category and agenda_category == promise_category)

    agenda_tokens = set(tokenize_text(agenda.get("title"), agenda.get("description"), agenda.get("summary")))
    promise_tokens = set(tokenize_text(promise.get("title"), promise.get("summary"), promise.get("description")))
    shared_tokens = sorted(agenda_tokens & promise_tokens)
    shared_count = len(shared_tokens)
    token_overlap_score = _token_jaccard(agenda_tokens, promise_tokens)

    agenda_timeline = normalize_text(agenda.get("timeline") or agenda.get("timeline_target") or "")
    promise_timeline = normalize_text(promise.get("timeline") or promise.get("timeline_target") or "")
    timeline_tokens = set(tokenize_text(agenda_timeline)) & set(tokenize_text(promise_timeline))
    timeline_match = bool(agenda_timeline and promise_timeline and (agenda_timeline == promise_timeline or len(timeline_tokens) >= 1))

    agenda_responsible = normalize_text(agenda.get("responsible_entity") or "")
    promise_responsible = normalize_text(promise.get("responsible_entity") or "")
    agenda_resp_tokens = set(tokenize_text(agenda_responsible))
    promise_resp_tokens = set(tokenize_text(promise_responsible))
    responsible_entity_match = bool(agenda_responsible and promise_responsible and (agenda_responsible == promise_responsible or len(agenda_resp_tokens & promise_resp_tokens) >= 1 or _contains_any(agenda_responsible, promise_resp_tokens) or _contains_any(promise_responsible, agenda_resp_tokens)))

    if not category_match and shared_count < _MIN_SHARED_TOKENS:
        return None

    score = 0.0
    if category_match:
        score += 0.35
    score += min(token_overlap_score, 0.30)
    if shared_count >= 3:
        score += min(0.15, 0.05 * (shared_count - 2))
    if timeline_match:
        score += 0.10
    if responsible_entity_match:
        score += 0.10

    score = round(min(score, 0.99), 3)
    if score < review_threshold:
        return None

    relation_type = "STRONGLY_ALIGNS" if score >= max(0.90, approval_threshold + 0.08) else "PARTIALLY_ALIGNS"
    notes_parts = []
    if category_match:
        notes_parts.append(f"shared category: {agenda.get('category') or promise.get('category')}")
    if shared_tokens:
        notes_parts.append("shared tokens: " + ", ".join(shared_tokens[:8]))
    if timeline_match:
        notes_parts.append("timeline hint matched")
    if responsible_entity_match:
        notes_parts.append("responsible entity hint matched")

    return AlignmentCandidateMatch(
        agenda_item_id=agenda_id,
        political_promise_id=promise_id,
        relation_type=relation_type,
        confidence=score,
        notes="; ".join(notes_parts)[:500],
        score_breakdown={
            "category": 0.35 if category_match else 0.0,
            "token_overlap": round(min(token_overlap_score, 0.30), 3),
            "shared_token_bonus": round(min(0.15, 0.05 * max(shared_count - 2, 0)), 3),
            "timeline_hint": 0.10 if timeline_match else 0.0,
            "responsible_entity_hint": 0.10 if responsible_entity_match else 0.0,
            "final": score,
        },
        shared_tokens=shared_tokens,
        category_match=category_match,
        responsible_entity_match=responsible_entity_match,
        timeline_match=timeline_match,
        agenda_category=str(agenda.get("category") or "").strip(),
        promise_category=str(promise.get("category") or "").strip(),
    )


def build_alignment_candidates(agenda_items: list[dict[str, Any]], political_promises: list[dict[str, Any]], *, approval_threshold: float = _DEFAULT_APPROVAL_THRESHOLD, review_threshold: float = _DEFAULT_REVIEW_THRESHOLD) -> list[AlignmentCandidateMatch]:
    candidates: list[AlignmentCandidateMatch] = []
    for agenda in agenda_items:
        for promise in political_promises:
            candidate = score_alignment_candidate(agenda, promise, approval_threshold=approval_threshold, review_threshold=review_threshold)
            if candidate is not None:
                candidates.append(candidate)
    candidates.sort(key=lambda item: (-item.confidence, item.agenda_item_id, item.political_promise_id))
    return candidates

import json
from collections import defaultdict
from typing import Any

from django.core.management.base import BaseCommand
from neomodel import db

from tracker.agents.alignment_candidates import build_alignment_candidates
from tracker.agents.schemas import stable_id
from tracker.models import ReviewQueueItem

_FETCH_AGENDA_ITEMS_QUERY = """
MATCH (a:AgendaItem)
OPTIONAL MATCH (a)-[:IN_CATEGORY]->(pc:PolicyCategory)
WITH a, [name IN collect(DISTINCT pc.name) WHERE name IS NOT NULL AND trim(name) <> ""] AS categories
OPTIONAL MATCH (a)-[:HAS_PROBLEM_STATEMENT]->(problem:ProblemStatement)
OPTIONAL MATCH (a)-[:HAS_SOLUTION_PLAN]->(solution:SolutionPlan)
OPTIONAL MATCH (a)-[:HAS_IMPLEMENTATION_PLAN]->(implementation:ImplementationPlan)
OPTIONAL MATCH (a)-[:HAS_PERFORMANCE_TARGET]->(performance:PerformanceTarget)
OPTIONAL MATCH (a)-[:HAS_LEGAL_FOUNDATION]->(legal:LegalFoundation)
OPTIONAL MATCH (a)-[:HAS_REAL_WORLD_EVIDENCE_SUMMARY]->(evidence:RealWorldEvidenceSummary)
WITH a,
     categories,
     head([value IN collect(DISTINCT problem.payload) WHERE value IS NOT NULL]) AS problem_payload,
     head([value IN collect(DISTINCT solution.payload) WHERE value IS NOT NULL]) AS solution_payload,
     head([value IN collect(DISTINCT implementation.payload) WHERE value IS NOT NULL]) AS implementation_payload,
     [value IN collect(DISTINCT performance.text) WHERE value IS NOT NULL AND trim(value) <> ""] AS performance_targets,
     head([value IN collect(DISTINCT legal.text) WHERE value IS NOT NULL AND trim(value) <> ""]) AS legal_foundation,
     head([value IN collect(DISTINCT evidence.payload) WHERE value IS NOT NULL]) AS real_world_evidence
RETURN {
  agenda_item_id: a.agendaItemId,
  title: coalesce(a.title, ""),
  description: coalesce(a.description, ""),
  summary: coalesce(a.summary, ""),
  category: coalesce(a.category, head(categories), ""),
  timeline: coalesce(a.timeline, ""),
  responsible_entity: coalesce(a.responsibleEntity, ""),
  problem: problem_payload,
  solution: solution_payload,
  implementation: implementation_payload,
  performance_targets: performance_targets,
  legal_foundation: coalesce(legal_foundation, ""),
  real_world_evidence: real_world_evidence
} AS row
"""

_FETCH_PROMISES_QUERY = """
MATCH (p:PoliticalPromise)
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(pc:PolicyCategory)
OPTIONAL MATCH (p)-[:ASSIGNED_TO]->(re:ResponsibleEntity)
WITH p,
     [name IN collect(DISTINCT pc.name) WHERE name IS NOT NULL AND trim(name) <> ""] AS categories,
     [name IN collect(DISTINCT re.name) WHERE name IS NOT NULL AND trim(name) <> ""] AS responsible_entities
RETURN {
  political_promise_id: p.politicalPromiseId,
  title: coalesce(p.title, ""),
  summary: coalesce(p.summary, ""),
  description: coalesce(p.description, ""),
  category: coalesce(p.category, head(categories), ""),
  timeline: coalesce(p.timeline, ""),
  responsible_entity: coalesce(p.responsible_entity, head(responsible_entities), "")
} AS row
"""


def _unwrap_rows(rows: list[Any]) -> list[dict[str, Any]]:
    unpacked: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            unpacked.append(row.get("row") if isinstance(row.get("row"), dict) else row)
        elif isinstance(row, (list, tuple)) and row and isinstance(row[0], dict):
            unpacked.append(row[0])
    return unpacked


class Command(BaseCommand):
    help = "Generate deterministic AgendaItem <-> PoliticalPromise alignment review candidates without publishing graph links."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview candidates without creating ReviewQueueItem rows.")
        parser.add_argument("--limit", type=int, default=100, help="Maximum candidates to emit/create after scoring and dedupe.")
        parser.add_argument("--review-threshold", type=float, default=0.40, help="Minimum score to consider for human review.")
        parser.add_argument("--approval-threshold", type=float, default=0.78, help="Higher confidence marker used only for relation strength labeling.")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        limit = max(1, int(options.get("limit", 100)))
        review_threshold = float(options.get("review_threshold", 0.40))
        approval_threshold = float(options.get("approval_threshold", 0.78))

        agenda_rows, _ = db.cypher_query(_FETCH_AGENDA_ITEMS_QUERY)
        promise_rows, _ = db.cypher_query(_FETCH_PROMISES_QUERY)
        agenda_items = _unwrap_rows(agenda_rows)
        political_promises = _unwrap_rows(promise_rows)

        candidates = build_alignment_candidates(
            agenda_items,
            political_promises,
            approval_threshold=approval_threshold,
            review_threshold=review_threshold,
        )

        deduped = []
        seen_pairs: set[tuple[str, str]] = set()
        for candidate in candidates:
            pair = (candidate.agenda_item_id, candidate.political_promise_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            deduped.append(candidate)
            if len(deduped) >= limit:
                break

        existing_pending = {
            item.fingerprint
            for item in ReviewQueueItem.objects.filter(
                entity_type="AlignmentAssessment",
                status__in=["pending_review", "approved"],
            ).only("fingerprint")
        }

        created = 0
        skipped_existing = 0
        score_buckets: dict[str, int] = defaultdict(int)
        preview = []

        for candidate in deduped:
            payload = candidate.to_review_queue_payload()
            fingerprint = stable_id("alignment_review_candidate", candidate.agenda_item_id, candidate.political_promise_id)
            if fingerprint in existing_pending:
                skipped_existing += 1
                continue
            if candidate.confidence >= 0.85:
                score_buckets["0.85+"] += 1
            elif candidate.confidence >= 0.75:
                score_buckets["0.75-0.84"] += 1
            elif candidate.confidence >= 0.60:
                score_buckets["0.60-0.74"] += 1
            else:
                score_buckets["0.40-0.59"] += 1

            preview.append({
                "agenda_item_id": candidate.agenda_item_id,
                "political_promise_id": candidate.political_promise_id,
                "confidence": candidate.confidence,
                "relation_type": candidate.relation_type,
                "notes": candidate.notes,
            })

            if dry_run:
                continue

            ReviewQueueItem.objects.create(
                status="pending_review",
                reason="alignment_candidate_generated",
                risk_level="medium",
                confidence=candidate.confidence,
                entity_type="AlignmentAssessment",
                record_key=payload["record_identity"],
                fingerprint=fingerprint,
                proposed_payload=payload,
                provenance={
                    "source_subtype": "agenda_promise_alignment_review",
                    "candidate_generation_method": "deterministic_rules_v3",
                    "score_breakdown": candidate.score_breakdown,
                    "shared_tokens": candidate.shared_tokens,
                    "agenda_item_id": candidate.agenda_item_id,
                    "political_promise_id": candidate.political_promise_id,
                    "review_context": payload.get("review_context") or {},
                },
            )
            created += 1

        response = {
            "status": "dry_run" if dry_run else "completed",
            "agenda_items_scanned": len(agenda_items),
            "political_promises_scanned": len(political_promises),
            "candidate_pairs_scored": len(agenda_items) * len(political_promises),
            "candidates_selected": len(deduped),
            "created_review_items": 0 if dry_run else created,
            "skipped_existing": skipped_existing,
            "review_threshold": review_threshold,
            "approval_threshold": approval_threshold,
            "score_buckets": dict(sorted(score_buckets.items())),
            "preview": preview[:10],
        }
        self.stdout.write(json.dumps(response, indent=2))

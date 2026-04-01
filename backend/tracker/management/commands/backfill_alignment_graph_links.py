import json

from django.core.management.base import BaseCommand
from neomodel import db

from tracker.management.commands.ingestion_publish_review import _build_direct_alignment_relations
from tracker.agents.smart_neo4j_publisher import publish_record

_FETCH_APPROVED_ALIGNMENTS = """
MATCH (aa:AlignmentAssessment)-[:ASSESSES_AGENDA_ITEM]->(a:AgendaItem)
MATCH (aa)-[:ASSESSES_POLITICAL_PROMISE]->(p:PoliticalPromise)
WHERE coalesce(aa.approvalState, aa.approval_state, "") = "approved"
RETURN {
  alignment_assessment_id: coalesce(aa.alignmentAssessmentId, aa.alignment_assessment_id),
  agenda_item_id: a.agendaItemId,
  political_promise_id: p.politicalPromiseId,
  relation_type: coalesce(aa.relationType, aa.relation_type, "PARTIALLY_ALIGNS"),
  confidence: coalesce(aa.confidence, 0.0),
  approval_state: coalesce(aa.approvalState, aa.approval_state, "approved")
} AS row
"""

_COUNT_EXISTING_DIRECT_LINKS = """
MATCH (:PoliticalPromise {politicalPromiseId: $political_promise_id})-[r:%s]->(t:%s {%s: $target_id})
WHERE coalesce(r.alignmentAssessmentId, r.alignment_assessment_id, "") = $alignment_assessment_id
RETURN count(t) AS count
"""


class Command(BaseCommand):
    help = "Backfill direct PoliticalPromise -> AgendaItem/SolutionPlan/ImplementationPlan links for already-approved AlignmentAssessment nodes."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview backfill work without writing graph links.")
        parser.add_argument("--limit", type=int, default=500, help="Maximum approved alignments to inspect.")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        limit = max(1, int(options.get("limit", 500)))

        rows, _ = db.cypher_query(_FETCH_APPROVED_ALIGNMENTS)
        alignments = []
        for row in rows[:limit]:
            if isinstance(row, dict):
                alignments.append(row.get("row") if isinstance(row.get("row"), dict) else row)
            elif isinstance(row, (list, tuple)) and row and isinstance(row[0], dict):
                alignments.append(row[0])

        created = 0
        skipped_existing = 0
        skipped_missing_targets = 0
        inspected_relations = 0
        preview = []

        for alignment in alignments:
            payload = {
                "record_identity": alignment["alignment_assessment_id"],
                "raw_payload": alignment,
                "graph_payload": {
                    "id": alignment["alignment_assessment_id"],
                    "key": "alignmentAssessmentId",
                    "properties": {
                        "alignmentAssessmentId": alignment["alignment_assessment_id"],
                        "alignment_assessment_id": alignment["alignment_assessment_id"],
                        "relationType": alignment["relation_type"],
                        "relation_type": alignment["relation_type"],
                        "confidence": alignment["confidence"],
                        "approvalState": alignment["approval_state"],
                        "approval_state": alignment["approval_state"],
                    },
                },
            }
            direct_relations = _build_direct_alignment_relations(payload)
            for relation in direct_relations:
                inspected_relations += 1
                target_id = relation.get("target_id")
                if not target_id and relation.get("target_lookup"):
                    try:
                        publish_record({
                            "entity_type": "AlignmentAssessment",
                            "record_identity": alignment["alignment_assessment_id"],
                            "graph_payload": payload["graph_payload"],
                            "graph_relations": [relation],
                        }) if not dry_run else None
                    except ValueError as exc:
                        if "target_id not found" in str(exc):
                            skipped_missing_targets += 1
                            continue
                        raise
                    if dry_run:
                        preview.append({
                            "alignment_assessment_id": alignment["alignment_assessment_id"],
                            "relation_type": relation["relation_type"],
                            "target": "lookup",
                        })
                        created += 1
                    else:
                        created += 1
                    continue

                count_query = _COUNT_EXISTING_DIRECT_LINKS % (
                    relation["relation_type"],
                    relation["target_entity_type"],
                    relation["target_key"],
                )
                count_rows, _ = db.cypher_query(count_query, {
                    "political_promise_id": alignment["political_promise_id"],
                    "target_id": target_id,
                    "alignment_assessment_id": alignment["alignment_assessment_id"],
                })
                existing_count = 0
                if count_rows:
                    first = count_rows[0]
                    if isinstance(first, dict):
                        existing_count = int(first.get("count") or 0)
                    elif isinstance(first, (list, tuple)) and first:
                        existing_count = int(first[0] or 0)
                if existing_count:
                    skipped_existing += 1
                    continue
                if dry_run:
                    preview.append({
                        "alignment_assessment_id": alignment["alignment_assessment_id"],
                        "relation_type": relation["relation_type"],
                        "target_id": target_id,
                    })
                    created += 1
                    continue
                try:
                    publish_record({
                        "entity_type": "AlignmentAssessment",
                        "record_identity": alignment["alignment_assessment_id"],
                        "graph_payload": payload["graph_payload"],
                        "graph_relations": [relation],
                    })
                except ValueError as exc:
                    if "target_id not found" in str(exc):
                        skipped_missing_targets += 1
                        continue
                    raise
                created += 1

        response = {
            "status": "dry_run" if dry_run else "completed",
            "approved_alignments_scanned": len(alignments),
            "direct_relations_inspected": inspected_relations,
            "direct_relations_created": created,
            "skipped_existing": skipped_existing,
            "skipped_missing_targets": skipped_missing_targets,
            "preview": preview[:20],
        }
        self.stdout.write(json.dumps(response, indent=2))

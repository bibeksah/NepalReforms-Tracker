import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tracker.agents.smart_ingestion_engine import refresh_job_rollup
from tracker.agents.smart_neo4j_publisher import ensure_smart_constraints, publish_record
from tracker.models import IngestionDocument, IngestionJob, ReviewQueueItem


def _is_rsp_bacha_patra_provenance_only(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("source_subtype") != "rsp_bacha_patra_pdf":
        return False
    raw_payload = payload.get("raw_payload") or {}
    workflow = raw_payload.get("ocr_workflow") or {}
    return raw_payload.get("extraction_mode") == "document_provenance_only" and workflow.get("structured_promises_status") == "not_extracted"


def _is_rsp_bacha_patra_reviewed_structured_promise(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("entity_type") != "PoliticalPromise":
        return False
    if payload.get("source_subtype") != "rsp_bacha_patra_pdf":
        return False
    raw_payload = payload.get("raw_payload") or {}
    review_context = payload.get("review_context") or {}
    workflow = (review_context.get("workflow") or {})
    return (
        raw_payload.get("extraction_mode") == "reviewed_structured_promises"
        and workflow.get("structured_promises_status") == "reviewed_approved"
        and workflow.get("ocr_text_review_status") == "approved"
    )


def _reviewed_rsp_bacha_patra_promise_is_publishable(payload: dict) -> bool:
    if not _is_rsp_bacha_patra_reviewed_structured_promise(payload):
        return False
    raw_payload = payload.get("raw_payload") or {}
    title = ((raw_payload.get("title") or payload.get("graph_payload", {}).get("properties", {}).get("title") or "").strip())
    excerpt = (raw_payload.get("source_excerpt") or "").strip()
    return (
        bool(title)
        and len(title) >= 10
        and bool(excerpt)
        and len(excerpt) >= 5
        and not bool(raw_payload.get("placeholder", False))
        and float(raw_payload.get("extraction_confidence", 0.0) or 0.0) >= 0.70
        and raw_payload.get("reviewer_status") == "approved"
        and bool(raw_payload.get("manifesto_document_id"))
    )


def _is_reviewed_alignment_assessment(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("entity_type") != "AlignmentAssessment":
        return False
    if payload.get("source_subtype") != "agenda_promise_alignment_review":
        return False
    raw_payload = payload.get("raw_payload") or {}
    review_context = payload.get("review_context") or {}
    workflow = review_context.get("workflow") or {}
    return (
        raw_payload.get("extraction_mode") == "reviewed_alignment_assessments"
        and workflow.get("reviewed_alignment_status") == "reviewed_approved"
    )


def _reviewed_alignment_assessment_is_publishable(payload: dict) -> bool:
    if not _is_reviewed_alignment_assessment(payload):
        return False
    raw_payload = payload.get("raw_payload") or {}
    graph_properties = (payload.get("graph_payload") or {}).get("properties") or {}
    agenda_item_id = str(raw_payload.get("agenda_item_id") or graph_properties.get("agenda_item_id") or "").strip()
    political_promise_id = str(raw_payload.get("political_promise_id") or graph_properties.get("political_promise_id") or "").strip()
    approval_state = str(raw_payload.get("approval_state") or graph_properties.get("approval_state") or "").strip()
    return (
        bool(agenda_item_id)
        and bool(political_promise_id)
        and approval_state == "approved"
        and raw_payload.get("reviewer_status") == "approved"
        and not bool(raw_payload.get("placeholder", False))
    )


def _alignment_provenance_properties(payload: dict) -> dict:
    raw_payload = payload.get("raw_payload") or {}
    graph_properties = (payload.get("graph_payload") or {}).get("properties") or {}
    return {
        "alignmentAssessmentId": str(graph_properties.get("alignmentAssessmentId") or graph_properties.get("alignment_assessment_id") or payload.get("record_identity") or "").strip(),
        "alignment_assessment_id": str(graph_properties.get("alignment_assessment_id") or graph_properties.get("alignmentAssessmentId") or payload.get("record_identity") or "").strip(),
        "relationType": str(raw_payload.get("relation_type") or graph_properties.get("relationType") or graph_properties.get("relation_type") or "PARTIALLY_ALIGNS").strip(),
        "relation_type": str(raw_payload.get("relation_type") or graph_properties.get("relationType") or graph_properties.get("relation_type") or "PARTIALLY_ALIGNS").strip(),
        "confidence": float(raw_payload.get("confidence") or graph_properties.get("confidence") or 0.0),
        "approvalState": str(raw_payload.get("approval_state") or graph_properties.get("approvalState") or graph_properties.get("approval_state") or "approved").strip(),
        "approval_state": str(raw_payload.get("approval_state") or graph_properties.get("approvalState") or graph_properties.get("approval_state") or "approved").strip(),
    }


def _build_direct_alignment_relations(payload: dict) -> list[dict]:
    raw_payload = payload.get("raw_payload") or {}
    agenda_item_id = str(raw_payload.get("agenda_item_id") or "").strip()
    political_promise_id = str(raw_payload.get("political_promise_id") or "").strip()
    if not agenda_item_id or not political_promise_id:
        return []
    rel_props = _alignment_provenance_properties(payload)
    return [
        {
            "relation_type": "ALIGNS_WITH_AGENDA_ITEM",
            "target_entity_type": "AgendaItem",
            "target_key": "agendaItemId",
            "target_id": agenda_item_id,
            "target_properties": {"agendaItemId": agenda_item_id},
            "relationship_properties": rel_props,
            "require_existing_target": True,
            "source_entity_type": "PoliticalPromise",
            "source_key": "politicalPromiseId",
            "source_id": political_promise_id,
        },
        {
            "relation_type": "ALIGNS_WITH_SOLUTION_PLAN",
            "target_entity_type": "SolutionPlan",
            "target_key": "solutionPlanId",
            "target_lookup": {
                "cypher": "MATCH (a:AgendaItem {agendaItemId: $agenda_item_id})-[:HAS_SOLUTION_PLAN]->(s:SolutionPlan) RETURN s.solutionPlanId AS target_id LIMIT 1",
                "params": {"agenda_item_id": agenda_item_id},
            },
            "target_properties": {},
            "relationship_properties": rel_props,
            "require_existing_target": True,
            "source_entity_type": "PoliticalPromise",
            "source_key": "politicalPromiseId",
            "source_id": political_promise_id,
        },
        {
            "relation_type": "ALIGNS_WITH_IMPLEMENTATION_PLAN",
            "target_entity_type": "ImplementationPlan",
            "target_key": "implementationPlanId",
            "target_lookup": {
                "cypher": "MATCH (a:AgendaItem {agendaItemId: $agenda_item_id})-[:HAS_IMPLEMENTATION_PLAN]->(i:ImplementationPlan) RETURN i.implementationPlanId AS target_id LIMIT 1",
                "params": {"agenda_item_id": agenda_item_id},
            },
            "target_properties": {},
            "relationship_properties": rel_props,
            "require_existing_target": True,
            "source_entity_type": "PoliticalPromise",
            "source_key": "politicalPromiseId",
            "source_id": political_promise_id,
        },
    ]


class Command(BaseCommand):
    help = "Publish approved review-queue items to Neo4j and resolve them."

    def add_arguments(self, parser):
        parser.add_argument("--job-id", help="Optional IngestionJob UUID filter. Use 'latest' for newest job.")
        parser.add_argument("--limit", type=int, default=500, help="Maximum approved items to publish.")
        parser.add_argument("--dry-run", action="store_true", help="Preview how many items are publishable without mutating DB/Neo4j.")

    def handle(self, *args, **options):
        job = None
        job_id = options.get("job_id")
        if job_id:
            if job_id == "latest":
                job = IngestionJob.objects.order_by("-created_at").first()
                if not job:
                    raise CommandError("No ingestion jobs found.")
            else:
                try:
                    job = IngestionJob.objects.get(id=job_id)
                except IngestionJob.DoesNotExist as exc:
                    raise CommandError(f"IngestionJob not found: {job_id}") from exc

        qs = ReviewQueueItem.objects.filter(status="approved").order_by("created_at")
        if job:
            qs = qs.filter(job=job)
        limit = max(1, int(options.get("limit", 500)))
        items = list(qs[:limit])

        if options.get("dry_run"):
            payload = {"status": "dry_run", "job_id": str(job.id) if job else None, "approved_items_selected": len(items), "limit": limit}
            self.stdout.write(json.dumps(payload, indent=2))
            return

        ensure_smart_constraints()

        published = 0
        failed = 0
        failures: list[dict] = []
        touched_docs: set[str] = set()
        touched_jobs: set[str] = set()
        now = timezone.now()

        for item in items:
            payload = item.proposed_payload or {}
            if _is_rsp_bacha_patra_provenance_only(payload):
                failed += 1
                failures.append({
                    "item_id": str(item.id),
                    "reason": "ocr_review_incomplete",
                    "error": "rsp_bacha_patra_pdf provenance record cannot be published from approved review until OCR-derived structured records are separately reviewed.",
                })
                continue
            if _is_rsp_bacha_patra_reviewed_structured_promise(payload) and not _reviewed_rsp_bacha_patra_promise_is_publishable(payload):
                failed += 1
                failures.append({
                    "item_id": str(item.id),
                    "reason": "reviewed_ocr_payload_incomplete",
                    "error": "rsp_bacha_patra_pdf reviewed structured promise is missing required approved OCR review fields or confidence.",
                })
                continue
            if _is_reviewed_alignment_assessment(payload) and not _reviewed_alignment_assessment_is_publishable(payload):
                failed += 1
                failures.append({
                    "item_id": str(item.id),
                    "reason": "reviewed_alignment_payload_incomplete",
                    "error": "agenda_promise_alignment_review payload is missing required approved alignment fields or confidence.",
                })
                continue
            publish_payload = payload
            if _is_reviewed_alignment_assessment(payload):
                publish_payload = dict(payload)
                publish_payload["graph_relations"] = list(payload.get("graph_relations") or []) + _build_direct_alignment_relations(payload)
            try:
                result = publish_record(publish_payload)
            except Exception as exc:
                failed += 1
                failures.append({"item_id": str(item.id), "reason": "neo4j_publish_failed", "error": f"{type(exc).__name__}: {exc}"})
                continue
            if not result.get("ok", True):
                failed += 1
                failures.append({"item_id": str(item.id), "reason": "neo4j_publish_failed"})
                continue

            with transaction.atomic():
                locked = ReviewQueueItem.objects.select_for_update().get(id=item.id)
                if locked.status != "approved":
                    continue
                locked.status = "resolved"
                locked.resolved_at = now
                locked.save(update_fields=["status", "resolved_at", "updated_at"])

                if locked.document_id:
                    doc = IngestionDocument.objects.select_for_update().get(id=locked.document_id)
                    doc.published_count += 1
                    if doc.held_count > 0:
                        doc.held_count -= 1
                    if doc.held_count == 0 and doc.published_count > 0 and doc.status != "failed":
                        doc.status = "published"
                    doc.save(update_fields=["published_count", "held_count", "status", "updated_at"])
                    touched_docs.add(str(doc.id))
                    touched_jobs.add(str(doc.job_id))
                elif locked.job_id:
                    touched_jobs.add(str(locked.job_id))
            published += 1

        refreshed_jobs = []
        for refreshed_job_id in sorted(touched_jobs):
            refreshed_job = IngestionJob.objects.get(id=refreshed_job_id)
            refresh_job_rollup(refreshed_job)
            refreshed_jobs.append({"job_id": str(refreshed_job.id), "status": refreshed_job.status})

        response = {
            "status": "completed",
            "job_id": str(job.id) if job else None,
            "approved_items_selected": len(items),
            "published": published,
            "failed": failed,
            "touched_documents": len(touched_docs),
            "refreshed_jobs": refreshed_jobs,
        }
        if failures:
            response["failures"] = failures[:30]
        self.stdout.write(json.dumps(response, indent=2))

import json

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from tracker.models import IngestionJob


class Command(BaseCommand):
    help = "Show centralized ingestion job status."

    def add_arguments(self, parser):
        parser.add_argument(
            "--job-id",
            default="latest",
            help="IngestionJob UUID or 'latest' (default).",
        )
        parser.add_argument(
            "--with-documents",
            action="store_true",
            help="Include per-document status rows.",
        )

    def handle(self, *args, **options):
        job_id = options["job_id"]
        if job_id == "latest":
            job = IngestionJob.objects.order_by("-created_at").first()
            if not job:
                raise CommandError("No ingestion jobs found.")
        else:
            try:
                job = IngestionJob.objects.get(id=job_id)
            except IngestionJob.DoesNotExist as exc:
                raise CommandError(f"IngestionJob not found: {job_id}") from exc

        doc_counts = list(
            job.documents.values("status").annotate(c=Count("id")).order_by("status")
        )
        doc_meta = list(job.documents.values_list("extra_metadata", flat=True))
        translation_checked_documents = 0
        non_english_documents = 0
        translation_applied_documents = 0
        translation_failed_documents = 0
        ocr_source_counts: dict[str, int] = {}
        for meta in doc_meta:
            if not isinstance(meta, dict):
                continue
            if "source_language" in meta or "translation_status" in meta:
                translation_checked_documents += 1
            source_lang = str(meta.get("source_language", "")).lower().strip()
            if source_lang and source_lang not in {"en", "eng", "english"}:
                non_english_documents += 1
            if bool(meta.get("translation_applied", False)):
                translation_applied_documents += 1
            if str(meta.get("translation_status", "")).lower() == "failed":
                translation_failed_documents += 1
            budget_sources = meta.get("record_budget_sources", {})
            if isinstance(budget_sources, dict):
                for key, count in budget_sources.items():
                    try:
                        ocr_source_counts[str(key)] = ocr_source_counts.get(str(key), 0) + int(count)
                    except Exception:
                        continue

        payload = {
            "job_id": str(job.id),
            "name": job.name,
            "status": job.status,
            "priority": job.priority,
            "source_count": job.source_count,
            "processed_count": job.processed_count,
            "published_count": job.published_count,
            "held_count": job.held_count,
            "failed_count": job.failed_count,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "document_status_counts": doc_counts,
            "review_queue_pending": job.review_items.filter(status="pending_review").count(),
            "review_queue_approved": job.review_items.filter(status="approved").count(),
            "review_queue_resolved": job.review_items.filter(status="resolved").count(),
            "translation_checked_documents": translation_checked_documents,
            "non_english_documents": non_english_documents,
            "translation_applied_documents": translation_applied_documents,
            "translation_failed_documents": translation_failed_documents,
            "ocr_source_counts": ocr_source_counts,
        }

        if options.get("with_documents"):
            payload["documents"] = list(
                job.documents.values(
                    "id",
                    "source_document",
                    "source_type",
                    "source_tier",
                    "status",
                    "plan_strategy",
                    "extracted_count",
                    "published_count",
                    "held_count",
                    "attempt_count",
                    "error_detail",
                    "extra_metadata",
                )
            )

        self.stdout.write(json.dumps(payload, indent=2))

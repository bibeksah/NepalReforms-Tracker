import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from tracker.agents.smart_ingestion_engine import run_job
from tracker.models import IngestionDocument, IngestionJob


class Command(BaseCommand):
    help = "Retry failed or review-hold documents in centralized ingestion jobs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--job-id",
            default="latest",
            help="IngestionJob UUID or 'latest' (default).",
        )
        parser.add_argument(
            "--failed-only",
            action="store_true",
            help="Retry only failed documents (default retries failed + review_hold).",
        )
        parser.add_argument("--max-workers", type=int, default=2)
        parser.add_argument("--publish-threshold", type=float, default=0.75)
        parser.add_argument("--no-adaptive", action="store_true")
        parser.add_argument(
            "--max-attempts",
            type=int,
            default=int(os.getenv("TRACKER_DOC_MAX_ATTEMPTS", "5")),
            help="Maximum attempts per document before dead-lettering the job context.",
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

        statuses = ["failed"] if options.get("failed_only") else ["failed", "review_hold"]
        qs = IngestionDocument.objects.filter(job=job, status__in=statuses)
        max_attempts = max(1, int(options.get("max_attempts", 5)))
        exhausted_qs = qs.filter(attempt_count__gte=max_attempts)
        exhausted_ids = list(exhausted_qs.values_list("id", flat=True))
        if exhausted_ids:
            exhausted_qs.update(
                status="failed",
                error_detail=f"retry_exhausted max_attempts={max_attempts}",
                last_attempt_at=timezone.now(),
            )
        qs = qs.exclude(id__in=exhausted_ids)
        doc_ids = list(qs.values_list("id", flat=True))
        if not doc_ids:
            job.status = "dead_letter" if exhausted_ids else job.status
            if exhausted_ids:
                job.completed_at = timezone.now()
                job.save(update_fields=["status", "completed_at"])
            self.stdout.write(
                json.dumps(
                    {
                        "status": "dead_letter" if exhausted_ids else "no_retry_targets",
                        "job_id": str(job.id),
                        "retry_statuses": statuses,
                        "exhausted_documents": len(exhausted_ids),
                        "max_attempts": max_attempts,
                    },
                    indent=2,
                )
            )
            return

        now = timezone.now()
        qs.update(status="queued", error_detail="", last_attempt_at=now)
        job.status = "queued"
        job.completed_at = None
        job.save(update_fields=["status", "completed_at"])

        result = run_job(
            job,
            max_workers=options["max_workers"],
            adaptive=not bool(options.get("no_adaptive")),
            publish_threshold=options["publish_threshold"],
        )
        result["retried_documents"] = len(doc_ids)
        result["exhausted_documents"] = len(exhausted_ids)
        result["max_attempts"] = max_attempts
        self.stdout.write(json.dumps(result, indent=2))

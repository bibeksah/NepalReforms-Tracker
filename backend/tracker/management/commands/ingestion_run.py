import json

from django.core.management.base import BaseCommand, CommandError

from tracker.agents.smart_ingestion_engine import run_job
from tracker.models import IngestionJob


class Command(BaseCommand):
    help = "Run a centralized smart-ingestion job."

    def add_arguments(self, parser):
        parser.add_argument(
            "--job-id",
            default="latest",
            help="IngestionJob UUID or 'latest' (default).",
        )
        parser.add_argument(
            "--max-workers",
            type=int,
            default=4,
            help="Maximum workers for execution. Adaptive mode may use fewer.",
        )
        parser.add_argument(
            "--adaptive",
            action="store_true",
            help="Enable adaptive parallelism (default true).",
        )
        parser.add_argument(
            "--no-adaptive",
            action="store_true",
            help="Disable adaptive parallelism.",
        )
        parser.add_argument(
            "--publish-threshold",
            type=float,
            default=0.75,
            help="Confidence threshold for direct Neo4j publish.",
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

        adaptive = not bool(options.get("no_adaptive"))
        if options.get("adaptive"):
            adaptive = True

        result = run_job(
            job,
            max_workers=options["max_workers"],
            adaptive=adaptive,
            publish_threshold=options["publish_threshold"],
        )
        self.stdout.write(json.dumps(result, indent=2))

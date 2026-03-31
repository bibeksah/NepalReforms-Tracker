from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Legacy command alias (retired). Use centralized retry command."

    def add_arguments(self, parser):
        # Kept for backward CLI compatibility; all options are now ignored.
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--source-path")
        parser.add_argument("--sources-root", default="../sources")
        parser.add_argument("--page-chunk-size", type=int, default=120)
        parser.add_argument("--max-page-workers-per-file", type=int, default=5)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        raise CommandError(
            "retry_failed_ingestion is retired.\n"
            "Use `python manage.py ingestion_retry --job-id <job-id-or-latest>`."
        )

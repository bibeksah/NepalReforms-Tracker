from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Legacy command alias (retired). Use centralized smart ingestion commands."

    def add_arguments(self, parser):
        # Kept for backward CLI compatibility; all options are now ignored.
        parser.add_argument("--sources-root", default="../sources")
        parser.add_argument("--max-workers", type=int, default=6)
        parser.add_argument("--page-chunk-size", type=int, default=120)
        parser.add_argument("--max-page-workers-per-file", type=int, default=5)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force-reingest", action="store_true")
        parser.add_argument("--show-plan", action="store_true")
        parser.add_argument("--source-file")
        parser.add_argument("--spawn-terminals", action="store_true")
        parser.add_argument("--legacy-mode", action="store_true")

    def handle(self, *args, **options):
        raise CommandError(
            "ingest_redbooks_multi_agent is retired.\n"
            "Use the centralized flow:\n"
            "  1) python manage.py ingestion_submit --manifest scripts/smart_ingestion_manifest.example.json\n"
            "  2) python manage.py ingestion_run --job-id latest --max-workers 10"
        )

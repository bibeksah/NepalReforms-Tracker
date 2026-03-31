"""
Management command: install Neo4j constraints and run consistency checks.

Usage:
    python manage.py graph_health                    # Full health check
    python manage.py graph_health --constraints      # Install constraints only
    python manage.py graph_health --consistency      # Consistency checks only
"""

from django.core.management.base import BaseCommand

from tracker.agents.consistency import run_all_checks
from tracker.graph_models import install_constraints


class Command(BaseCommand):
    help = "Install Neo4j constraints and run consistency checks"

    def add_arguments(self, parser):
        parser.add_argument(
            "--constraints",
            action="store_true",
            help="Install Neo4j UNIQUE constraints and indexes",
        )
        parser.add_argument(
            "--consistency",
            action="store_true",
            help="Run graph consistency checks",
        )
        parser.add_argument(
            "--audit",
            action="store_true",
            help="Retired option kept for compatibility (no-op).",
        )

    def handle(self, *args, **options):
        if options.get("audit"):
            self.stdout.write(self.style.WARNING("--audit is retired and has no effect."))

        run_all = not any([options["constraints"], options["consistency"]])

        if run_all or options["constraints"]:
            self._install_constraints()

        if run_all or options["consistency"]:
            self._check_consistency()

    def _install_constraints(self):
        self.stdout.write(self.style.HTTP_INFO("\nInstalling Neo4j constraints..."))
        try:
            count = install_constraints()
            self.stdout.write(self.style.SUCCESS(f"   OK: {count} constraints/indexes installed"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"   FAILED: {exc}"))

    def _check_consistency(self):
        self.stdout.write(self.style.HTTP_INFO("\nRunning graph consistency checks..."))
        try:
            violations = run_all_checks()
            if not violations:
                self.stdout.write(self.style.SUCCESS("   OK: all checks passed"))
                return

            for violation in violations:
                style = self.style.ERROR if violation.severity == "critical" else self.style.WARNING
                self.stdout.write(
                    style(f"   [{violation.severity.upper()}] {violation.check_name}: {violation.message}")
                )
                if violation.affected_nodes:
                    for node in violation.affected_nodes[:3]:
                        self.stdout.write(f"     -> {node}")
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"   FAILED: Neo4j check unavailable: {exc}"))

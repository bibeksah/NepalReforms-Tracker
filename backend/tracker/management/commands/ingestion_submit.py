import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from tracker.agents.smart_ingestion_engine import (
    detect_source_type,
    hash_file,
    infer_fiscal_year,
    infer_scope_from_path,
)
from tracker.models import IngestionDocument, IngestionJob


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        raise CommandError(f"Manifest not found: {path}")
    suffix = path.suffix.lower()
    if suffix in {".json", ".manifest"}:
        return json.loads(path.read_text(encoding="utf-8"))

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise CommandError("YAML manifest requires PyYAML installed.") from exc
        with path.open("r", encoding="utf-8") as stream:
            parsed = yaml.safe_load(stream)
            return parsed or {}

    raise CommandError("Unsupported manifest format. Use .json/.yaml/.yml")


class Command(BaseCommand):
    help = "Submit a centralized smart-ingestion job from manifest or direct document list."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", help="Path to ingestion manifest (json/yaml).")
        parser.add_argument(
            "--document",
            action="append",
            help="Direct document path to ingest. Repeat this flag for multiple files.",
        )
        parser.add_argument("--name", help="Optional job name override.")
        parser.add_argument("--requested-by", default="system", help="Operator identifier.")
        parser.add_argument(
            "--allow-missing",
            action="store_true",
            help="Queue missing/unreadable documents instead of rejecting them at submit time.",
        )

    def handle(self, *args, **options):
        manifest_raw = options.get("manifest")
        direct_documents = options.get("document") or []
        if not manifest_raw and not direct_documents:
            raise CommandError("Provide either --manifest or at least one --document.")
        if manifest_raw and direct_documents:
            raise CommandError("Use either --manifest or --document, not both together.")

        manifest_path: Path | None = None
        if manifest_raw:
            manifest_path = Path(manifest_raw).resolve()
            manifest = _load_manifest(manifest_path)
            docs = manifest.get("documents", [])
            if not isinstance(docs, list) or not docs:
                raise CommandError("Manifest must contain non-empty 'documents' array.")
            job_name = options.get("name") or manifest.get("name") or manifest_path.stem
            priority = int(manifest.get("priority", 50))
            job_options = manifest.get("options", {})
        else:
            docs = [{"path": raw} for raw in direct_documents]
            job_name = options.get("name") or "smart_ingestion_ad_hoc"
            priority = 50
            job_options = {"submitted_via": "document_cli"}

        job = IngestionJob.objects.create(
            name=job_name,
            manifest_path=str(manifest_path) if manifest_path else "",
            requested_by=options.get("requested_by", "system"),
            status="queued",
            priority=priority,
            options=job_options,
        )

        created = 0
        skipped: list[dict] = []
        allow_missing = bool(options.get("allow_missing"))
        for item in docs:
            if isinstance(item, str):
                raw_path = item
                source_type = ""
                source_tier = "A"
                destination = "tracker"
                gov_level = ""
                province_name = ""
                fiscal_year = ""
                extra_metadata = {}
            elif isinstance(item, dict):
                raw_path = str(item.get("path", "")).strip()
                source_type = str(item.get("source_type", "")).strip()
                source_tier = str(item.get("source_tier", "A")).strip() or "A"
                destination = str(item.get("destination", "tracker")).strip() or "tracker"
                gov_level = str(item.get("gov_level", "")).strip()
                province_name = str(item.get("province_name", "")).strip()
                fiscal_year = str(item.get("fiscal_year", "")).strip()
                extra_metadata = item.get("extra_metadata", {}) or {}
            else:
                skipped.append({"path": "", "reason": "invalid_manifest_item_type"})
                continue

            if not raw_path:
                skipped.append({"path": "", "reason": "missing_path"})
                continue

            candidate = Path(raw_path)
            if not candidate.is_absolute():
                preferred_root = manifest_path.parent if manifest_path else Path.cwd()
                preferred = (preferred_root / candidate).resolve()
                fallback = (Path.cwd() / candidate).resolve()
                if preferred.exists():
                    candidate = preferred
                elif fallback.exists():
                    candidate = fallback
                else:
                    candidate = preferred

            if (not candidate.exists() or not candidate.is_file()) and not allow_missing:
                skipped.append({"path": str(candidate), "reason": "file_missing"})
                continue

            source_path = str(candidate)
            inferred_type = source_type or detect_source_type(source_path)
            inferred_gov, inferred_province = infer_scope_from_path(source_path)
            source_document = candidate.name

            IngestionDocument.objects.create(
                job=job,
                source_path=source_path,
                source_document=source_document,
                source_hash=hash_file(source_path),
                source_type=(
                    inferred_type
                    if inferred_type in {"lal_kitab", "manifesto", "media", "citizen", "other"}
                    else "other"
                ),
                source_tier=source_tier if source_tier in {"A", "B", "C"} else "A",
                destination=destination if destination in {"tracker", "platform", "both"} else "tracker",
                gov_level=gov_level or inferred_gov,
                province_name=province_name or inferred_province,
                fiscal_year=fiscal_year or infer_fiscal_year(source_document),
                status="queued",
                extra_metadata=extra_metadata,
            )
            created += 1

        if created == 0:
            job.delete()
            if skipped:
                reason = skipped[0]
                raise CommandError(
                    f"No documents queued. First error: {reason['reason']} path={reason['path']}"
                )
            raise CommandError("No documents queued.")

        job.source_count = created
        job.save(update_fields=["source_count"])
        payload = {
            "status": "queued",
            "job_id": str(job.id),
            "job_name": job.name,
            "documents_created": created,
            "documents_skipped": len(skipped),
            "manifest_path": str(manifest_path) if manifest_path else None,
        }
        if skipped:
            payload["skipped"] = skipped[:20]
        self.stdout.write(json.dumps(payload, indent=2))

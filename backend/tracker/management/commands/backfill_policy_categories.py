import json
from collections import Counter
from typing import Any

from django.core.management.base import BaseCommand
from neomodel import db

from tracker.agents.policy_categories import classify_policy_category
from tracker.agents.schemas import stable_id


_FETCH_NODES_QUERY = """
MATCH (n)
WHERE n:AgendaItem OR n:PoliticalPromise
RETURN {
  entity_type: CASE WHEN n:AgendaItem THEN "AgendaItem" ELSE "PoliticalPromise" END,
  node_id: coalesce(n.agendaItemId, n.politicalPromiseId, ""),
  category: coalesce(n.category, ""),
  name: coalesce(n.name, ""),
  title: coalesce(n.title, ""),
  summary: coalesce(n.summary, ""),
  description: coalesce(n.description, ""),
  text: coalesce(n.text, "")
} AS row
"""

_ENTITY_CONFIG = {
    "AgendaItem": {"id_key": "agendaItemId"},
    "PoliticalPromise": {"id_key": "politicalPromiseId"},
}


def _unpack_row(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        if "row" in row and isinstance(row["row"], dict):
            return row["row"]
        return row
    if isinstance(row, (list, tuple)) and row and isinstance(row[0], dict):
        return row[0]
    return {}


def _normalize_for_compare(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


class Command(BaseCommand):
    help = "Backfill canonical shared PolicyCategory nodes and IN_CATEGORY links for AgendaItem/PoliticalPromise."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview category normalization/linking without mutating Neo4j.")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))

        rows, _ = db.cypher_query(_FETCH_NODES_QUERY)
        category_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        errors: list[dict[str, str]] = []
        category_updates = 0
        links_merged = 0
        processed = 0
        skipped = 0

        for raw in rows:
            node = _unpack_row(raw)
            entity_type = str(node.get("entity_type") or "").strip()
            node_id = str(node.get("node_id") or "").strip()
            config = _ENTITY_CONFIG.get(entity_type)
            if not config or not node_id:
                skipped += 1
                continue

            classification = classify_policy_category(
                raw_category=str(node.get("category") or node.get("name") or ""),
                title=str(node.get("title") or ""),
                summary=str(node.get("summary") or ""),
                description=str(node.get("description") or ""),
                text=str(node.get("text") or ""),
            )
            category_name = classification.display_name
            category_slug = classification.slug
            category_id = stable_id("policy_category", category_name)
            current_category = str(node.get("category") or "")
            if _normalize_for_compare(current_category) != _normalize_for_compare(category_name):
                category_updates += 1
            category_counts[category_slug] += 1
            source_counts[classification.source] += 1
            processed += 1

            if dry_run:
                continue

            try:
                query = """
                MATCH (n:`%s` {%s: $node_id})
                MERGE (c:PolicyCategory {policyCategoryId: $policy_category_id})
                  ON CREATE SET c.createdAt = datetime()
                SET c.name = $category_name,
                    c.slug = $category_slug,
                    c.updatedAt = datetime()
                MERGE (n)-[r:IN_CATEGORY]->(c)
                  ON CREATE SET r.createdAt = datetime()
                SET r.updatedAt = datetime(),
                    n.category = CASE
                        WHEN coalesce(trim(n.category), "") = $category_name THEN n.category
                        ELSE $category_name
                    END
                RETURN n.%s as node_id
                """ % (entity_type, config["id_key"], config["id_key"])
                db.cypher_query(
                    query,
                    {
                        "node_id": node_id,
                        "policy_category_id": category_id,
                        "category_name": category_name,
                        "category_slug": category_slug,
                    },
                )
                links_merged += 1
            except Exception as exc:
                errors.append(
                    {
                        "entity_type": entity_type,
                        "node_id": node_id,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        response = {
            "status": "dry_run" if dry_run else "completed",
            "nodes_scanned": len(rows),
            "nodes_processed": processed,
            "nodes_skipped": skipped,
            "category_updates": category_updates,
            "category_links_merged": 0 if dry_run else links_merged,
            "categories": dict(sorted(category_counts.items())),
            "classification_sources": dict(sorted(source_counts.items())),
        }
        if errors:
            response["errors"] = errors[:30]
            response["failed"] = len(errors)
        self.stdout.write(json.dumps(response, indent=2))

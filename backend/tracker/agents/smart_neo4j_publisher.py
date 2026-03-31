"""
Neo4j direct publisher for smart ingestion.

Publishes high-confidence Project records with deterministic fingerprint merges.
"""

from __future__ import annotations

import hashlib
from typing import Any

from neomodel import db


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def compute_project_fingerprint(record: dict[str, Any]) -> str:
    payload = "|".join(
        [
            normalize_text(record.get("title_ne", "")),
            normalize_text(record.get("title_en", "")),
            str(record.get("budget", 0)),
            normalize_text(record.get("fiscal_year", "")),
            normalize_text(record.get("gov_level", "")),
            normalize_text(record.get("province_name", "")),
            normalize_text(record.get("source_hash", "")),
            str(record.get("page_num", 0)),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ensure_smart_constraints() -> None:
    db.cypher_query(
        "CREATE CONSTRAINT project_fingerprint IF NOT EXISTS "
        "FOR (p:Project) REQUIRE p.fingerprint IS UNIQUE"
    )
    db.cypher_query(
        "CREATE CONSTRAINT fy_year IF NOT EXISTS "
        "FOR (f:FiscalYear) REQUIRE f.year IS UNIQUE"
    )
    db.cypher_query(
        "CREATE CONSTRAINT province_name IF NOT EXISTS "
        "FOR (pr:Province) REQUIRE pr.name IS UNIQUE"
    )


def publish_project_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Upsert project + province + fiscal year with provenance fields.
    """
    fingerprint = compute_project_fingerprint(record)
    params = {
        "fingerprint": fingerprint,
        "title": record.get("title_en") or record.get("title_ne") or "Untitled Project",
        "title_ne": record.get("title_ne", ""),
        "budget": int(record.get("budget", 0)),
        "page_num": int(record.get("page_num", 0)),
        "source_document": record.get("source_document", ""),
        "source_path": record.get("source_path", ""),
        "source_hash": record.get("source_hash", ""),
        "budget_source": record.get("budget_source", "deterministic"),
        "budget_hash": record.get("budget_hash", ""),
        "fiscal_year": record.get("fiscal_year", "unknown"),
        "province": record.get("province_name") or "Federal",
        "gov_level": record.get("gov_level", "federal"),
        "translation_confidence": float(record.get("translation_confidence", 1.0)),
        "ingest_confidence": float(record.get("confidence", 0.0)),
    }

    query = """
    MERGE (fy:FiscalYear {year: $fiscal_year})
      ON CREATE SET fy.uid = randomUUID(), fy.created_at = datetime()
      SET fy.updated_at = datetime()
    MERGE (pr:Province {name: $province})
      ON CREATE SET pr.uid = randomUUID(), pr.created_at = datetime()
      SET pr.updated_at = datetime()
    MERGE (p:Project {fingerprint: $fingerprint})
      ON CREATE SET p.uid = randomUUID(), p.created_at = datetime()
      SET p.updated_at = datetime(),
          p.title = $title,
          p.title_ne = $title_ne,
          p.budget = $budget,
          p.page_num = $page_num,
          p.source_document = $source_document,
          p.source_path = $source_path,
          p.source_hash = $source_hash,
          p.budget_source = $budget_source,
          p.budget_hash = $budget_hash,
          p.gov_level = $gov_level,
          p.translation_confidence = $translation_confidence,
          p.ingest_confidence = $ingest_confidence,
          p.status = 'active'
    MERGE (p)-[:FUNDED_IN]->(fy)
    MERGE (p)-[:LOCATED_IN]->(pr)
    RETURN p.uid as uid, p.fingerprint as fingerprint
    """
    rows, _ = db.cypher_query(query, params)
    if not rows:
        return {"ok": False, "fingerprint": fingerprint, "uid": ""}
    return {"ok": True, "fingerprint": rows[0][1], "uid": rows[0][0]}


def _record_to_params(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "fingerprint": record.get("fingerprint") or compute_project_fingerprint(record),
        "title": record.get("title_en") or record.get("title_ne") or "Untitled Project",
        "title_ne": record.get("title_ne", ""),
        "budget": int(record.get("budget", 0)),
        "page_num": int(record.get("page_num", 0)),
        "source_document": record.get("source_document", ""),
        "source_path": record.get("source_path", ""),
        "source_hash": record.get("source_hash", ""),
        "budget_source": record.get("budget_source", "deterministic"),
        "budget_hash": record.get("budget_hash", ""),
        "fiscal_year": record.get("fiscal_year", "unknown"),
        "province": record.get("province_name") or "Federal",
        "gov_level": record.get("gov_level", "federal"),
        "translation_confidence": float(record.get("translation_confidence", 1.0)),
        "ingest_confidence": float(record.get("confidence", 0.0)),
    }


def publish_project_records_batch(records: list[dict[str, Any]], batch_size: int = 200) -> dict[str, Any]:
    """
    Batch upsert Project nodes using UNWIND for higher throughput.
    """
    if not records:
        return {
            "ok_count": 0,
            "published_fingerprints": [],
            "failed_fingerprints": [],
            "errors": [],
        }

    query = """
    UNWIND $rows AS row
    MERGE (fy:FiscalYear {year: row.fiscal_year})
      ON CREATE SET fy.uid = randomUUID(), fy.created_at = datetime()
      SET fy.updated_at = datetime()
    MERGE (pr:Province {name: row.province})
      ON CREATE SET pr.uid = randomUUID(), pr.created_at = datetime()
      SET pr.updated_at = datetime()
    MERGE (p:Project {fingerprint: row.fingerprint})
      ON CREATE SET p.uid = randomUUID(), p.created_at = datetime()
      SET p.updated_at = datetime(),
          p.title = row.title,
          p.title_ne = row.title_ne,
          p.budget = row.budget,
          p.page_num = row.page_num,
          p.source_document = row.source_document,
          p.source_path = row.source_path,
          p.source_hash = row.source_hash,
          p.budget_source = row.budget_source,
          p.budget_hash = row.budget_hash,
          p.gov_level = row.gov_level,
          p.translation_confidence = row.translation_confidence,
          p.ingest_confidence = row.ingest_confidence,
          p.status = 'active'
    MERGE (p)-[:FUNDED_IN]->(fy)
    MERGE (p)-[:LOCATED_IN]->(pr)
    RETURN collect(p.fingerprint) as fingerprints
    """

    params_rows = [_record_to_params(record) for record in records]
    published_fingerprints: list[str] = []
    failed_fingerprints: list[str] = []
    errors: list[dict[str, str]] = []

    for idx in range(0, len(params_rows), max(1, int(batch_size))):
        chunk = params_rows[idx : idx + max(1, int(batch_size))]
        expected = {row["fingerprint"] for row in chunk}
        try:
            rows, _ = db.cypher_query(query, {"rows": chunk})
            chunk_published = set(rows[0][0] if rows else [])
            published_fingerprints.extend(sorted(chunk_published))
            failed = expected - chunk_published
            failed_fingerprints.extend(sorted(failed))
        except Exception as exc:
            failed_fingerprints.extend(sorted(expected))
            errors.append(
                {
                    "chunk_start": str(idx),
                    "chunk_size": str(len(chunk)),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    return {
        "ok_count": len(published_fingerprints),
        "published_fingerprints": published_fingerprints,
        "failed_fingerprints": failed_fingerprints,
        "errors": errors,
    }

"""Phase 1 Neo4j publisher.

Keeps Lal Kitab project publishing intact, and adds deterministic entity-family publish
paths for NepalReforms agenda baseline, RSP CSV promises, and reviewable alignment
assessment scaffolding.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from neomodel import db


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a dict")
    return value


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _coerce_property_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        if all(isinstance(item, (str, int, float, bool)) or item is None for item in value):
            return value
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _coerce_graph_properties(properties: dict[str, Any]) -> dict[str, Any]:
    return {key: _coerce_property_value(value) for key, value in properties.items()}


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
    statements = [
        "CREATE CONSTRAINT project_fingerprint IF NOT EXISTS FOR (p:Project) REQUIRE p.fingerprint IS UNIQUE",
        "CREATE CONSTRAINT fy_year IF NOT EXISTS FOR (f:FiscalYear) REQUIRE f.year IS UNIQUE",
        "CREATE CONSTRAINT province_name IF NOT EXISTS FOR (pr:Province) REQUIRE pr.name IS UNIQUE",
        "CREATE CONSTRAINT manifesto_document_id IF NOT EXISTS FOR (n:ManifestoDocument) REQUIRE n.manifestoDocumentId IS UNIQUE",
        "CREATE CONSTRAINT agenda_version_id IF NOT EXISTS FOR (n:AgendaVersion) REQUIRE n.agendaVersionId IS UNIQUE",
        "CREATE CONSTRAINT agenda_item_id IF NOT EXISTS FOR (n:AgendaItem) REQUIRE n.agendaItemId IS UNIQUE",
        "CREATE CONSTRAINT political_promise_id IF NOT EXISTS FOR (n:PoliticalPromise) REQUIRE n.politicalPromiseId IS UNIQUE",
        "CREATE CONSTRAINT policy_category_id IF NOT EXISTS FOR (n:PolicyCategory) REQUIRE n.policyCategoryId IS UNIQUE",
        "CREATE CONSTRAINT responsible_entity_id IF NOT EXISTS FOR (n:ResponsibleEntity) REQUIRE n.responsibleEntityId IS UNIQUE",
        "CREATE CONSTRAINT timeline_target_id IF NOT EXISTS FOR (n:TimelineTarget) REQUIRE n.timelineTargetId IS UNIQUE",
        "CREATE CONSTRAINT legal_foundation_id IF NOT EXISTS FOR (n:LegalFoundation) REQUIRE n.legalFoundationId IS UNIQUE",
        "CREATE CONSTRAINT performance_target_id IF NOT EXISTS FOR (n:PerformanceTarget) REQUIRE n.performanceTargetId IS UNIQUE",
        "CREATE CONSTRAINT problem_statement_id IF NOT EXISTS FOR (n:ProblemStatement) REQUIRE n.problemStatementId IS UNIQUE",
        "CREATE CONSTRAINT solution_plan_id IF NOT EXISTS FOR (n:SolutionPlan) REQUIRE n.solutionPlanId IS UNIQUE",
        "CREATE CONSTRAINT implementation_plan_id IF NOT EXISTS FOR (n:ImplementationPlan) REQUIRE n.implementationPlanId IS UNIQUE",
        "CREATE CONSTRAINT real_world_evidence_summary_id IF NOT EXISTS FOR (n:RealWorldEvidenceSummary) REQUIRE n.realWorldEvidenceSummaryId IS UNIQUE",
        "CREATE CONSTRAINT alignment_assessment_id IF NOT EXISTS FOR (n:AlignmentAssessment) REQUIRE n.alignmentAssessmentId IS UNIQUE",
    ]
    for stmt in statements:
        db.cypher_query(stmt)


def publish_project_record(record: dict[str, Any]) -> dict[str, Any]:
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
    if not records:
        return {"ok_count": 0, "published_fingerprints": [], "failed_fingerprints": [], "errors": []}
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
    step = max(1, int(batch_size))
    for idx in range(0, len(params_rows), step):
        chunk = params_rows[idx : idx + step]
        expected = {row["fingerprint"] for row in chunk}
        try:
            rows, _ = db.cypher_query(query, {"rows": chunk})
            chunk_published = set(rows[0][0] if rows else [])
            published_fingerprints.extend(sorted(chunk_published))
            failed_fingerprints.extend(sorted(expected - chunk_published))
        except Exception as exc:
            failed_fingerprints.extend(sorted(expected))
            errors.append({"chunk_start": str(idx), "chunk_size": str(len(chunk)), "error": f"{type(exc).__name__}: {exc}"})
    return {
        "ok_count": len(published_fingerprints),
        "published_fingerprints": published_fingerprints,
        "failed_fingerprints": failed_fingerprints,
        "errors": errors,
    }


def _publish_generic_record(record: dict[str, Any]) -> dict[str, Any]:
    entity_type = _require_non_empty_str(record.get("entity_type"), "entity_type")
    payload = _require_mapping(record.get("graph_payload"), "graph_payload")
    relations = record.get("graph_relations") or []
    if not isinstance(relations, list):
        raise ValueError("graph_relations must be a list")
    node_key = _require_non_empty_str(payload.get("key"), "graph_payload.key")
    node_value = _require_non_empty_str(payload.get("id"), "graph_payload.id")
    properties = payload.get("properties") or {}
    if not isinstance(properties, dict):
        raise ValueError("graph_payload.properties must be a dict")
    properties = _coerce_graph_properties(properties)
    query = """
    MERGE (n:`%s` {%s: $node_value})
      ON CREATE SET n.createdAt = datetime()
      SET n += $properties, n.updatedAt = datetime()
    RETURN $node_value as node_id
    """ % (entity_type, node_key)
    db.cypher_query(query, {"node_value": node_value, "properties": properties})

    relation_results = []
    for rel in relations:
        rel = _require_mapping(rel, "graph_relations[]")
        target_entity_type = _require_non_empty_str(rel.get("target_entity_type"), "graph_relations[].target_entity_type")
        target_key = _require_non_empty_str(rel.get("target_key"), "graph_relations[].target_key")
        relation_type = _require_non_empty_str(rel.get("relation_type"), "graph_relations[].relation_type")
        target_id = _require_non_empty_str(rel.get("target_id"), "graph_relations[].target_id")
        target_properties = rel.get("target_properties") or {}
        relationship_properties = rel.get("relationship_properties") or {}
        if not isinstance(target_properties, dict):
            raise ValueError("graph_relations[].target_properties must be a dict")
        if not isinstance(relationship_properties, dict):
            raise ValueError("graph_relations[].relationship_properties must be a dict")
        target_properties = _coerce_graph_properties(target_properties)
        relationship_properties = _coerce_graph_properties(relationship_properties)
        rel_query = """
        MATCH (s:`%s` {%s: $source_value})
        MERGE (t:`%s` {%s: $target_value})
          ON CREATE SET t.createdAt = datetime()
          SET t += $target_properties, t.updatedAt = datetime()
        MERGE (s)-[r:%s]->(t)
        SET r.updatedAt = datetime(), r += $rel_properties
        RETURN $target_value as target_id
        """ % (
            entity_type,
            node_key,
            target_entity_type,
            target_key,
            relation_type,
        )
        db.cypher_query(
            rel_query,
            {
                "source_value": node_value,
                "target_value": target_id,
                "target_properties": target_properties,
                "rel_properties": relationship_properties,
            },
        )
        relation_results.append(target_id)
    return {"ok": True, "node_id": node_value, "relations": relation_results}


def publish_record(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("entity_type") == "Project":
        return publish_project_record(record)
    return _publish_generic_record(record)


def publish_records_batch(records: list[dict[str, Any]], batch_size: int = 200) -> dict[str, Any]:
    if not records:
        return {"ok_count": 0, "published_ids": [], "failed_ids": [], "errors": []}
    project_records = [record for record in records if record.get("entity_type") == "Project"]
    other_records = [record for record in records if record.get("entity_type") != "Project"]
    published_ids: list[str] = []
    failed_ids: list[str] = []
    errors: list[dict[str, str]] = []
    if project_records:
        project_result = publish_project_records_batch(project_records, batch_size=batch_size)
        published_ids.extend(project_result["published_fingerprints"])
        failed_ids.extend(project_result["failed_fingerprints"])
        errors.extend(project_result["errors"])
    for record in other_records:
        record_id = (record.get("graph_payload") or {}).get("id") or record.get("fingerprint") or ""
        try:
            publish_record(record)
            published_ids.append(record_id)
        except Exception as exc:
            failed_ids.append(record_id)
            errors.append({"entity_type": record.get("entity_type", "Unknown"), "record_id": record_id, "error": f"{type(exc).__name__}: {exc}"})
    return {"ok_count": len(published_ids), "published_ids": published_ids, "failed_ids": failed_ids, "errors": errors}

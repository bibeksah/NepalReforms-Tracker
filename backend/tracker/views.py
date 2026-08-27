from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from neomodel import db

GRAPH_STATUS_QUERY = """
MATCH (a:AgendaItem)
WITH a, coalesce(toString(a.sourceItemId), toString(a.source_item_id)) AS agendaId
WHERE agendaId IS NOT NULL AND agendaId <> "" AND (size($ids) = 0 OR agendaId IN $ids)
CALL {
    WITH a
    OPTIONAL MATCH (a)-[:HAS_SOLUTION_PLAN]->(s:SolutionPlan)
    RETURN count(DISTINCT s) AS solutionPlans
}
CALL {
    WITH a
    OPTIONAL MATCH (a)-[:HAS_IMPLEMENTATION_PLAN]->(i:ImplementationPlan)
    RETURN count(DISTINCT i) AS implementationPlans
}
CALL {
    WITH a
    OPTIONAL MATCH (a)-[:HAS_REAL_WORLD_EVIDENCE_SUMMARY]->(e:RealWorldEvidenceSummary)
    RETURN count(DISTINCT e) AS evidenceSummaries
}
CALL {
    WITH a
    OPTIONAL MATCH (a)-[:HAS_PERFORMANCE_TARGET]->(pt:PerformanceTarget)
    RETURN count(DISTINCT pt) AS performanceTargets
}
CALL {
    WITH a
    OPTIONAL MATCH (aa:AlignmentAssessment)-[:ASSESSES_AGENDA_ITEM]->(a)
    WITH collect(DISTINCT aa) AS assessments
    RETURN size(assessments) AS alignmentAssessments,
           [item IN [assessment IN assessments | coalesce(assessment.relationType, assessment.relation_type)] WHERE item IS NOT NULL][0..10] AS relationTypes
}
CALL {
    WITH a
    OPTIONAL MATCH (p:PoliticalPromise)-[:ALIGNS_WITH_AGENDA_ITEM]->(a)
    RETURN count(DISTINCT p) AS directPromiseLinks
}
CALL {
    WITH a
    OPTIONAL MATCH (p:PoliticalPromise)-[link:ALIGNS_WITH_AGENDA_ITEM]->(a)
    OPTIONAL MATCH (p)-[pd:PROMISED_IN]->(d:ManifestoDocument)
    WITH collect(
        DISTINCT CASE
            WHEN p IS NULL THEN NULL
            ELSE {
                promiseId: coalesce(p.politicalPromiseId, p.political_promise_id, ""),
                promiseTitle: coalesce(p.title, ""),
                relationType: coalesce(link.relationType, link.relation_type, type(link), ""),
                alignmentAssessmentId: coalesce(link.alignmentAssessmentId, link.alignment_assessment_id, ""),
                documentId: coalesce(d.manifestoDocumentId, d.manifesto_document_id, ""),
                documentName: coalesce(d.name, d.title, ""),
                sourceReference: coalesce(d.source_reference, p.source_reference, ""),
                sourcePage: coalesce(pd.source_page, p.source_page),
                sourceExcerpt: coalesce(pd.source_excerpt, p.source_excerpt, "")
            }
        END
    ) AS rawLinks
    RETURN [item IN rawLinks WHERE item IS NOT NULL][0..10] AS promiseLinks
}
RETURN agendaId,
       a.agendaItemId AS agendaItemId,
       a.title AS title,
       coalesce(a.updatedAt, a.updated_at) AS updatedAt,
       coalesce(a.active, true) AS active,
       coalesce(a.priority, "") AS priority,
       coalesce(a.timeline, "") AS timeline,
       solutionPlans,
       implementationPlans,
       evidenceSummaries,
       performanceTargets,
       alignmentAssessments,
       relationTypes,
       directPromiseLinks,
       promiseLinks
ORDER BY agendaId ASC
"""


def _parse_ids(request: HttpRequest) -> list[str]:
    parsed: list[str] = []
    for raw in request.GET.getlist("ids"):
        for part in str(raw).split(","):
            value = part.strip()
            if value:
                parsed.append(value)
    return list(dict.fromkeys(parsed))


def _normalize_promise_links(value: object) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for link in value or []:
        if not isinstance(link, dict):
            continue
        promise_id = str(link.get("promiseId") or "").strip()
        promise_title = str(link.get("promiseTitle") or "").strip()
        if not promise_id and not promise_title:
            continue
        normalized.append(
            {
                "promiseId": promise_id,
                "promiseTitle": promise_title,
                "relationType": str(link.get("relationType") or "").strip(),
                "alignmentAssessmentId": str(link.get("alignmentAssessmentId") or "").strip(),
                "documentId": str(link.get("documentId") or "").strip(),
                "documentName": str(link.get("documentName") or "").strip(),
                "sourceReference": str(link.get("sourceReference") or "").strip(),
                "sourcePage": link.get("sourcePage"),
                "sourceExcerpt": str(link.get("sourceExcerpt") or "").strip(),
            }
        )
    return normalized


def public_agenda_graph_status(request: HttpRequest) -> JsonResponse:
    ids = _parse_ids(request)

    try:
        rows, meta = db.cypher_query(GRAPH_STATUS_QUERY, {"ids": ids})
    except Exception as exc:
        return JsonResponse(
            {
                "data": [],
                "count": 0,
                "ids": ids,
                "error": f"graph_query_failed: {type(exc).__name__}",
            },
            status=500,
        )

    items = []
    for row in rows:
        item = dict(zip(meta, row))
        agenda_id = str(item.get("agendaId") or "").strip()
        if not agenda_id:
            continue

        promise_links = _normalize_promise_links(item.get("promiseLinks"))
        items.append(
            {
                "agendaId": agenda_id,
                "agendaItemId": item.get("agendaItemId") or "",
                "title": item.get("title") or "",
                "updatedAt": item.get("updatedAt"),
                "active": bool(item.get("active", True)),
                "priority": item.get("priority") or "",
                "timeline": item.get("timeline") or "",
                "solutionPlans": int(item.get("solutionPlans") or 0),
                "implementationPlans": int(item.get("implementationPlans") or 0),
                "evidenceSummaries": int(item.get("evidenceSummaries") or 0),
                "performanceTargets": int(item.get("performanceTargets") or 0),
                "alignmentAssessments": int(item.get("alignmentAssessments") or 0),
                "relationTypes": item.get("relationTypes") or [],
                "directPromiseLinks": int(item.get("directPromiseLinks") or len(promise_links) or 0),
                "promiseLinks": promise_links,
            }
        )

    if ids:
        order = {agenda_id: index for index, agenda_id in enumerate(ids)}
        items.sort(key=lambda item: (order.get(item["agendaId"], len(order)), item["agendaId"]))

    return JsonResponse(
        {
            "data": items,
            "count": len(items),
            "ids": ids,
            "source": "live_graph",
        }
    )
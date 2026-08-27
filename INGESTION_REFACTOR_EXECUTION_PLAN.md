# Ingestion Refactor Execution Plan

Status: Active rebuild plan
Scope: tracker/backend smart ingestion system
Mode: Forward-only production rebuild for NepalReforms use

---

## 1. Goal

Rebuild the tracker ingestion system so it becomes production-ready for the locked architecture.

The new system must support:
- NepalReforms agenda ingestion as a first-class source
- RSP manifesto ingestion as a first-class source
- reviewed agenda-to-promise alignment
- forward-only budget and budget-flow ingestion
- paper truth vs ground truth
- strong provenance and review discipline
- graph publishing for all core entity families, not only projects

---

## 2. Keep vs rebuild

## Keep
These parts are worth preserving:
- IngestionJob
- IngestionDocument
- ReviewQueueItem
- FailedIngestionItem
- job orchestration flow
- retry / failure handling
- status commands
- useful Lal Kitab extraction utilities
- reusable language preprocessing / validation helpers where stable

## Rebuild
These parts should be replaced or heavily rewritten:
- graph ontology / graph models
- source routing model
- manifesto ingestion pipeline
- publisher layer
- record contracts / payload schemas
- budget flow representation
- non-project publish paths
- citizen verification data model
- reconciliation path

## Deprecate
These should be treated as legacy prototype paths:
- old `graph_models.py` assumptions
- project-only direct graph publishing design
- generic manifesto-like LLM extraction as the default path
- forced hold of all non-project entities in V1

---

## 3. Production target architecture

The rebuilt ingestion system should have these source-native pipelines:

1. NepalReforms agenda pipeline
2. RSP manifesto pipeline
3. Alignment assessment pipeline
4. Forward-only budget allocation pipeline
5. Forward-only budget flow pipeline
6. Evidence / truth status pipeline
7. Citizen Oracle pipeline
8. Volunteer verification pipeline

The first production milestone should only implement the first three plus the shared ingestion backbone.

---

## 4. Phase sequence

## Phase 1 — Foundation rebuild
Build the new domain core before extending the old prototype.

Deliverables:
- canonical graph entity implementation aligned to FOUNDATION_GRAPH_SCHEMA_V1.md
- source registry discipline
- source-native extractor interfaces
- publisher interfaces by entity family

## Phase 2 — NepalReforms agenda ingestion
Deliverables:
- deterministic ingestion from structured source files
- AgendaVersion, ManifestoDocument, AgendaItem creation
- category, timeline, legal foundation, performance target, problem, solution, implementation, evidence-summary preservation

## Phase 3 — RSP manifesto ingestion
Deliverables:
- deterministic CSV ingestion first
- PoliticalPromise, category, target deadline, responsible entity preservation
- optional PDF enrichment later if needed

## Phase 4 — Alignment layer
Deliverables:
- reviewed AlignmentAssessment creation
- AI suggestion path separated from approved graph truth

## Phase 5 — Forward-only budget allocation + flow
Deliverables:
- BudgetAllocation publisher
- ReleaseEvent / TransferEvent / ReceiptEvent support
- ImplementingBody and Project linking

## Phase 6 — Truth divergence
Deliverables:
- PaperStatus
- GroundStatus
- DivergenceRecord
- ReviewDecision and ReconciliationRecord integration

## Phase 7 — Citizen Oracle + volunteer verification
Deliverables:
- CitizenSubmission
- CitizenCluster
- VerificationTask
- VolunteerReport
- documentary backtracking vs field dispatch logic

---

## 5. File-by-file refactor map

## Keep and adapt
- `backend/tracker/models.py`
  - keep orchestration tables
  - extend only if needed for review / source registry metadata

- `backend/tracker/agents/language_preprocessor.py`
  - keep if stable
  - use only where deterministic parsing cannot preserve original structure directly

- `backend/tracker/agents/validators.py`
  - keep selectively
  - split by source family later

- `backend/tracker/management/commands/ingestion_submit.py`
- `backend/tracker/management/commands/ingestion_run.py`
- `backend/tracker/management/commands/ingestion_status.py`
- `backend/tracker/management/commands/ingestion_retry.py`
- `backend/tracker/management/commands/ingestion_publish_review.py`
  - keep command shell
  - rewire internal service calls to new publishers

## Replace
- `backend/tracker/graph_models.py`
  - replace with schema-aligned graph implementation

- `backend/tracker/agents/smart_ingestion_engine.py`
  - retain orchestration ideas
  - rewrite extraction and publish routing around source-native pipelines

- `backend/tracker/agents/smart_neo4j_publisher.py`
  - replace with entity-family publisher layer

- `backend/tracker/agents/router.py`
  - refactor from generic prompt router into controlled source-routing + optional AI-assist service

- `backend/tracker/agents/schemas.py`
  - replace generic manifesto contracts with explicit source-native contracts

## New modules to add
Suggested structure:
- `backend/tracker/domain/`
  - `source_registry.py`
  - `contracts.py`
  - `review_policy.py`
  - `provenance.py`

- `backend/tracker/publishers/`
  - `agenda_publisher.py`
  - `promise_publisher.py`
  - `alignment_publisher.py`
  - `budget_publisher.py`
  - `truth_publisher.py`

- `backend/tracker/extractors/`
  - `nepalreforms_agenda_extractor.py`
  - `rsp_csv_extractor.py`
  - `rsp_pdf_extractor.py`
  - `budget_extractor.py`

- `backend/tracker/services/`
  - `ingestion_service.py`
  - `alignment_service.py`
  - `review_service.py`
  - `budget_flow_service.py`

---

## 6. Non-negotiable implementation rules

1. Do not flatten structured manifesto sources into generic text blobs.
2. Do not publish current-government fulfillment claims without forward-only scope confirmation.
3. Do not force NepalReforms agenda items and RSP promises into one merged node type.
4. Do not use AI where deterministic structured parsing already exists.
5. Do not let non-approved semantic links become source-of-truth edges.
6. Preserve provenance for every published node and high-impact edge.
7. Budget flow must be event-based, not only allocation-based.

---

## 7. First code milestone

The first implementation milestone should deliver:
- new graph implementation for:
  - ManifestoDocument
  - AgendaVersion
  - AgendaItem
  - PoliticalPromise
  - AlignmentAssessment
  - PolicyCategory
  - ResponsibleEntity
  - TimelineTarget
  - LegalFoundation
  - PerformanceTarget
  - ProblemStatement
  - SolutionPlan
  - ImplementationPlan
  - RealWorldEvidenceSummary
- deterministic NepalReforms agenda ingestion
- deterministic RSP CSV ingestion
- publish path for those entities
- reviewable alignment assessment path

This should happen before budget-flow rebuild.

---

## 8. Immediate next step

Start coding Phase 1 by replacing the legacy graph publishing assumptions and implementing source-native ingestion for:
1. NepalReforms agenda baseline
2. RSP manifesto CSV promises

---

End of execution plan.

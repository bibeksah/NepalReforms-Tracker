# Foundation Graph Schema V1

Status: Phase 1 locked foundation
Scope: Forward-only active tracker architecture
Last optimized against actual source documents in:
- `nepalreforms-platform/public/locales/en/manifesto.json`
- `nepalreforms-platform/public/locales/np/manifesto-summary.json`
- `nepalreforms-platform/scripts/004_seed_manifesto_agendas.sql`
- `nepalreforms-tracker/sources/RSPdocs/pratipaakshya.csv`
- `nepalreforms-tracker/sources/NepalReforms_menafesto/*`

---

## 1. Foundation principles

1. NepalReforms agenda items and RSP manifesto promises are both first-class tracked objects.
2. They are ingested separately.
3. They are connected only when a reviewed relationship exists.
4. Budget truth is forward-only in active scope.
5. Budget flow must be event-based, not allocation-only.
6. Citizen Oracle is signal input, not direct truth input.
7. Paper truth and ground truth are distinct and must both be represented.
8. High-impact semantic links require approval discipline.
9. The schema should reflect the real structure of source documents, not just abstract architecture.

---

## 2. Canonical node families

### 2.1 Reform and promise layer
- `AgendaVersion`
- `AgendaItem`
- `ManifestoDocument`
- `PoliticalPromise`
- `AlignmentAssessment`
- `PolicyCategory`
- `ResponsibleEntity`
- `TimelineTarget`
- `LegalFoundation`
- `PerformanceTarget`

### 2.2 Structured narrative layer
- `ProblemStatement`
- `SolutionPlan`
- `ImplementationPlan`
- `RealWorldEvidenceSummary`

### 2.3 Budget and flow layer
- `FiscalYear`
- `GovernmentTerm`
- `BudgetAllocation`
- `ReleaseEvent`
- `TransferEvent`
- `ReceiptEvent`
- `ImplementingBody`
- `Project`
- `ImplementationEvent`
- `UtilizationEvent`

### 2.4 Evidence and verification layer
- `Evidence`
- `PaperStatus`
- `GroundStatus`
- `DivergenceRecord`
- `ReconciliationRecord`
- `ReviewDecision`

### 2.5 Citizen Oracle layer
- `CitizenSubmission`
- `CitizenCluster`
- `VerificationTask`
- `VolunteerReport`

### 2.6 Context and intelligence layer
- `Location`
- `Contractor`
- `Organization`

---

## 3. Why the schema changed after reading real sources

The NepalReforms source documents are not just simple title/description manifesto rows.
Each agenda item can contain:
- title
- description
- category
- priority
- timeline
- legal foundation
- problem section
- solution section
- implementation section
- performance targets
- real-world evidence

The RSP CSV currently contains at least:
- category
- specific promise
- target deadline
- responsible entity

This means the graph should not flatten everything into one generic text field.
It should preserve the operational structure that already exists in the source material.

---

## 4. Minimal required properties by node type

### AgendaVersion
- `agendaVersionId`
- `name`
- `baselineCount`
- `effectiveFrom`
- `status`
- `sourceReference`

### AgendaItem
- `agendaItemId`
- `sourceItemId`
- `title`
- `description`
- `language`
- `active`
- `sourceReference`

### ManifestoDocument
- `manifestoDocumentId`
- `ownerType` (NepalReforms | Party | Other)
- `ownerName`
- `name`
- `publishedAt`
- `language`
- `sourceReference`

### PoliticalPromise
- `politicalPromiseId`
- `title`
- `summary`
- `language`
- `promiseScope`
- `sourceReference`

### AlignmentAssessment
- `alignmentAssessmentId`
- `relationType` (ALIGNS_WITH | PARTIALLY_ALIGNS | REFRAMES | NO_DIRECT_MATCH)
- `confidence`
- `approvalState`
- `notes`

### PolicyCategory
- `policyCategoryId`
- `name`
- `parentCategory`

### ResponsibleEntity
- `responsibleEntityId`
- `name`
- `entityType`
- `level`

### TimelineTarget
- `timelineTargetId`
- `label`
- `durationText`
- `deadlineType`

### LegalFoundation
- `legalFoundationId`
- `citationText`
- `jurisdiction`

### PerformanceTarget
- `performanceTargetId`
- `targetText`
- `metricType`

### ProblemStatement
- `problemStatementId`
- `shortText`
- `longText`

### SolutionPlan
- `solutionPlanId`
- `shortSummary`
- `longStructureType`

### ImplementationPlan
- `implementationPlanId`
- `shortSummary`
- `longStructureType`

### RealWorldEvidenceSummary
- `realWorldEvidenceSummaryId`
- `shortSummary`
- `longStructureType`

### FiscalYear
- `fiscalYearId`
- `label`
- `startDate`
- `endDate`

### GovernmentTerm
- `governmentTermId`
- `name`
- `startedAt`
- `endedAt`
- `governmentType`

### BudgetAllocation
- `budgetAllocationId`
- `title`
- `amount`
- `currency`
- `budgetClass`
- `sector`
- `subsector`

### ReleaseEvent / TransferEvent / ReceiptEvent
- `eventId`
- `eventType`
- `eventDate`
- `amount`
- `sourceReference`
- `confidence`

### ImplementingBody
- `implementingBodyId`
- `name`
- `bodyType`
- `level` (federal | province | district | local | ward)

### Project
- `projectId`
- `title`
- `projectType`
- `status`
- `startPlanned`
- `endPlanned`

### ImplementationEvent
- `implementationEventId`
- `eventType`
- `eventDate`
- `summary`

### UtilizationEvent
- `utilizationEventId`
- `eventDate`
- `amount`
- `summary`

### Evidence
- `evidenceId`
- `evidenceType`
- `sourceTier`
- `sourceReference`
- `capturedAt`
- `confidence`

### PaperStatus / GroundStatus
- `statusId`
- `status`
- `statusDate`
- `confidence`
- `reason`

### DivergenceRecord
- `divergenceRecordId`
- `divergenceType`
- `openedAt`
- `severity`
- `reason`

### ReconciliationRecord
- `reconciliationRecordId`
- `resolutionType` (AGREE | PARTIAL | CONFLICT | UNRESOLVED | SUPERSEDED)
- `resolvedAt`
- `notes`

### ReviewDecision
- `reviewDecisionId`
- `decisionType`
- `decidedAt`
- `decidedBy`
- `notes`

### CitizenSubmission
- `citizenSubmissionId`
- `channel`
- `submittedAt`
- `locationHint`
- `contentHash`

### CitizenCluster
- `citizenClusterId`
- `clusterTheme`
- `createdAt`
- `signalStrength`
- `credibilityStage`

### VerificationTask
- `verificationTaskId`
- `taskStatus`
- `createdAt`
- `locationSummary`
- `taskType`

### VolunteerReport
- `volunteerReportId`
- `submittedAt`
- `reportSummary`
- `fieldConfidence`

### Location
- `locationId`
- `country`
- `province`
- `district`
- `localBody`
- `ward`

### Contractor
- `contractorId`
- `name`
- `registrationRef`
- `category`

### Organization
- `organizationId`
- `name`
- `orgType`
- `level`

---

## 5. Canonical edge types

### Reform and promise edges
- `(AgendaVersion)-[:CONTAINS]->(AgendaItem)`
- `(ManifestoDocument)-[:CONTAINS]->(AgendaItem)`
- `(ManifestoDocument)-[:CONTAINS]->(PoliticalPromise)`
- `(AgendaItem)-[:IN_CATEGORY]->(PolicyCategory)`
- `(PoliticalPromise)-[:IN_CATEGORY]->(PolicyCategory)`
- `(AgendaItem)-[:HAS_TIMELINE_TARGET]->(TimelineTarget)`
- `(PoliticalPromise)-[:HAS_TIMELINE_TARGET]->(TimelineTarget)`
- `(PoliticalPromise)-[:ASSIGNED_TO]->(ResponsibleEntity)`
- `(AgendaItem)-[:HAS_LEGAL_FOUNDATION]->(LegalFoundation)`
- `(AgendaItem)-[:HAS_PERFORMANCE_TARGET]->(PerformanceTarget)`
- `(AgendaItem)-[:HAS_PROBLEM_STATEMENT]->(ProblemStatement)`
- `(AgendaItem)-[:HAS_SOLUTION_PLAN]->(SolutionPlan)`
- `(AgendaItem)-[:HAS_IMPLEMENTATION_PLAN]->(ImplementationPlan)`
- `(AgendaItem)-[:HAS_REAL_WORLD_EVIDENCE_SUMMARY]->(RealWorldEvidenceSummary)`
- `(AlignmentAssessment)-[:COMPARES_AGENDA]->(AgendaItem)`
- `(AlignmentAssessment)-[:COMPARES_PROMISE]->(PoliticalPromise)`

### Budget and governance edges
- `(BudgetAllocation)-[:IN_FISCAL_YEAR]->(FiscalYear)`
- `(BudgetAllocation)-[:UNDER_GOVERNMENT_TERM]->(GovernmentTerm)`
- `(BudgetAllocation)-[:TARGETS_LOCATION]->(Location)`
- `(BudgetAllocation)-[:MANAGED_BY]->(ImplementingBody)`
- `(BudgetAllocation)-[:FUNDS]->(Project)`
- `(ReleaseEvent)-[:RELATES_TO]->(BudgetAllocation)`
- `(TransferEvent)-[:RELATES_TO]->(BudgetAllocation)`
- `(ReceiptEvent)-[:RELATES_TO]->(BudgetAllocation)`
- `(ReleaseEvent)-[:TO_BODY]->(ImplementingBody)`
- `(TransferEvent)-[:TO_BODY]->(ImplementingBody)`
- `(ReceiptEvent)-[:RECEIVED_BY]->(ImplementingBody)`
- `(Project)-[:LOCATED_IN]->(Location)`
- `(Project)-[:IMPLEMENTED_BY]->(ImplementingBody)`
- `(Project)-[:HAS_IMPLEMENTATION_EVENT]->(ImplementationEvent)`
- `(Project)-[:HAS_UTILIZATION_EVENT]->(UtilizationEvent)`
- `(Project)-[:CONTRACTED_TO]->(Contractor)`

### Evidence and truth edges
- `(Evidence)-[:SUPPORTS]->(Project)`
- `(Evidence)-[:SUPPORTS]->(BudgetAllocation)`
- `(Evidence)-[:SUPPORTS]->(PoliticalPromise)`
- `(Evidence)-[:SUPPORTS]->(AgendaItem)`
- `(Project)-[:HAS_PAPER_STATUS]->(PaperStatus)`
- `(Project)-[:HAS_GROUND_STATUS]->(GroundStatus)`
- `(DivergenceRecord)-[:BETWEEN_PAPER]->(PaperStatus)`
- `(DivergenceRecord)-[:BETWEEN_GROUND]->(GroundStatus)`
- `(ReconciliationRecord)-[:RECONCILES]->(Evidence)`
- `(ReviewDecision)-[:DECIDES]->(Evidence)`
- `(ReviewDecision)-[:DECIDES]->(GroundStatus)`
- `(ReviewDecision)-[:DECIDES]->(AlignmentAssessment)`

### Citizen Oracle edges
- `(CitizenSubmission)-[:CLUSTERED_INTO]->(CitizenCluster)`
- `(CitizenCluster)-[:RELATES_TO_PROJECT]->(Project)`
- `(CitizenCluster)-[:RELATES_TO_LOCATION]->(Location)`
- `(VerificationTask)-[:CREATED_FROM]->(CitizenCluster)`
- `(VolunteerReport)-[:SUBMITTED_FOR]->(VerificationTask)`
- `(VolunteerReport)-[:SUPPORTS]->(GroundStatus)`
- `(VolunteerReport)-[:SUPPORTS]->(Evidence)`

---

## 6. Locked interpretation rules

1. `AgendaItem` and `PoliticalPromise` must never be force-merged.
2. `AlignmentAssessment` is the official way to represent reviewed overlap or non-overlap.
3. No direct current-government fulfillment edge should be created unless the relevant budget/allocation belongs to the forward-only tracking scope.
4. `CitizenSubmission` and `CitizenCluster` do not directly create `PaperStatus`.
5. `GroundStatus` should normally require reviewed field evidence, volunteer input, or equivalent trusted verification.
6. High-impact alignment or fulfillment links must preserve approval state and provenance.
7. NepalReforms agenda ingestion must preserve problem/solution/implementation/evidence structure rather than flattening it.
8. RSP promise ingestion must preserve target deadline and responsible entity when available.

---

## 7. Locked Phase 1 starting order

1. Ingest `ManifestoDocument`, `AgendaVersion`, and `AgendaItem` baseline for NepalReforms.
2. Ingest `ManifestoDocument` and `PoliticalPromise` for RSP.
3. Attach categories, timeline targets, responsible entities, legal foundations, performance targets, and narrative substructures where present.
4. Create reviewed `AlignmentAssessment` records between agendas and promises where relevant.
5. Prepare forward-only budget and flow ingestion using this same graph foundation.

---

End of Foundation Graph Schema V1.

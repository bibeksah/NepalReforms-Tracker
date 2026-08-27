# NepalReforms Tracker + NepalReforms Platform
## Master Architecture and System Plan

Version: 1.0 (Canonical working document)
Status: Active master plan
Owner: NepalReforms

---

## 1. Purpose of this document

This is the single source planning document for the NepalReforms Tracker system and its shared intelligence engine.

It replaces older scattered architecture diagrams, MVP notes, orchestration plans, and implementation sketches.

From now on, this document should answer:
- what the system is
- why it exists
- what it tracks
- how data enters
- how truth is determined
- when humans intervene
- how tracker and NepalReforms platform share the same intelligence layer
- how budget, promises, reforms, and citizen reports are connected

This document is written in direct operational language rather than fragmented planning language.

---

## 2. Core mission

The mission of this system is to build a public accountability engine that can trace political promises, public reforms, budget allocations, budget movement, implementation status, and ground reality from the national level down to the people.

The long-term goal is simple in principle but difficult in execution:

- track what was proposed
- track what was promised
- track what was budgeted
- track where the money moved
- track what physically happened on the ground
- track what people are experiencing
- explain where the system failed when reality and paperwork do not match

The graph is intended to become the core source of truth.

---

## 3. What the system must connect

The system is designed to connect six major layers of reality:

1. NepalReforms reform agenda
2. Political promise layer
3. Budget allocation layer
4. Budget movement layer
5. Implementation / utilization layer
6. Citizen ground reality layer

These layers must stay distinct but connected.

### 3.1 NepalReforms reform agenda layer
This is the civic reform layer created after the post-protest political rupture.

The NepalReforms platform began with 27 reforms and later expanded to 31 reforms through additional public opinions and refinements.`r`n`r`nThe current working baseline is 31 agendas.`r`nAgenda version tracking should begin after this 31-agenda baseline, so future additions, removals, merges, and refinements are explicitly versioned.`r`nThe current agenda source material is maintained in the source/nepalreforms-platform folder.`r`n`r`nThis means the system must treat the reform agenda as a living agenda with version control from the 31-agenda state onward rather than a frozen one-time manifesto.

### 3.2 Political promise layer
This layer contains:
- RSP Bachapatra / Vacha Patra commitments
- later MP-level constituency promises
- other written public commitments as scope expands

The system must be able to answer:
- which NepalReforms agendas were taken into political promises
- which were ignored
- which were adopted partially

### 3.3 Budget allocation layer
This layer contains the formal budget commitments found in Lal Kitab and related official records.

The tracker should operate as a forward-only accountability system from the present point onward.

### 3.4 Budget movement layer
This layer is critical and must be modeled explicitly.

Allocation is not enough.
The system must trace movement through the chain:
- federal approval
- federal release
- province receipt
- province release
- district/local receipt
- ward availability

This is where many real failures or diversions may occur.

### 3.5 Implementation / utilization layer
This layer tracks whether work actually started, continued, completed, stalled, or was falsely claimed as completed.

### 3.6 Citizen ground reality layer
This layer captures what people experience, report, and observe.

Citizen input is important, but it is not immediate truth. It is treated as signal until verified.

---

## 4. The two public products

This architecture supports two public-facing systems using one shared intelligence engine.

### 4.1 tracker.nepalreforms.com
The tracker is the accountability surface.
It focuses on:
- promises
- budgets
- allocation vs utilization
- project status
- evidence-backed implementation truth
- constituency and geographic drill-down

### 4.2 nepalreforms.com
The platform is the civic participation and public demand surface.
It focuses on:
- reform agendas
- public participation
- demands
- structured opinions
- unmet grievances
- demand clustering and promotion

The tracker and platform are different products, but they should share one intake and reasoning backbone.

---

## 5. Source-of-truth philosophy

The graph is intended to become the source of truth, but not all data enters the graph equally.

The system must always distinguish between:
- demand
- claim
- evidence
- verified truth

The graph must never become a dumping ground for unverified sentiment.

It should become a disciplined reconciliation layer where:
- official data is ingested
- citizen signals are clustered
- contradictions are identified
- humans verify high-impact ambiguities
- all important conclusions remain explainable through provenance

---

## 6. Trust tiers

All inputs must be assigned a trust tier.

### Tier A
Official government documents and records.
Examples:
- Lal Kitab
- gazettes
- ministry records
- official releases
- treasury / release records when available

### Tier B
Credible public evidence.
Examples:
- verified media
- verified public social accounts
- corroborated public evidence

### Tier C
Citizen and unverified inputs.
Examples:
- WhatsApp reports
- Viber reports
- Telegram reports
- Instagram reports
- forms
- direct public complaints and opinions

Tier C should never directly alter accountability truth without passing verification gates.

---

## 7. Main ingestion architecture

The ingestion layer has three major components before and around the shared AI reasoning engine.

### 7.1 Source layer
This defines where information comes from.

Sources include:
- government documents
- public media and verified social sources
- citizen oracle inputs
- current official and public inputs from this point forward

### 7.2 Adapters and fetchers
These are the mechanisms that pull or receive data from the source layer.

Main adapters include:
- doc fetcher for PDF / HTML / API sources
- news / social harvester
- bot intake gateway for citizen oracle
- direct source intake for current and future records

The job of adapters is to convert messy external inputs into a consistent raw event structure.

### 7.3 Schedulers and operations control
This layer controls when and how processing happens.

Current intended operating pattern:
- continuous Citizen Oracle intake
- daily main processing run
- daily retry run
- monthly cleanup
- priority-based queue handling

---

## 8. Shared AI intelligence engine

One shared AI engine should power both tracker and NepalReforms platform.

Its current intended roles are:
1. Ingestion agent
2. Citizen cluster agent
3. Label / normalize agent
4. Dedup agent
5. Topic + entity extraction agent
6. Verification and risk gate agent
7. Budget flow trace agent
8. Anomaly detection agent
9. Volunteer task generation agent
10. Graph attachment agent
11. Reconciliation agent
12. Conclusion / status proposal agent
13. Publisher / routing agent

This engine is not the source of truth by itself.
It is a proposal, enrichment, routing, and structuring engine that works under policy.

---

## 9. What each AI stage does

### 9.1 Ingestion agent
Reads staged batches and determines the processing path.

### 9.2 Citizen cluster agent
Clusters similar Citizen Oracle submissions into structured issue groups before further reasoning.

### 9.3 Label / normalize agent
Standardizes names, entities, dates, amounts, scope, and bilingual labels.

### 9.4 Dedup agent
Removes duplicates and near-duplicates across sources.

### 9.5 Topic + entity extraction agent
Identifies agendas, promises, projects, ministries, localities, claims, demands, and evidence candidates.

### 9.6 Verification and risk gate agent
Applies source-tier logic, contradiction checks, and defamation-sensitive handling.

### 9.7 Budget flow trace agent
Reconstructs the budget movement chain from allocation through release, receipt, availability, and implementation milestones.

### 9.8 Anomaly detection agent
Detects suspicious patterns such as abnormal transfer delays, missing downstream receipts, paper/ground mismatch indicators, repeated complaints against completed work, and suspicious contractor patterns.

### 9.9 Volunteer task generation agent
Creates structured field-verification task packets when a lead is documentary-credible and field checking is justified.

### 9.10 Graph attachment agent
Proposes how structured items should connect inside the graph.

### 9.11 Reconciliation agent
Compares conflicting truth inputs from official documents, citizen clusters, volunteer evidence, media, and local records and determines whether they agree, partially agree, conflict, remain unresolved, or are superseded.

### 9.12 Conclusion / status proposal agent
Proposes interpretations such as funded, delayed, active, incomplete, unsupported, or divergent between paper truth and ground truth.

### 9.13 Publisher / routing agent
Determines whether the result should:
- go to tracker
- go to NepalReforms platform
- go to both
- go to human review
- remain staged only

---

## 10. Routing logic between tracker and platform

Every relevant item should be classified into one of three high-level types:
- tracking
- request
- both

### tracking
Used for factual accountability items such as:
- project status
- budget allocation
- budget movement
- implementation evidence

### request
Used for unmet public demands, grievances, and reform asks that are not yet verified accountability facts.

### both
Used when an item contains both public demand and factual accountability relevance.

---

## 11. Citizen Oracle philosophy

Citizen Oracle is not direct truth input.
It is structured civic signal input.

Its function is to collect what people are seeing, needing, experiencing, and claiming.

That data is useful, but dangerous if treated as truth without discipline.

Therefore Citizen Oracle should be used to:
- detect recurring concerns
- cluster local complaints
- identify possible implementation problems
- surface unmet reform demands
- trigger documentary and field verification paths when justified

---

## 12. Citizen Oracle processing flow

### Step 1: raw intake
Citizen reports arrive through supported channels.

### Step 2: clustering
Similar reports are grouped into one structured cluster.

### Step 3: signal shaping
The system identifies:
- what the common issue is
- where it is happening
- whether it may relate to a known project, budget, promise, or reform

### Step 4: credibility analysis
The system does not send volunteers automatically.
It first checks whether the lead is credible enough.

### Step 5: branch decision
A cluster may become:
- a demand-only item
- a documentary backtracking case
- a field verification case
- a mixed case

---

## 13. Human in the loop

Human review is not just final approval after AI. It is a structured verification layer.

There are at least three kinds of human involvement:
- editorial review
- volunteer field verification
- sensitive contradiction review

---

## 14. Volunteer verification model

Volunteers should not be sent for every citizen complaint.

They should only be sent when the lead is already documentary-credible and the unresolved question is about ground truth.

### Correct volunteer trigger
Send volunteer only if:
- a real budget/project/promise exists
- the documentary trail shows the item plausibly reached the local implementation layer
- and the remaining uncertainty is physical execution on the ground

### Do not send volunteer if:
- the issue is still likely in the paperwork or release chain
- the budget appears not to have reached the ward/local implementation layer yet
- the anomaly is upstream and explainable through system backtracking

---

## 15. Documentary backtracking before field verification

This is one of the most important architectural rules.

When a citizen complaint is received, the system should first ask:
- is the project real?
- is it budgeted?
- was it released?
- where is it in the movement chain?
- how long should movement normally take?
- how long has it actually taken?

If the budget has not yet credibly reached the ward, then the likely issue is administrative, political, or financial bottleneck in the release chain.

That should trigger system investigation, not volunteer dispatch.

---

## 16. Budget flow timing model

The system must eventually learn or define how long budget movement normally takes through each stage.

Example movement path:
- federal -> province
- province -> district/local
- district/local -> ward

The tracker should compare:
- expected time
- actual time

### If actual time is far beyond expected range
This becomes a system anomaly.
Backtrack the chain.

### If the papers show the budget reached the ward but the work is not done
This becomes a field anomaly.
Send volunteer.

---

## 17. Two forms of truth

The system must explicitly distinguish between paper truth and ground truth.

### Paper truth
What official records claim:
- budget approved
- released
- received
- completed
- utilized

### Ground truth
What local reality shows:
- incomplete
- delayed
- abandoned
- lower-quality implementation
- no visible work
- false completion claim

A major mission of the tracker is to explain when these two truths diverge.

---

## 18. Core graph responsibilities

The graph should not merely store entities. It should explain relationships and flows.

It should eventually support answering:
- which NepalReforms agendas became political promises
- which promises became funded
- which funded items moved through the system successfully
- where releases stalled
- where money reached but work did not happen
- where people are reporting problems
- where paper truth and ground truth disagree

---

## 19. What the graph should be able to answer

Examples of target questions:
- Which NepalReforms agendas were adopted by RSP?
- Which of those got budget allocations?
- How much was allocated?
- In which fiscal year?
- Which ministry is responsible?
- Which province/district/ward is affected?
- Did the budget reach local level?
- Did implementation begin?
- Was the work completed?
- Do citizens report a contradiction?
- Has a volunteer verified the contradiction?
- Where in the chain did the delay or corruption most likely occur?

---

## 20. Current scope baseline

The current working scope includes:
- NepalReforms reform agendas
- RSP commitments
- current and upcoming budget lines
- budget allocation vs utilization from this point forward
- later MP-level promises
- Citizen Oracle demand and claim intake

Historical files may remain archived as reference material, but historical backfilling is not part of the active MVP architecture.

---

## 21. Design principles

The architecture should obey these principles:

1. The graph is the source of truth, but only after policy-controlled validation.
2. Citizen input is signal first, truth later.
3. Do system backtracking before field dispatch when possible.
4. Humans verify high-impact ambiguity.
5. Every important edge must be explainable by provenance.
6. Demand, claim, evidence, and verified truth must stay distinct.
7. Tracker and platform should share one intelligence backbone but remain separate public experiences.
8. Paper truth and ground truth must be separately modeled.
9. Time matters; accountability is temporal.
10. The system must be able to say not just what happened, but where the chain failed.

---

## 21A. Founder-approved refinement decisions (current)

The following architecture improvements are currently accepted into the master direction:

1. Model the budget flow chain explicitly.
2. Separate promise tracking from fund-flow tracking while linking them clearly.
3. Add a credibility ladder before human review.
4. Make volunteer tasks structured rather than narrative.
5. Agenda versioning is accepted, but formal tracked versioning begins after the current 31-agenda baseline.
6. Distinguish paper truth from ground truth.
7. Make anomaly detection a core system capability.
8. Define normal transfer timelines by budget/program type.
9. Strictly separate demand, claim, and evidence.
10. Track contractor and implementer intelligence.
11. Use decomposed confidence rather than one flat confidence score.
12. Make provenance queryable at every important edge.
13. Split review queues by problem type.
14. Make temporal truth first-class in the graph.
15. Keep high-impact AI linking under approval discipline.
16. Make "no volunteer needed" a first-class resolution.
17. Add anti-manipulation protections to Citizen Oracle.
18. Track what is missing, not only what is present.
19. Add a reconciliation engine for conflicting signals.
20. Design outputs for explanation, not just storage.
## 22. What this document will become next

This document is the living master architecture.

It will be improved iteratively through structured founder review.
Each refinement should be added back into this document so that the architecture becomes progressively more precise and operational.

---

## 23. Immediate next refinement topics

The next stage of refinement should clarify:
- graph entity model
- budget flow model
- agenda versioning model
- documentary vs field verification workflow
- volunteer task packet design
- platform/tracker routing rules
- anomaly detection logic
- confidence decomposition
- provenance and audit design
- queue/review workflows

---

End of current version.


## 24. Accepted architecture refinements now locked into this plan

The following decisions are now treated as accepted architectural direction.
They are no longer open brainstorming items.

### 24.1 Explicit budget flow chain
The system must model budget movement as a first-class chain rather than treating budget allocation as the end of financial truth.

Required movement stages include:
- federal approval
- federal release
- province receipt
- province release
- district/local receipt
- ward availability
- implementation start
- implementation completion
- utilization evidence

The graph and surrounding state model should eventually support entities and/or state transitions such as:
- BudgetAllocation
- ReleaseEvent
- TransferEvent
- ReceiptEvent
- ImplementationEvent
- UtilizationEvent

### 24.2 Separate but linked truth chains
The system must maintain two linked but distinct chains.

#### Political commitment chain
- NepalReforms agenda
- RSP Bachapatra promise
- MP/local promise later as the system expands

#### Financial execution chain
- budget line
- release path
- implementing body
- project status
- utilization

These must be linked, but not collapsed into one object model.
A promise can exist without funding.
Funding can exist without execution.
Execution can happen without being meaningfully connected to the promise.

### 24.3 Credibility ladder before human intervention
A lead maturity model must exist before volunteer or editorial escalation.

Proposed credibility ladder:
- raw signal
- clustered signal
- linked to real project
- linked to real release chain
- documentary anomaly found
- field-worthy anomaly
- volunteer verified
- editorially approved
- graph-truth eligible

This ladder is intended to make decisions consistent and auditable.

### 24.4 Structured volunteer task packets
Volunteer tasks must never be vague narrative assignments.
Each task should clearly specify:
- what claim is being checked
- why the lead is considered credible
- official release status
- likely linked project or budget item
- exact or best-known location
- required evidence types
- what counts as approval / rejection / partial confirmation
- whether the suspected issue is execution failure, non-arrival, diversion, or mixed

### 24.5 Agenda evolution and versioning rule
Agenda versioning is accepted, but formal tracked versioning begins after the current 31-agenda baseline.

The current accepted baseline is:
- NepalReforms platform started with 27 reforms
- later expanded to 31 reforms
- future modifications after this 31-agenda state must be explicitly versioned

The source material currently lives in the source/nepalreforms-platform folder.

### 24.6 Paper truth vs ground truth must be first-class
Every tracked item must support a distinction between official documentary reality and field reality.

Core concepts:
- paper_status
- ground_status
- status_divergence
- divergence_reason

This distinction is fundamental because many accountability failures happen when documents claim completion or release while ground reality shows delay, absence, or lower-quality work.

### 24.7 Anomaly detection is a core capability
The system should not treat anomaly detection as an optional layer.
It is central to the accountability mission.

Important anomaly classes include:
- transfer delays beyond expected range
- duplicate releases
- missing downstream receipts
- paper-complete but no field evidence
- utilization mismatches
- repeated citizen complaints against officially completed work
- same contractor repeated across suspicious cases
- repeated budget patterns with no visible outcome

### 24.8 Normal transfer timelines by budget/program type
The system must define or learn expected transfer timelines by category rather than using one generic delay rule.

This should vary by:
- budget class
- level in the chain
- geography / remoteness
- implementation type

The model should support a confidence band around what counts as normal delay.

### 24.9 Strict distinction between demand, claim, and evidence
This distinction is non-negotiable.

- Demand = what people want or need
- Claim = what people say happened
- Evidence = what supports belief that something happened

The system must never auto-upgrade one into another without passing validation rules.

### 24.10 Contractor / supplier / implementer intelligence
Tracking public money requires entity intelligence beyond government levels.

The system should eventually track:
- contractor identity
- awards
- repeated vendor patterns
- completion history
- geography concentration
- complaint frequency
- historical anomalies

### 24.11 Confidence decomposition
The system should not use only one flat confidence score.
It should decompose confidence into distinct dimensions such as:
- source confidence
- extraction confidence
- linkage confidence
- transfer-chain confidence
- field-verification confidence
- editorial confidence

### 24.12 Queryable provenance at every important edge
Every important relation must remain explainable.

Each important edge should eventually preserve:
- evidence references
- method of creation
- who approved it
- when it was last reviewed
- confidence
- whether it came from AI suggestion, official records, or volunteer verification

### 24.13 Review queues by problem type
The system should not rely on one generic review queue.
It should eventually support specialized queues such as:
- low-confidence extraction
- budget transfer anomaly
- citizen cluster awaiting system check
- field verification task pending
- volunteer report awaiting editorial approval
- contradiction between paper and ground
- legal/defamation-sensitive claims

### 24.14 Temporal truth
The system must preserve time as a first-class dimension.
It must answer not only what is true, but when that truth changed.

Examples:
- when approved
- when it should have moved
- when it actually moved
- when the complaint arose
- when the field check happened
- when status changed

### 24.15 Approval discipline for high-impact AI linking
AI may propose links such as:
- agenda <-> promise
- promise <-> project
- complaint <-> project

But politically or financially sensitive links should not be auto-authoritative.
For high-impact links, the system should preserve:
- AI proposal
- human/editor approval state
- provenance of approval

### 24.16 “No volunteer needed” as a first-class resolution
Citizen Oracle outcomes must explicitly include cases where field verification is unnecessary.

Possible outcomes should include:
- insufficient signal
- duplicate/noise
- demand-only
- documentary backtracking needed
- volunteer field check needed
- resolved by official records alone
- escalated for editorial/legal review

### 24.17 Anti-manipulation protections for Citizen Oracle
The system must assume that people may try to game public input channels.

It should eventually defend against:
- repeated fake submissions
- coordinated political spam
- location spoofing
- same claim from many fake identities
- bot amplification
- targeted defamation

Likely controls include:
- unique submitter-aware clustering
- phone/account trust scoring
- repetition weighting by identity quality
- geographic consistency checks
- anomaly flags for coordinated campaigns

### 24.18 Track what is missing, not only what is present
The tracker must not only explain what got budget and what moved.
It should also explain absence.

Examples:
- which reforms/promises got no meaningful allocation
- which allocations show no downstream implementation footprint
- which commitments remain unfunded or structurally unsupported

### 24.19 Reconciliation engine
The architecture must eventually reconcile multiple truth sources.
Relevant sources include:
- official records
- public platform demands
- citizen reports
- volunteer evidence
- media reports
- local government records

The reconciliation layer should eventually support outcomes such as:
- agree
- partially agree
- conflict
- unresolved
- superseded

### 24.20 Outputs must explain, not merely store
The final user experience should explain the money and accountability chain in human language.

Example target explanation style:
- approved in federal budget
- released to province on X date
- received by local body on Y date
- no verified implementation evidence after Z days
- N citizen complaints clustered
- volunteer verified incomplete work on date A
- current status: paper-released, ground-delayed

This is how the tracker builds trust with users.

## 25. Working note on question flow

The earlier one-by-one architectural question flow is no longer the main process.
The accepted founder decisions above should now be treated as the active refinement base.

Future questions should only be asked when there is a genuinely unresolved design choice that materially changes the system model.


### 24.21 Standalone agent expansion rule
The following capabilities are no longer treated only as background logic modules.
They are now explicitly elevated to standalone agents in the architecture:
- Citizen cluster agent
- Budget flow trace agent
- Anomaly detection agent
- Volunteer task generation agent
- Reconciliation agent

This means the formal core agentic architecture now contains 13 explicit agents rather than 8.

### 24.22 Forward-only tracking rule
The active architecture is now forward-only.

This means:
- historical backfilling is removed from the active MVP scope
- the tracker should build accountable truth from the present point onward
- old files may remain archived as source/reference material, but they should not be treated as graph-complete historical truth unless a future dedicated historical ingestion phase is approved

This rule is intended to preserve source-of-truth quality by avoiding incomplete or misleading reconstruction of past fiscal years.


## 26. Phase 1 foundation lock

Phase 1 is now officially locked around a graph-first foundation.

### 26.1 First-class tracked universes
The system must track both of these independently:
- NepalReforms agenda items
- RSP manifesto promises

Neither one should be treated as a subset of the other.
They are connected only when a reviewed relationship exists.

### 26.2 Official relationship object for overlap
The architecture should use an explicit `AlignmentAssessment` object to represent whether an agenda item and a political promise:
- align
- partially align
- reframe one another
- have no direct match

This is better than forcing every item into a direct match/no-match edge without review context.

### 26.3 Locked canonical Phase 1 node families
The foundation node families are now:
- AgendaVersion
- AgendaItem
- ManifestoDocument
- PoliticalPromise
- AlignmentAssessment
- FiscalYear
- GovernmentTerm
- BudgetAllocation
- ReleaseEvent
- TransferEvent
- ReceiptEvent
- ImplementingBody
- Project
- ImplementationEvent
- UtilizationEvent
- Evidence
- PaperStatus
- GroundStatus
- DivergenceRecord
- ReconciliationRecord
- ReviewDecision
- CitizenSubmission
- CitizenCluster
- VerificationTask
- VolunteerReport
- Location
- Contractor
- Organization

### 26.4 Locked Phase 1 implementation order
1. Ingest NepalReforms agenda baseline.
2. Ingest RSP manifesto document and promises.
3. Create reviewed alignment assessments where relevant.
4. Build forward-only budget and flow ingestion on the same schema.


### 26.5 Source-grounded schema optimization
After reviewing the actual source documents, the graph schema was optimized to reflect the real document structure.

Important findings:
- NepalReforms manifesto items are richly structured and contain category, priority, timeline, legal foundation, performance targets, and nested problem/solution/implementation/evidence sections.
- RSP source data currently exposes at least category, specific promise, target deadline, and responsible entity.

As a result, the Phase 1 foundation must preserve:
- PolicyCategory
- ResponsibleEntity
- TimelineTarget
- LegalFoundation
- PerformanceTarget
- ProblemStatement
- SolutionPlan
- ImplementationPlan
- RealWorldEvidenceSummary

This makes the graph more faithful to the actual source material and improves future query quality.

# NepalReforms Tracker - Phase 1 MVP Design Specification

## Overview
The NepalReforms Tracker is a stateful, graph-powered accountability system designed to track political promises and budget execution with high fidelity. Phase 1 (MVP) focuses on mapping the Rastriya Swatantra Party (RSP) "Vacha Patra" (manifesto) against the National and Provincial Lal Kitab (Budget) for the past 2 fiscal years.

*Future phases (Phase 2+) will expand this to track individual MP promises at the constituency level.*

## 1. Architecture
*   **Backend:** Django (Python) + LangGraph for stateful agent orchestration.
*   **Database:**
    *   **Neo4j:** Stores the complex Knowledge Graph (entities, relationships, temporal status).
    *   **Supabase (PostgreSQL):** Stores relational data (user auth, raw ingestion staging, system config).
*   **Frontend:** Next.js (Dashboard + Map-centric UI).
*   **Data Extraction:** Hybrid approach combining deterministic parsers (for precise financial data) and AI agents (for semantic linking and normalization).

## 2. Knowledge Graph (Neo4j Ontology)
The Phase 1 graph focuses on the macro-level promises and budget lines.

### Core Nodes
*   `FiscalYear`: Time-bound tracking (e.g., "2080/81", "2081/82").
*   `Province`: Geographic scope (Federal/National level is also a distinct scope).
*   `Ministry`: Federal and Provincial ministries responsible for execution.
*   `Project`: Specific budget lines extracted from Lal Kitab.
*   `ManifestoPromise`: Specific commitments extracted from RSP documents and citizen demands.
*   `Evidence`: Corroborating documents, verified media reports, or verified citizen ground reports.

### Key Relationships
*   `(Project)-[:FUNDED_IN]->(FiscalYear)`
*   `(Project)-[:LOCATED_IN]->(Province)`
*   `(Project)-[:MANAGED_BY]->(Ministry)`
*   `(Project)-[:FULFILLS {impact_weight: Float}]->(ManifestoPromise)` (The Accountability Link)
*   `(Evidence)-[:VERIFIES_STATUS {status: "ACTIVE|DONE|DELAYED", confidence: Float}]->(Project)`

## 3. AI Orchestration Pipeline (LangGraph)
A stateful workflow manages data from raw source to verified graph node:

1.  **Ingestion Agent:** Reads Lal Kitab PDFs, RSP "Vacha Patra", and Citizen Oracle staging data.
2.  **Deterministic Parser:** Extracts precise financial digits and tables from Lal Kitab using standard parsing libraries (preventing LLM financial hallucinations).
3.  **Label/Normalize Agent:** Translates and standardizes bilingual (Nepali/English) project names.
4.  **Dedup Agent:** Identifies and links duplicate entries across different data sources.
5.  **Linking Agent (Semantic):** Proposes relationships between Budget Lines (`Project`) and `ManifestoPromise` nodes.
6.  **Verification Gate (Human-in-the-Loop):** **CRITICAL PATH.** All AI-proposed links and status updates must be reviewed and approved by a human editor before graph insertion.
7.  **Citizen Oracle Agent:** Aggregates raw Tier C (WhatsApp/Viber) data into summarized "Clusters" within a staging area, awaiting volunteer review.
8.  **Publisher Agent:** Commits the final, human-verified data to Neo4j and triggers Next.js frontend cache invalidations.

## 4. Trust Tiers & Data Routing
*   **Tier A (Government Docs / Lal Kitab):** Direct impact on status, high confidence.
*   **Tier B (Verified Media):** Requires 2+ corroborating sources or human approval to impact status.
*   **Tier C (Citizen Oracle):** Staged and summarized. Only enters the Tracker Graph after human verification.
*   **Routing Logic:** Unverified or broad Citizen Oracle demands are routed to the public "Demands Board" (nepalreforms.com) based on thresholds (Local >= 50, National >= 200). Verified factual updates go to the Tracker Graph (tracker.nepalreforms.com).

## 5. Security & Safety
*   **Defamation Safety:** Sensitive claims from Tier C remain isolated and unverified until human review.
*   **Audit Trail:** Every status change in Neo4j includes metadata about the `Evidence` node that triggered it and the human editor who approved it.

## 6. Success Criteria (Phase 1 MVP)
1.  **Coverage:** 100% of the RSP "Vacha Patra" promises mapped into the graph.
2.  **Accuracy:** 0 "Financial Hallucinations" (ensured via deterministic parsing).
3.  **Accountability:** A complete, queryable provenance trail for every graph edge and status change.

"""
Neo4j Knowledge Graph Ontology for NepalReforms Tracker.

Defines 6 core node types and their relationships per the design spec:
  FiscalYear, Province, Ministry, Project, ManifestoPromise, Evidence

Relationships:
  (Project)-[:FUNDED_IN]->(FiscalYear)
  (Project)-[:LOCATED_IN]->(Province)
  (Project)-[:MANAGED_BY]->(Ministry)
  (ManifestoPromise)-[:FULFILLED_BY {impact_weight}]->(Project)
  (Evidence)-[:VERIFIES_STATUS {status, confidence}]->(Project)

All nodes include created_at / updated_at for temporal auditing.
"""

from neomodel import (
    StructuredNode,
    StringProperty,
    IntegerProperty,
    FloatProperty,
    RelationshipTo,
    UniqueIdProperty,
    DateTimeProperty,
    StructuredRel,
    db,
)
from datetime import datetime


# ── Relationship Models (for properties on edges) ──────────────────────

class FulfillsRel(StructuredRel):
    """Edge properties for ManifestoPromise -[:FULFILLED_BY]-> Project."""
    impact_weight = FloatProperty(default=1.0)
    created_at = DateTimeProperty(default_now=True)


class VerifiesRel(StructuredRel):
    """Edge properties for Evidence -[:VERIFIES_STATUS]-> Project."""
    status = StringProperty(default="PENDING")  # PENDING | ACTIVE | DONE | DELAYED
    confidence = FloatProperty(default=0.0)
    created_at = DateTimeProperty(default_now=True)


# ── Base Node (temporal fields for all nodes) ──────────────────────────

class TemporalMixin:
    """Mixin that adds created_at and updated_at to every node."""
    created_at = DateTimeProperty(default_now=True)
    updated_at = DateTimeProperty(default_now=True)

    def save(self):
        self.updated_at = datetime.utcnow()
        return super().save()


# ── Node Models ────────────────────────────────────────────────────────

class FiscalYear(TemporalMixin, StructuredNode):
    uid = UniqueIdProperty()
    year = StringProperty(unique_index=True, required=True)  # e.g. "2081/82"


class Province(TemporalMixin, StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True, required=True)
    name_ne = StringProperty()


class Ministry(TemporalMixin, StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True, required=True)
    name_ne = StringProperty()
    level = StringProperty(default="federal")  # "federal" | "provincial"


class Project(TemporalMixin, StructuredNode):
    uid = UniqueIdProperty()
    fingerprint = StringProperty(unique_index=True)
    title = StringProperty(required=True, index=True)
    title_ne = StringProperty(index=True)
    budget = IntegerProperty(default=0)
    page_num = IntegerProperty()
    source_document = StringProperty()
    source_path = StringProperty()
    source_hash = StringProperty()
    budget_source = StringProperty(default="deterministic")
    budget_hash = StringProperty()  # SHA-256 of raw budget cell
    gov_level = StringProperty(default="federal")
    translation_confidence = FloatProperty(default=1.0)
    ingest_confidence = FloatProperty(default=0.0)

    # Status tracking: lifecycle of a project in the graph
    status = StringProperty(default="active")  # active | revised | superseded

    located_in = RelationshipTo("Province", "LOCATED_IN")
    funded_in = RelationshipTo("FiscalYear", "FUNDED_IN")
    managed_by = RelationshipTo("Ministry", "MANAGED_BY")


class ManifestoPromise(TemporalMixin, StructuredNode):
    uid = UniqueIdProperty()
    text = StringProperty(required=True, index=True)
    text_ne = StringProperty(index=True)
    category = StringProperty(index=True)
    source_document = StringProperty()

    fulfilled_by = RelationshipTo("Project", "FULFILLED_BY", model=FulfillsRel)


class Evidence(TemporalMixin, StructuredNode):
    uid = UniqueIdProperty()
    description = StringProperty(required=True)
    source_url = StringProperty()
    tier = StringProperty(required=True)  # "A" | "B" | "C"
    confidence = FloatProperty(default=0.0)
    verified_by = StringProperty()  # human editor who approved
    verified_at = DateTimeProperty()

    verifies = RelationshipTo("Project", "VERIFIES_STATUS", model=VerifiesRel)


# ── Neo4j Constraint Installation ──────────────────────────────────────


def install_constraints():
    """
    Install Neo4j UNIQUE constraints and indexes.

    neomodel's unique_index=True creates indexes but not always enforces
    UNIQUE constraints at the database level. This function ensures
    database-level enforcement.

    Call this once during deployment or via management command.
    """
    constraints = [
        # Uniqueness constraints (also creates indexes)
        "CREATE CONSTRAINT project_uid IF NOT EXISTS FOR (p:Project) REQUIRE p.uid IS UNIQUE",
        "CREATE CONSTRAINT project_fingerprint IF NOT EXISTS FOR (p:Project) REQUIRE p.fingerprint IS UNIQUE",
        "CREATE CONSTRAINT fy_year IF NOT EXISTS FOR (f:FiscalYear) REQUIRE f.year IS UNIQUE",
        "CREATE CONSTRAINT province_name IF NOT EXISTS FOR (p:Province) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT ministry_name IF NOT EXISTS FOR (m:Ministry) REQUIRE m.name IS UNIQUE",
        "CREATE CONSTRAINT promise_uid IF NOT EXISTS FOR (m:ManifestoPromise) REQUIRE m.uid IS UNIQUE",
        "CREATE CONSTRAINT evidence_uid IF NOT EXISTS FOR (e:Evidence) REQUIRE e.uid IS UNIQUE",
    ]

    indexes = [
        # Composite and text indexes for search performance
        "CREATE TEXT INDEX project_title_text IF NOT EXISTS FOR (p:Project) ON (p.title)",
        "CREATE TEXT INDEX project_title_ne_text IF NOT EXISTS FOR (p:Project) ON (p.title_ne)",
        "CREATE TEXT INDEX promise_text_text IF NOT EXISTS FOR (m:ManifestoPromise) ON (m.text)",
        "CREATE INDEX project_status IF NOT EXISTS FOR (p:Project) ON (p.status)",
        "CREATE INDEX project_budget IF NOT EXISTS FOR (p:Project) ON (p.budget)",
    ]

    installed = 0
    for stmt in constraints + indexes:
        try:
            db.cypher_query(stmt)
            installed += 1
        except Exception as e:
            # Constraint may already exist
            if "already exists" not in str(e).lower():
                raise
    return installed

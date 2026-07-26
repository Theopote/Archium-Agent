"""Project Aggregate Map (DOM-023).

``Project`` is the **only** architectural identity root. New capabilities must
attach via ``project_id`` (or documented child FKs), not invent a second
long-lived Project entity / table.

Allowed ``*Project*`` type names in ``archium.domain`` are listed below.
Forbidden stems reject parallel identity (LogicalProject, WorkspaceProject,
ResearchProject, CadProject, BimProject, VisualProject, …).

Non-identity views (allowed outside domain identity):
- ``ProjectOverview`` (UI DTO)
- ``ProjectContextBundle`` (RAG DTO)
- ``ArchitecturalAsset`` / ``DesignArtifact`` (facades / VOs, not Project twins)
"""

from __future__ import annotations

# Branches of the formal aggregate map (documentation + guard vocabulary).
PROJECT_AGGREGATE_BRANCHES: tuple[str, ...] = (
    "cognition",  # KnowledgeState → ProjectContext (derived)
    "process",  # ProjectProcessBoard (derived pointers)
    "knowledge",  # Fact / KnowledgeItem / Document / Asset
    "design",  # Session → ConceptDirection → Mission.DesignIntent
    "memory",  # IntentEvolution / ProjectEvent / KS History
    "delivery",  # Presentation… (reporting BC; must not redefine Project)
)

# Domain types whose names contain "Project" and are allowed satellites / enums.
ALLOWED_PROJECT_TYPE_NAMES: frozenset[str] = frozenset(
    {
        "Project",
        "ProjectArchitectureCase",
        "ProjectContext",
        "ProjectDomain",
        "ProjectEvent",
        "ProjectEventActor",
        "ProjectEventType",
        "ProjectFact",
        "ProjectInvite",
        "ProjectKnowledgeItem",
        "ProjectLifecycleStage",
        "ProjectLLMTier",
        "ProjectMember",
        "ProjectMission",
        "ProjectOriginMode",
        "ProjectPermission",
        "ProjectProcessBoard",
        "ProjectProcessKind",
        "ProjectProcessPhase",
        "ProjectRole",
        "ProjectStage",
        "ProjectStatus",
        "ProjectType",
        # Acceptance / phase profiles (metrics DTOs, not identity roots)
        "Phase7ProjectProfile",
        "RealProjectAcceptanceMetrics",
        "RealProjectAcceptanceRecord",
        "RealProjectScenario",
    }
)

# Stems that must never appear as a new long-lived identity class name.
FORBIDDEN_PROJECT_IDENTITY_STEMS: frozenset[str] = frozenset(
    {
        "LogicalProject",
        "WorkspaceProject",
        "ResearchProject",
        "CadProject",
        "BimProject",
        "VisualProject",
        "DeliveryProject",
        "StudioProject",
        "TenantProject",
    }
)

# Only identity table is ``projects``; children use ``project_*`` prefixes.
PROJECT_IDENTITY_TABLENAME = "projects"
ALLOWED_PROJECT_TABLENAME_PREFIXES: tuple[str, ...] = (
    "projects",
    "project_",
)

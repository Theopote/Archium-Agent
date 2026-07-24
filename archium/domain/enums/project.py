"""Domain enumerations — project bounded context (DOM-018)."""

from enum import StrEnum


class ProjectType(StrEnum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    OFFICE = "office"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    CULTURE = "culture"
    INDUSTRIAL = "industrial"
    URBAN_DESIGN = "urban_design"
    URBAN_RENEWAL = "urban_renewal"
    LANDSCAPE = "landscape"
    INTERIOR = "interior"
    MIXED_USE = "mixed_use"
    OTHER = "other"

class ProjectStage(StrEnum):
    RESEARCH = "research"
    CONCEPT = "concept"
    SCHEMATIC = "schematic"
    DESIGN_DEVELOPMENT = "design_development"
    CONSTRUCTION_DOCUMENT = "construction_document"
    CONSTRUCTION = "construction"
    POST_OCCUPANCY = "post_occupancy"

class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETING = "deleting"
    DELETED = "deleted"


class ProjectOriginMode(StrEnum):
    """How the project was started — drives default planning and navigation."""

    CONCEPT_EXPLORATION = "concept_exploration"
    EXISTING_PROJECT = "existing_project"
    RESEARCH_PROGRAMMING = "research_programming"

    @property
    def skips_default_clarification(self) -> bool:
        """Origins that default to lightweight planning without a materials gate."""
        return self in {
            ProjectOriginMode.CONCEPT_EXPLORATION,
            ProjectOriginMode.RESEARCH_PROGRAMMING,
        }

    @property
    def allows_outline_without_materials(self) -> bool:
        return self.skips_default_clarification


class ArchitecturalWorkspaceMode(StrEnum):
    """Product workspace mode — how the current project should feel in the UI.

    Distinct from :class:`ProjectOriginMode`: origin is how the project started;
    workspace mode is the active work posture (may elevate to design iteration).
    """

    EXISTING_PROJECT = "existing_project"
    CONCEPT_EXPLORATION = "concept_exploration"
    RESEARCH_PROGRAMMING = "research_programming"
    DESIGN_ITERATION = "design_iteration"

class ProjectDomain(StrEnum):
    """Subject domain of the task — background context, not workflow driver."""

    ARCHITECTURE = "architecture"
    URBAN = "urban"
    LANDSCAPE = "landscape"
    INTERIOR = "interior"
    HERITAGE = "heritage"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    CULTURE = "culture"
    HOUSING = "housing"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    TRANSPORT = "transport"
    SUSTAINABILITY = "sustainability"
    OPERATIONS = "operations"
    OTHER = "other"

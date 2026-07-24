"""Domain enumerations — mission bounded context (DOM-018)."""

from enum import StrEnum


class TaskNature(StrEnum):
    """Nature of the architectural task — distinct from :class:`ProjectType`."""

    NEW_BUILD = "new_build"
    RENOVATION = "renovation"
    ADAPTIVE_REUSE = "adaptive_reuse"
    EXPANSION = "expansion"
    RECONSTRUCTION = "reconstruction"
    RESTORATION = "restoration"
    CONSERVATION = "conservation"
    URBAN_RENEWAL = "urban_renewal"
    RESEARCH = "research"
    PLANNING = "planning"
    CONSULTING = "consulting"
    ASSESSMENT = "assessment"
    STRATEGY = "strategy"
    DESIGN_REVIEW = "design_review"
    PRESENTATION_SYNTHESIS = "presentation_synthesis"
    TECHNICAL_STUDY = "technical_study"
    OTHER = "other"

class InterventionScale(StrEnum):
    REGION = "region"
    CITY = "city"
    DISTRICT = "district"
    CAMPUS = "campus"
    VILLAGE = "village"
    SITE = "site"
    BUILDING_COMPLEX = "building_complex"
    BUILDING = "building"
    FLOOR = "floor"
    SPACE = "space"
    COMPONENT = "component"
    SYSTEM = "system"

class ServiceDepth(StrEnum):
    """Depth of professional service requested — not traditional design phase."""

    TASK_INTERPRETATION = "task_interpretation"
    INFORMATION_COLLECTION = "information_collection"
    PRELIMINARY_RESEARCH = "preliminary_research"
    PROJECT_DIAGNOSIS = "project_diagnosis"
    FEASIBILITY = "feasibility"
    PROGRAMMING = "programming"
    CONCEPT_PLANNING = "concept_planning"
    CONCEPT_DESIGN = "concept_design"
    SCHEMATIC_SUPPORT = "schematic_support"
    CASE_STUDY = "case_study"
    TECHNICAL_PROPOSAL = "technical_proposal"
    IMPLEMENTATION_STRATEGY = "implementation_strategy"
    DECISION_SUPPORT = "decision_support"
    PRESENTATION_PRODUCTION = "presentation_production"

class UncertaintyLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class EffortLevel(StrEnum):
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTENSIVE = "extensive"

class ConstraintSource(StrEnum):
    USER = "user"
    DOCUMENT = "document"
    REGULATION = "regulation"
    SITE = "site"
    BUDGET = "budget"
    SCHEDULE = "schedule"
    OPERATION = "operation"
    ASSUMPTION = "assumption"
    OTHER = "other"

class WorkstreamType(StrEnum):
    TASK_INTERPRETATION = "task_interpretation"
    DOCUMENT_REVIEW = "document_review"
    SITE_ANALYSIS = "site_analysis"
    HISTORICAL_RESEARCH = "historical_research"
    USER_RESEARCH = "user_research"
    CASE_STUDY = "case_study"
    REGULATION_REVIEW = "regulation_review"
    PROGRAMMING = "programming"
    FUNCTIONAL_ANALYSIS = "functional_analysis"
    CIRCULATION_ANALYSIS = "circulation_analysis"
    TECHNICAL_STUDY = "technical_study"
    SUSTAINABILITY = "sustainability"
    DESIGN_STRATEGY = "design_strategy"
    IMPLEMENTATION = "implementation"
    COST_AND_PHASE = "cost_and_phase"
    RISK_REVIEW = "risk_review"
    PRESENTATION = "presentation"
    OTHER = "other"

class WorkstreamStatus(StrEnum):
    PROPOSED = "proposed"
    SELECTED = "selected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

class DeliverableType(StrEnum):
    PRESENTATION = "presentation"
    REPORT = "report"
    MEMO = "memo"
    CHECKLIST = "checklist"
    CASE_STUDY = "case_study"
    TASK_BRIEF = "task_brief"
    DESIGN_BRIEF = "design_brief"
    TECHNICAL_PROPOSAL = "technical_proposal"
    RISK_REGISTER = "risk_register"
    QUESTION_LIST = "question_list"
    WORK_PLAN = "work_plan"
    IMPLEMENTATION_ROADMAP = "implementation_roadmap"
    OTHER = "other"


class ArtifactJobStatus(StrEnum):
    """Lifecycle for non-presentation artifact generation jobs."""

    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConceptDirectionStatus(StrEnum):
    """Lifecycle for concept design-iteration direction drafts."""

    DRAFT = "draft"
    SELECTED = "selected"
    ARCHIVED = "archived"

"""Domain enumerations."""

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


class DocumentType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    IMAGE = "image"
    OTHER = "other"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_OCR = "needs_ocr"


class VerificationStatus(StrEnum):
    EXTRACTED = "extracted"
    INFERRED = "inferred"
    USER_CONFIRMED = "user_confirmed"
    CONFLICTED = "conflicted"
    REJECTED = "rejected"


class InformationOrigin(StrEnum):
    """Provenance of a knowledge item or claim."""

    USER_UPLOAD = "user_upload"
    USER_CONFIRMED = "user_confirmed"
    PUBLIC_RESEARCH = "public_research"
    SYSTEM_INFERENCE = "system_inference"
    REFERENCE_CASE = "reference_case"


class InformationReliability(StrEnum):
    """Confidence tier for a knowledge item used in generation gating."""

    CONFIRMED = "confirmed"
    HIGH_CONFIDENCE = "high_confidence"
    UNVERIFIED = "unverified"
    INFERENCE = "inference"
    CONFLICTING = "conflicting"


class DocumentPurpose(StrEnum):
    """Role of an imported document in project knowledge."""

    PROJECT_MATERIAL = "project_material"
    REFERENCE_CASE = "reference_case"
    REFERENCE_STYLE = "reference_style"
    POLICY = "policy"
    PUBLIC_RESEARCH = "public_research"


class KnowledgeItemStatus(StrEnum):
    """Lifecycle status for a project knowledge item."""

    ACTIVE = "active"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class OutlineAudienceMode(StrEnum):
    """Audience profile affecting outline structure and emphasis."""

    GOVERNMENT = "government"
    CLIENT = "client"
    EXPERT_REVIEW = "expert_review"
    COMMUNITY = "community"
    INVESTOR = "investor"
    CULTURE_TOURISM = "culture_tourism"
    INTERNAL_DESIGN = "internal_design"


class PresentationType(StrEnum):
    CONCEPT = "concept"
    SCHEMATIC = "schematic"
    DESIGN_DEVELOPMENT = "design_development"
    CLIENT_REVIEW = "client_review"
    COMPETITION = "competition"
    INTERNAL = "internal"
    OTHER = "other"


class PresentationStatus(StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    APPROVED = "approved"
    EXPORTED = "exported"
    ARCHIVED = "archived"


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SlideType(StrEnum):
    TITLE = "title"
    SECTION = "section"
    CONTENT = "content"
    IMAGE = "image"
    COMPARISON = "comparison"
    TIMELINE = "timeline"
    DATA = "data"
    SUMMARY = "summary"
    CLOSING = "closing"


class SlideStatus(StrEnum):
    DRAFT = "draft"
    PLANNED = "planned"
    APPROVED = "approved"
    RENDERED = "rendered"
    NEEDS_REVISION = "needs_revision"


class RevisionSource(StrEnum):
    """Origin of an entity revision — shared by slides, briefs, missions, plans, etc."""

    GENERATED = "generated"
    MANUAL_EDIT = "manual_edit"
    REGENERATION = "regeneration"
    AUTO_REPAIR = "auto_repair"
    CLARIFICATION = "clarification"
    APPROVAL = "approval"
    IMPORT = "import"


# Backward-compatible alias; prefer RevisionSource for new code.
SlideChangeSource = RevisionSource


class SlideRepairTier(StrEnum):
    """Graduated auto-repair strategy (least to most invasive)."""

    SHORTEN_REPETITION = "shorten_repetition"
    REWRITE = "rewrite"
    SPLIT = "split"
    USER_CONFIRMATION = "user_confirmation"


class SlideRepairSource(StrEnum):
    """Origin of an automated slide repair action."""

    RULE = "rule"
    LLM = "llm"


class RevisionEntityType(StrEnum):
    BRIEF = "brief"
    STORYLINE = "storyline"
    OUTLINE = "outline"
    CULTURAL_NARRATIVE = "cultural_narrative"
    RENOVATION_ISSUE_MAP = "renovation_issue_map"
    REFERENCE_STYLE_PROFILE = "reference_style_profile"
    SLIDE = "slide"
    ASSET_ASSIGNMENT = "asset_assignment"
    PRESENTATION_THEME = "presentation_theme"
    MISSION = "mission"
    WORKSTREAM_PLAN = "workstream_plan"
    DELIVERABLE_PLAN = "deliverable_plan"
    ASSUMPTION = "assumption"
    DESIGN_SYSTEM = "design_system"
    ART_DIRECTION = "art_direction"
    VISUAL_INTENT = "visual_intent"
    LAYOUT_PLAN = "layout_plan"
    HUMAN_VISUAL_REVIEW = "human_visual_review"


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


class KnowledgeGapCategory(StrEnum):
    PROJECT_SCOPE = "project_scope"
    SITE = "site"
    AREA = "area"
    PROGRAM = "program"
    USER_NEEDS = "user_needs"
    REGULATION = "regulation"
    HISTORY = "history"
    OPERATION = "operation"
    BUDGET = "budget"
    SCHEDULE = "schedule"
    STAKEHOLDER = "stakeholder"
    TECHNICAL = "technical"
    DELIVERABLE = "deliverable"
    OTHER = "other"


class KnowledgeGapStatus(StrEnum):
    OPEN = "open"
    ASSUMED = "assumed"
    ANSWERED = "answered"
    DEFERRED = "deferred"
    NOT_APPLICABLE = "not_applicable"


class ResolutionMethod(StrEnum):
    USER_INPUT = "user_input"
    DOCUMENT_REVIEW = "document_review"
    SITE_VISIT = "site_visit"
    STAKEHOLDER_INTERVIEW = "stakeholder_interview"
    RESEARCH = "research"
    ASSUMPTION = "assumption"
    DEFER = "defer"
    OTHER = "other"


class AssumptionStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    CONFIRMED = "confirmed"


class QuestionAnswerType(StrEnum):
    TEXT = "text"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    BOOLEAN = "boolean"
    NUMBER = "number"


class QuestionStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    DEFERRED = "deferred"
    ASSUMED = "assumed"
    NOT_APPLICABLE = "not_applicable"


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


class VisualType(StrEnum):
    SITE_PLAN = "site_plan"
    FLOOR_PLAN = "floor_plan"
    SECTION = "section"
    ELEVATION = "elevation"
    RENDERING = "rendering"
    SITE_PHOTO = "site_photo"
    DIAGRAM = "diagram"
    CHART = "chart"
    TABLE = "table"
    TIMELINE = "timeline"
    COMPARISON = "comparison"
    REFERENCE_CASE = "reference_case"
    ICON = "icon"
    MAP = "map"
    TEXT_ONLY = "text_only"


class AssetType(StrEnum):
    IMAGE = "image"
    DRAWING = "drawing"
    DIAGRAM = "diagram"
    PHOTO = "photo"
    CHART = "chart"
    OTHER = "other"


class PipelineRole(StrEnum):
    """Logical pipeline roles — annotation vocabulary, not runtime Agent classes.

    See ``docs/architecture/pipeline-roles.md``. Services and workflow nodes
    implement these roles; do not add one Agent class per role.
    """

    RESEARCH = "research"
    NARRATIVE = "narrative"
    ARCHITECTURE = "architecture"
    COMPOSITION = "composition"
    LAYOUT = "layout"
    RENDER = "render"
    CRITIC = "critic"


class ReviewLayer(StrEnum):
    CONTENT = "content"
    EVIDENCE = "evidence"
    ARCHITECTURAL = "architectural"
    LAYOUT = "layout"
    SEMANTIC = "semantic"


class ReviewCategory(StrEnum):
    CITATION = "citation"
    CONTENT = "content"
    STRUCTURE = "structure"
    VISUAL = "visual"
    CONSISTENCY = "consistency"
    COVERAGE = "coverage"
    LENGTH = "length"
    OTHER = "other"


class ReviewSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    SUGGESTION = "suggestion"


class ValidationSeverity(StrEnum):
    """Severity for MissionValidationIssue (mission planning, not slide review)."""

    FATAL = "fatal"
    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class ReviewStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlanningSessionStatus(StrEnum):
    """Lifecycle of a mission-first planning session (not a Presentation)."""

    DRAFT = "draft"
    CLARIFYING = "clarifying"
    PLANNING = "planning"
    AWAITING_MISSION_CORRECTION = "awaiting_mission_correction"
    AWAITING_MISSION_APPROVAL = "awaiting_mission_approval"
    AWAITING_APPROVAL = "awaiting_approval"
    READY = "ready"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStep(StrEnum):
    INIT = "init"
    LOAD_PROJECT = "load_project"
    VALIDATE_SOURCES = "validate_sources"
    RETRIEVE_CONTEXT = "retrieve_context"
    EXTRACT_FACTS = "extract_facts"
    VALIDATE_FACTS = "validate_facts"
    BUILD_MANUSCRIPT = "build_manuscript"
    REVIEW_MANUSCRIPT = "review_manuscript"
    BRIEF = "brief"
    REVIEW_BRIEF = "review_brief"
    CULTURAL_NARRATIVE = "cultural_narrative"
    RENOVATION_ISSUE_MAP = "renovation_issue_map"
    REFERENCE_STYLE_PROFILE = "reference_style_profile"
    STORYLINE = "storyline"
    REVIEW_STORYLINE = "review_storyline"
    OUTLINE = "outline"
    REVIEW_OUTLINE = "review_outline"
    REVIEW_SLIDES = "review_slides"
    SLIDES = "slides"
    RESOLVE_CITATIONS = "resolve_citations"
    MATCH_ASSETS = "match_assets"
    CONTENT_REVIEW = "content_review"
    EVIDENCE_REVIEW = "evidence_review"
    ARCHITECTURAL_REVIEW = "architectural_review"
    LAYOUT_REVIEW = "layout_review"
    PROFESSIONAL_REVIEW = "professional_review"
    REPAIR_SLIDES = "repair_slides"
    SLIDE_VALIDATION = "slide_validation"
    EXPORT = "export"
    PRESENTATION_SPEC = "presentation_spec"
    MARP = "marp"
    FINALIZE = "finalize"
    FAILED = "failed"
    # Planning workflow (mission-first chain; not presentation Stage renumbering)
    PLANNING_LOAD_CONTEXT = "planning_load_context"
    PLANNING_ANALYZE_TASK = "planning_analyze_task"
    PLANNING_VALIDATE_MISSION = "planning_validate_mission"
    PLANNING_AWAIT_MISSION_CORRECTION = "planning_await_mission_correction"
    PLANNING_AWAIT_CLARIFICATION = "planning_await_clarification"
    PLANNING_REVISE_MISSION = "planning_revise_mission"
    PLANNING_VALIDATE_REVISED_MISSION = "planning_validate_revised_mission"
    PLANNING_AWAIT_MISSION_APPROVAL = "planning_await_mission_approval"
    PLANNING_WORKSTREAMS = "planning_workstreams"
    PLANNING_DELIVERABLES = "planning_deliverables"
    PLANNING_AWAIT_APPROVAL = "planning_await_approval"
    PLANNING_PREPARE_ARTIFACTS = "planning_prepare_artifacts"
    # Legacy alias — old checkpoints may still store this string.
    PLANNING_PREPARE_PRESENTATION = "planning_prepare_presentation"
    PLANNING_FINALIZE = "planning_finalize"
    # Visual composition workflow (independent of presentation generation chain)
    VISUAL_LOAD_CONTEXT = "visual_load_context"
    VISUAL_LOAD_DESIGN_SYSTEM = "visual_load_design_system"
    VISUAL_GENERATE_ART_DIRECTION = "visual_generate_art_direction"
    VISUAL_AWAIT_ART_DIRECTION_APPROVAL = "visual_await_art_direction_approval"
    VISUAL_GENERATE_INTENTS = "visual_generate_intents"
    VISUAL_GENERATE_DECK_COMPOSITION = "visual_generate_deck_composition"
    VISUAL_GENERATE_LAYOUT_CANDIDATES = "visual_generate_layout_candidates"
    VISUAL_SELECT_LAYOUTS = "visual_select_layouts"
    VISUAL_VALIDATE_LAYOUTS = "visual_validate_layouts"
    VISUAL_REPAIR_LAYOUTS = "visual_repair_layouts"
    VISUAL_APPLY_SAFE_FALLBACK = "visual_apply_safe_fallback"
    VISUAL_AWAIT_LAYOUT_REVIEW = "visual_await_layout_review"
    VISUAL_RENDER = "visual_render"
    VISUAL_CRITIQUE = "visual_critique"
    VISUAL_SCENE_REPAIR = "visual_scene_repair"
    VISUAL_FINALIZE = "visual_finalize"

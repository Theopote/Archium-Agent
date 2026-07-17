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


class SlideChangeSource(StrEnum):
    GENERATED = "generated"
    MANUAL_EDIT = "manual_edit"
    REGENERATION = "regeneration"


class RevisionEntityType(StrEnum):
    BRIEF = "brief"
    STORYLINE = "storyline"
    SLIDE = "slide"
    ASSET_ASSIGNMENT = "asset_assignment"
    PRESENTATION_THEME = "presentation_theme"


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


class ReviewLayer(StrEnum):
    CONTENT = "content"
    EVIDENCE = "evidence"
    ARCHITECTURAL = "architectural"
    LAYOUT = "layout"


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


class WorkflowStep(StrEnum):
    INIT = "init"
    LOAD_PROJECT = "load_project"
    VALIDATE_SOURCES = "validate_sources"
    RETRIEVE_CONTEXT = "retrieve_context"
    EXTRACT_FACTS = "extract_facts"
    VALIDATE_FACTS = "validate_facts"
    BRIEF = "brief"
    REVIEW_BRIEF = "review_brief"
    STORYLINE = "storyline"
    REVIEW_STORYLINE = "review_storyline"
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

"""Domain enumerations — presentation bounded context (DOM-018)."""

from enum import StrEnum

class NarrativeStage(StrEnum):
    """Position of a section/page on the deck argument arc."""

    CONTEXT = "context"
    PROBLEM = "problem"
    EVIDENCE = "evidence"
    TENSION = "tension"
    STRATEGY = "strategy"
    RESOLUTION = "resolution"
    DECISION = "decision"

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
    # Approved outline edited again — needs re-confirmation before generation.
    CHANGES_PENDING = "changes_pending"

class EvidenceAvailability(StrEnum):
    """Tri-state project materials check — never collapse query failure into bool."""

    AVAILABLE = "available"
    MISSING = "missing"
    UNKNOWN = "unknown"

class SlideType(StrEnum):
    """SlideSpec rhetorical / content-planning type.

    Not interchangeable with ``FunctionalSlideType`` or ``TemplatePageType``.
    Cross-maps: ``archium.domain.visual.page_type_catalog`` (DOM-005).
    """

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

class SlideDeliveryStatus(StrEnum):
    """Per-page delivery readiness — independent of content review lifecycle."""

    READY = "ready"
    FALLBACK_USED = "fallback_used"
    ASSET_MISSING = "asset_missing"
    RENDER_FAILED = "render_failed"
    SCHEMA_BLOCKED = "schema_blocked"
    SKIPPED = "skipped"

class DeckDeliveryStatus(StrEnum):
    """Deck-level delivery readiness — single page failure ≠ whole-deck failure."""

    READY = "ready"
    READY_WITH_FAILED_SLIDES = "ready_with_failed_slides"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"

class RevisionSource(StrEnum):
    """Origin of an entity revision — shared by slides, briefs, missions, plans, etc."""

    GENERATED = "generated"
    MANUAL_EDIT = "manual_edit"
    REGENERATION = "regeneration"
    AUTO_REPAIR = "auto_repair"
    AI_PROPOSAL = "ai_proposal"
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
    RENDER_SCENE = "render_scene"
    HUMAN_VISUAL_REVIEW = "human_visual_review"

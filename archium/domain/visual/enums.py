"""Enums for the architectural visual composition system."""

from enum import StrEnum


class DesignSystemSource(StrEnum):
    BUILTIN = "builtin"
    PROJECT = "project"
    USER = "user"
    IMPORTED = "imported"


class GridType(StrEnum):
    COLUMN = "column"
    MODULAR = "modular"
    DRAWING_CANVAS = "drawing_canvas"


class ImageFit(StrEnum):
    CONTAIN = "contain"
    COVER = "cover"
    FILL = "fill"
    NONE = "none"


class PhotoTreatment(StrEnum):
    NONE = "none"
    SUBTLE_UNIFY = "subtle_unify"
    DOCUMENT_SCAN = "document_scan"
    HISTORICAL = "historical"


class CropPolicy(StrEnum):
    NONE = "none"
    SAFE_TRIM = "safe_trim"
    COVER_CROP = "cover_crop"
    FORBIDDEN = "forbidden"


class VisualContentType(StrEnum):
    HERO_IMAGE = "hero_image"
    PHOTO_EVIDENCE = "photo_evidence"
    SITE_PLAN = "site_plan"
    FLOOR_PLAN = "floor_plan"
    SECTION = "section"
    ELEVATION = "elevation"
    ANALYTICAL_DIAGRAM = "analytical_diagram"
    PROCESS = "process"
    COMPARISON = "comparison"
    METRICS = "metrics"
    TEXT_ARGUMENT = "text_argument"
    MIXED = "mixed"


class DensityLevel(StrEnum):
    SPACIOUS = "spacious"
    BALANCED = "balanced"
    COMPACT = "compact"


class ContinuityRole(StrEnum):
    OPENING = "opening"
    SECTION_OPENING = "section_opening"
    EXPLANATION = "explanation"
    EVIDENCE = "evidence"
    COMPARISON = "comparison"
    CLIMAX = "climax"
    TRANSITION = "transition"
    SUMMARY = "summary"
    CLOSING = "closing"


class LayoutFamily(StrEnum):
    """Geometry / composition family for layout planning (DOM-006).

    Not a synonym of ``SlideType`` / Spec ``layout`` / ``TemplatePageType``.
    Coercion + aliases: ``archium.domain.visual.layout_family_normalize``.
    """

    HERO = "hero"
    EVIDENCE_BOARD = "evidence_board"
    DRAWING_FOCUS = "drawing_focus"
    COMPARATIVE_MATRIX = "comparative_matrix"
    PROCESS_NARRATIVE = "process_narrative"
    ANALYTICAL_DIAGRAM = "analytical_diagram"
    METRIC_DASHBOARD = "metric_dashboard"
    STRATEGY_CARDS = "strategy_cards"
    TEXTUAL_ARGUMENT = "textual_argument"
    HYBRID_CANVAS = "hybrid_canvas"


class LayoutElementRole(StrEnum):
    TITLE = "title"
    SUBTITLE = "subtitle"
    LEAD_STATEMENT = "lead_statement"
    HERO_VISUAL = "hero_visual"
    SUPPORTING_VISUAL = "supporting_visual"
    BODY_TEXT = "body_text"
    METRIC = "metric"
    CAPTION = "caption"
    ANNOTATION = "annotation"
    SOURCE = "source"
    FOOTER = "footer"
    PAGE_NUMBER = "page_number"
    DECORATION = "decoration"


class LayoutContentType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    DRAWING = "drawing"
    METRIC = "metric"
    CHART = "chart"
    TABLE = "table"
    SHAPE = "shape"


class OverflowPolicy(StrEnum):
    CLIP = "clip"
    SHRINK = "shrink"
    WARN = "warn"
    SPLIT = "split"


class LayoutValidationStatus(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    REPAIRED = "repaired"


class LayoutConstraintType(StrEnum):
    ALIGN_LEFT = "align_left"
    ALIGN_RIGHT = "align_right"
    ALIGN_TOP = "align_top"
    ALIGN_BOTTOM = "align_bottom"
    EQUAL_WIDTH = "equal_width"
    EQUAL_HEIGHT = "equal_height"
    MIN_GAP = "min_gap"
    CONTAIN_WITHIN_SAFE_AREA = "contain_within_safe_area"
    PRESERVE_ASPECT_RATIO = "preserve_aspect_ratio"
    NO_OVERLAP = "no_overlap"
    READING_ORDER = "reading_order"
    MIN_FONT_SIZE = "min_font_size"


class ConstraintPriority(StrEnum):
    REQUIRED = "required"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class LayoutIssueSeverity(StrEnum):
    """Layout / deck-QA finding severity. Gate mapping: ``domain.visual.severity``."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AssetVisualRole(StrEnum):
    PHOTO = "photo"
    TECHNICAL_DRAWING = "technical_drawing"
    ANALYTICAL_DIAGRAM = "analytical_diagram"
    DATA_VISUALIZATION = "data_visualization"
    HISTORICAL_DOCUMENT = "historical_document"
    DECORATIVE = "decorative"


class VisualEmphasis(StrEnum):
    IMAGE_LED = "image_led"
    DRAWING_LED = "drawing_led"
    TEXT_LED = "text_led"
    BALANCED = "balanced"


class FormalityLevel(StrEnum):
    CASUAL = "casual"
    PROFESSIONAL = "professional"
    FORMAL = "formal"
    CEREMONIAL = "ceremonial"


class DecorationLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WhitespacePreference(StrEnum):
    TIGHT = "tight"
    BALANCED = "balanced"
    GENEROUS = "generous"


class DrawingDisplayMode(StrEnum):
    CLEAR = "clear"
    ANNOTATED = "annotated"
    CONTEXTUAL = "contextual"


class PresentationContext(StrEnum):
    CLIENT_REVIEW = "client_review"
    GOVERNMENT_REVIEW = "government_review"
    DESIGN_COMPETITION = "design_competition"
    INTERNAL_CRITIQUE = "internal_critique"
    TECHNICAL_REPORT = "technical_report"
    ACADEMIC_RESEARCH = "academic_research"

"""Domain enumerations — assets bounded context (DOM-018)."""

from enum import StrEnum


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

class SlideAssetBindingRole(StrEnum):
    """User-declared role when binding a project asset to a planned page."""

    PRIMARY_DRAWING = "primary_drawing"
    PROJECT_PHOTO = "project_photo"
    SUPPORTING_PHOTO = "supporting_photo"
    REFERENCE_CASE = "reference_case"
    METRIC_SOURCE = "metric_source"
    BACKGROUND = "background"
    LOGO = "logo"

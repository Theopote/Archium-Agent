"""Architectural Graphic Asset Library — professional drawing notation.

Three tiers:
  1. Analysis symbols   — sun_path, wind_flow, pedestrian_flow, axis, threshold
  2. Drawing notation   — dimension_line, callout_box, detail_marker, north_arrow, scale_bar, section_cut
  3. Decorative texture — paper_texture, ink_bleed, blueprint_noise, sketch_overlay

Assets are metadata + SVG/icon refs; they are not absolute-coordinate geometry.
The materializer (or pptxgen adapter) resolves them to concrete shapes.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class AssetTier(StrEnum):
    ANALYSIS_SYMBOL = "analysis_symbol"
    DRAWING_NOTATION = "drawing_notation"
    DECORATIVE_TEXTURE = "decorative_texture"


class AssetPlacement(StrEnum):
    """Where on the page this asset naturally belongs."""

    CORNER = "corner"            # north_arrow, scale_bar
    EDGE = "edge"                # dimension_line along drawing
    OVERLAY = "overlay"          # wind_flow, sun_path, analysis diagrams
    BACKGROUND = "background"    # paper_texture, blueprint_noise
    INLINE = "inline"            # callout_box, detail_marker near content


class ArchitecturalAsset(DomainModel):
    """One graphic asset from the architectural drawing toolkit."""

    id: str = Field(min_length=1, max_length=64)
    tier: AssetTier
    label_zh: str = Field(max_length=32)
    label_en: str = Field(max_length=64)
    meaning: str = Field(default="", max_length=120)
    placement: AssetPlacement = AssetPlacement.OVERLAY
    icon_ref: str | None = Field(
        default=None,
        max_length=64,
        description="Bundled SVG ref (icon:xxx) or None for shape-only assets.",
    )
    default_opacity: float = Field(default=0.85, ge=0.05, le=1.0)
    default_scale: float = Field(default=1.0, ge=0.2, le=4.0)
    style_tags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "tier": self.tier.value,
            "label_zh": self.label_zh,
            "label_en": self.label_en,
            "meaning": self.meaning,
            "placement": self.placement.value,
            "icon_ref": self.icon_ref,
            "default_opacity": self.default_opacity,
            "default_scale": self.default_scale,
            "style_tags": list(self.style_tags),
        }


# ── Tier 1: Analysis Symbols ──────────────────────────────────────────

SUN_PATH = ArchitecturalAsset(
    id="sun_path",
    tier=AssetTier.ANALYSIS_SYMBOL,
    label_zh="日照分析",
    label_en="Sun Path Diagram",
    meaning="solar_access_analysis",
    placement=AssetPlacement.OVERLAY,
    icon_ref="icon:sun_path",
    default_opacity=0.6,
    style_tags=("environmental", "site_analysis"),
)

WIND_FLOW = ArchitecturalAsset(
    id="wind_flow",
    tier=AssetTier.ANALYSIS_SYMBOL,
    label_zh="风环境",
    label_en="Wind Flow",
    meaning="prevailing_wind_direction",
    placement=AssetPlacement.OVERLAY,
    icon_ref="icon:wind_flow",
    default_opacity=0.55,
    style_tags=("environmental", "site_analysis"),
)

PEDESTRIAN_FLOW = ArchitecturalAsset(
    id="pedestrian_flow",
    tier=AssetTier.ANALYSIS_SYMBOL,
    label_zh="人流分析",
    label_en="Pedestrian Flow",
    meaning="circulation_analysis",
    placement=AssetPlacement.OVERLAY,
    icon_ref="icon:pedestrian_flow",
    default_opacity=0.7,
    style_tags=("circulation", "site_analysis"),
)

BOUNDARY = ArchitecturalAsset(
    id="boundary",
    tier=AssetTier.ANALYSIS_SYMBOL,
    label_zh="用地边界",
    label_en="Site Boundary",
    meaning="property_or_zoning_limit",
    placement=AssetPlacement.OVERLAY,
    default_opacity=0.65,
    style_tags=("regulatory", "site_analysis"),
)

THRESHOLD = ArchitecturalAsset(
    id="threshold",
    tier=AssetTier.ANALYSIS_SYMBOL,
    label_zh="空间阈值",
    label_en="Spatial Threshold",
    meaning="boundary_between_zones",
    placement=AssetPlacement.OVERLAY,
    default_opacity=0.7,
    style_tags=("spatial", "circulation"),
)

AXIS = ArchitecturalAsset(
    id="axis",
    tier=AssetTier.ANALYSIS_SYMBOL,
    label_zh="空间轴线",
    label_en="Spatial Axis",
    meaning="primary_or_secondary_axis",
    placement=AssetPlacement.OVERLAY,
    default_opacity=0.5,
    style_tags=("composition", "site_analysis"),
)

GRID = ArchitecturalAsset(
    id="grid",
    tier=AssetTier.ANALYSIS_SYMBOL,
    label_zh="结构网格",
    label_en="Structural Grid",
    meaning="column_grid_or_modular_system",
    placement=AssetPlacement.OVERLAY,
    default_opacity=0.35,
    style_tags=("structural", "drawing_notation"),
)

# ── Tier 2: Drawing Notation ──────────────────────────────────────────

DIMENSION_LINE = ArchitecturalAsset(
    id="dimension_line",
    tier=AssetTier.DRAWING_NOTATION,
    label_zh="尺寸标注",
    label_en="Dimension Line",
    meaning="measured_distance",
    placement=AssetPlacement.EDGE,
    default_opacity=0.8,
    default_scale=0.8,
    style_tags=("precise", "technical"),
)

CALLOUT_BOX = ArchitecturalAsset(
    id="callout_box",
    tier=AssetTier.DRAWING_NOTATION,
    label_zh="标注框",
    label_en="Callout Box",
    meaning="annotation_pointer",
    placement=AssetPlacement.INLINE,
    default_opacity=0.9,
    style_tags=("annotation", "technical"),
)

DETAIL_MARKER = ArchitecturalAsset(
    id="detail_marker",
    tier=AssetTier.DRAWING_NOTATION,
    label_zh="详图标记",
    label_en="Detail Marker",
    meaning="detail_reference_circle",
    placement=AssetPlacement.INLINE,
    default_opacity=0.85,
    default_scale=0.7,
    style_tags=("reference", "technical"),
)

NORTH_ARROW = ArchitecturalAsset(
    id="north_arrow",
    tier=AssetTier.DRAWING_NOTATION,
    label_zh="指北针",
    label_en="North Arrow",
    meaning="orientation_indicator",
    placement=AssetPlacement.CORNER,
    icon_ref="icon:north_arrow",
    default_opacity=0.7,
    default_scale=0.6,
    style_tags=("orientation", "site"),
)

SCALE_BAR = ArchitecturalAsset(
    id="scale_bar",
    tier=AssetTier.DRAWING_NOTATION,
    label_zh="比例尺",
    label_en="Scale Bar",
    meaning="graphic_scale_reference",
    placement=AssetPlacement.CORNER,
    default_opacity=0.65,
    default_scale=0.7,
    style_tags=("scale", "technical"),
)

SECTION_CUT = ArchitecturalAsset(
    id="section_cut",
    tier=AssetTier.DRAWING_NOTATION,
    label_zh="剖切线",
    label_en="Section Cut Line",
    meaning="cross_section_indicator",
    placement=AssetPlacement.OVERLAY,
    default_opacity=0.75,
    style_tags=("section", "technical"),
)

# ── Tier 3: Decorative Texture ────────────────────────────────────────

PAPER_TEXTURE = ArchitecturalAsset(
    id="paper_texture",
    tier=AssetTier.DECORATIVE_TEXTURE,
    label_zh="纸质肌理",
    label_en="Paper Texture",
    meaning="tactile_craft_quality",
    placement=AssetPlacement.BACKGROUND,
    default_opacity=0.08,
    style_tags=("craft", "atmosphere"),
)

INK_BLEED = ArchitecturalAsset(
    id="ink_bleed",
    tier=AssetTier.DECORATIVE_TEXTURE,
    label_zh="墨迹渗透",
    label_en="Ink Bleed",
    meaning="hand_drawn_authenticity",
    placement=AssetPlacement.BACKGROUND,
    default_opacity=0.06,
    style_tags=("craft", "atmosphere"),
)

BLUEPRINT_NOISE = ArchitecturalAsset(
    id="blueprint_noise",
    tier=AssetTier.DECORATIVE_TEXTURE,
    label_zh="蓝图噪点",
    label_en="Blueprint Noise",
    meaning="technical_drawing_heritage",
    placement=AssetPlacement.BACKGROUND,
    default_opacity=0.1,
    style_tags=("heritage", "atmosphere"),
)

SKETCH_OVERLAY = ArchitecturalAsset(
    id="sketch_overlay",
    tier=AssetTier.DECORATIVE_TEXTURE,
    label_zh="手绘叠加",
    label_en="Sketch Overlay",
    meaning="concept_stage_looseness",
    placement=AssetPlacement.BACKGROUND,
    default_opacity=0.12,
    style_tags=("concept", "atmosphere"),
)


# ── Registry ──────────────────────────────────────────────────────────

_ASSET_CATALOG: dict[str, ArchitecturalAsset] = {
    a.id: a
    for a in (
        # Tier 1
        SUN_PATH, WIND_FLOW, PEDESTRIAN_FLOW, BOUNDARY, THRESHOLD, AXIS, GRID,
        # Tier 2
        DIMENSION_LINE, CALLOUT_BOX, DETAIL_MARKER, NORTH_ARROW, SCALE_BAR, SECTION_CUT,
        # Tier 3
        PAPER_TEXTURE, INK_BLEED, BLUEPRINT_NOISE, SKETCH_OVERLAY,
    )
}


def get_asset(asset_id: str) -> ArchitecturalAsset | None:
    return _ASSET_CATALOG.get(asset_id)


def list_assets(*, tier: AssetTier | None = None) -> list[ArchitecturalAsset]:
    if tier is None:
        return list(_ASSET_CATALOG.values())
    return [a for a in _ASSET_CATALOG.values() if a.tier == tier]


def assets_for_formula(formula_id: str) -> list[ArchitecturalAsset]:
    """Suggest assets based on page grammar formula."""
    _FORMULA_ASSETS: dict[str, list[str]] = {
        "site_layer_analysis": ["sun_path", "wind_flow", "pedestrian_flow", "boundary", "north_arrow"],
        "masterplan_focus": ["north_arrow", "scale_bar", "axis", "grid", "boundary"],
        "axonometric_callout": ["callout_box", "detail_marker", "dimension_line", "section_cut"],
        "evidence_comparison": ["dimension_line", "callout_box", "pedestrian_flow"],
        "hero_atmosphere": ["paper_texture", "sketch_overlay"],
        "phasing_timeline": ["dimension_line", "threshold", "axis"],
        "section_opener": ["blueprint_noise"],
        "drawing_plus_analysis": ["north_arrow", "scale_bar", "callout_box"],
        "photo_plus_analysis": ["pedestrian_flow", "boundary", "callout_box"],
    }
    ids = _FORMULA_ASSETS.get(formula_id, [])
    return [_ASSET_CATALOG[aid] for aid in ids if aid in _ASSET_CATALOG]


def assets_for_slide_context(
    *,
    title: str = "",
    has_drawing: bool = False,
    has_site_plan: bool = False,
    has_section: bool = False,
) -> list[ArchitecturalAsset]:
    """Context-based asset suggestion (lightweight heuristic)."""
    out: list[ArchitecturalAsset] = []
    title_lower = title.lower()

    if has_site_plan or "区位" in title or "总图" in title or "site" in title_lower:
        out.extend([NORTH_ARROW, SCALE_BAR])
    if has_drawing or has_site_plan:
        out.append(DIMENSION_LINE)
    if has_section or "剖" in title or "section" in title_lower:
        out.append(SECTION_CUT)
    if "日照" in title or "sun" in title_lower:
        out.append(SUN_PATH)
    if "风" in title or "wind" in title_lower:
        out.append(WIND_FLOW)
    if "流线" in title or "交通" in title or "circulation" in title_lower:
        out.append(PEDESTRIAN_FLOW)

    # Deduplicate preserving order.
    seen: set[str] = set()
    unique: list[ArchitecturalAsset] = []
    for a in out:
        if a.id not in seen:
            seen.add(a.id)
            unique.append(a)
    return unique

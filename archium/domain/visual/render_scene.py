"""RenderScene — unified final visual scene for all renderers.

Supports Text / Image / Drawing / Shape plus optional Chart / Table nodes for
dual chart-export strategy (``ChartExportMode``). Chart/Table nodes carry
structured data so exporters can choose cross-app stable shapes/images or
native PowerPoint Chart/Table objects with embedded workbooks.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel


class BoxSpacing(DomainModel):
    top: float = 0
    right: float = 0
    bottom: float = 0
    left: float = 0


class CropBox(DomainModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class Point(DomainModel):
    x: float
    y: float


class BorderStyle(DomainModel):
    color: str
    width: float = Field(gt=0)


class ShadowStyle(DomainModel):
    color: str = "#00000033"
    offset_x: float = 0
    offset_y: float = 2
    blur: float = 4


class TextParagraph(DomainModel):
    text: str
    alignment: str = "left"


class BackgroundStyle(DomainModel):
    color: str
    image_asset_path: str | None = None


class ThemeTokens(DomainModel):
    colors: dict[str, str] = Field(default_factory=dict)
    typography: dict[str, dict[str, object]] = Field(default_factory=dict)
    spacing: dict[str, float] = Field(default_factory=dict)


class FontAsset(DomainModel):
    """A font referenced by the scene (portable — no host filesystem paths)."""

    family: str
    resolved_family: str | None = None
    path: str | None = None
    weight: int = 400
    style: str = "normal"
    role: str = ""
    script: str = ""  # cjk | latin | mixed


class SceneAssetReference(DomainModel):
    """Persisted asset pointer — portable URI; resolve at render time.

    P2 (schema v2 plan): persist ``storage_uri`` only; drop mirrored
    ``asset_path`` from JSON. ``resolved_path`` stays runtime-only (exclude=True).
    Until then ``asset_path`` is kept as a same-URI alias for backward readers.
    """

    asset_id: UUID | None = None
    storage_uri: str = ""
    asset_path: str = Field(
        default="",
        description=(
            "Deprecated alias of storage_uri (often a URI, not a filesystem path). "
            "Remove from persistence in RenderScene schema_version >= 2."
        ),
    )
    origin: str = "project_upload"
    content_ref: str | None = None
    resolved_path: str | None = Field(default=None, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _coerce_storage_uri(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        uri = str(data.get("storage_uri") or data.get("asset_path") or "").strip()
        payload = dict(data)
        payload["storage_uri"] = uri
        payload["asset_path"] = uri
        return payload

    @model_validator(mode="after")
    def _sync_path_fields(self) -> Self:
        uri = (self.storage_uri or self.asset_path or "").strip()
        if self.storage_uri != uri or self.asset_path != uri:
            object.__setattr__(self, "storage_uri", uri)
            object.__setattr__(self, "asset_path", uri)
        return self


class BaseRenderNode(DomainModel):
    id: str = Field(min_length=1)
    node_type: str
    semantic_role: str = ""
    source_layout_element_id: str | None = None
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    rotation: float = 0
    opacity: float = Field(default=1.0, ge=0, le=1)
    z_index: int = 0
    visible: bool = True
    locked: bool = False
    lock_scopes: list[str] = Field(default_factory=list)
    group_id: str | None = None


class TextNode(BaseRenderNode):
    node_type: Literal["text"] = "text"
    text: str
    paragraphs: list[TextParagraph] = Field(default_factory=list)
    font_family: str
    font_family_cjk: str = ""
    font_family_latin: str = ""
    font_size: float = Field(gt=0)
    font_weight: int = Field(default=400, ge=100, le=900)
    font_style: str = "normal"
    color: str
    # Prefer token refs for theme re-resolution; empty = treat ``color`` as explicit.
    color_token: str = ""
    typography_token: str = ""
    alignment: str = "left"
    vertical_alignment: str = "top"
    line_height: float = Field(gt=0)
    letter_spacing: float = 0
    padding: BoxSpacing = Field(default_factory=BoxSpacing)
    overflow_policy: Literal["error", "shrink", "clip", "continue"] = "shrink"
    minimum_font_size: float = Field(default=8, gt=0)


def replace_text_node_content(node: TextNode, new_text: str) -> None:
    """Replace TextNode.text and collapse paragraphs to one consistent source."""
    node.text = new_text
    alignment = node.paragraphs[0].alignment if node.paragraphs else node.alignment
    node.paragraphs = [TextParagraph(text=new_text, alignment=alignment)]


class ImageNode(BaseRenderNode):
    node_type: Literal["image"] = "image"
    asset_id: UUID | None = None
    storage_uri: str = ""
    asset_path: str = Field(
        default="",
        description=(
            "Deprecated alias of storage_uri (portable URI, not a host path). "
            "Schema v2: stop persisting; renderers use resolved Scene only."
        ),
    )
    asset_origin: Literal[
        "project_upload",
        "public_research",
        "reference_case",
        "ai_generated",
        "stock_image",
    ] = "project_upload"
    fit_mode: Literal["contain", "cover", "crop"] = "cover"
    crop: CropBox | None = None
    focus_point: Point | None = None
    corner_radius: float = Field(default=0, ge=0)
    border: BorderStyle | None = None
    shadow: ShadowStyle | None = None
    caption_node_id: str | None = None
    asset_unresolved: bool = False
    resolved_path: str | None = Field(default=None, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _coerce_storage_uri(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        uri = str(data.get("storage_uri") or data.get("asset_path") or "").strip()
        payload = dict(data)
        payload["storage_uri"] = uri
        payload["asset_path"] = uri
        return payload

    @model_validator(mode="after")
    def _sync_path_fields(self) -> Self:
        uri = (self.storage_uri or self.asset_path or "").strip()
        if self.storage_uri != uri or self.asset_path != uri:
            object.__setattr__(self, "storage_uri", uri)
            object.__setattr__(self, "asset_path", uri)
        return self


DrawingType = Literal[
    "site_plan",
    "floor_plan",
    "elevation",
    "section",
    "detail",
    "diagram",
    "heritage_map",
    "circulation_plan",
]
DrawingFitMode = Literal["contain", "safe_crop"]


class DrawingNode(BaseRenderNode):
    node_type: Literal["drawing"] = "drawing"
    asset_id: UUID | None = None
    storage_uri: str = ""
    asset_path: str = Field(
        default="",
        description=(
            "Deprecated alias of storage_uri (portable URI, not a host path). "
            "Schema v2: stop persisting; renderers use resolved Scene only."
        ),
    )
    drawing_type: DrawingType = "site_plan"
    fit_mode: DrawingFitMode = "contain"
    crop_allowed: bool = False
    preserve_aspect_ratio: bool = True
    preserve_annotations: bool = True
    background_cleanup: bool = False
    line_enhancement: bool = False
    scale_label: str | None = None
    north_arrow_visible: bool = False
    asset_unresolved: bool = False
    resolved_path: str | None = Field(default=None, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _coerce_storage_uri(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        uri = str(data.get("storage_uri") or data.get("asset_path") or "").strip()
        payload = dict(data)
        payload["storage_uri"] = uri
        payload["asset_path"] = uri
        return payload

    @model_validator(mode="after")
    def _sync_path_fields(self) -> Self:
        uri = (self.storage_uri or self.asset_path or "").strip()
        if self.storage_uri != uri or self.asset_path != uri:
            object.__setattr__(self, "storage_uri", uri)
            object.__setattr__(self, "asset_path", uri)
        return self


class ShapeNode(BaseRenderNode):
    node_type: Literal["shape"] = "shape"
    shape_kind: Literal["rectangle", "ellipse", "line", "card"] = "rectangle"
    fill_color: str | None = None
    stroke_color: str | None = None
    stroke_width: float = Field(default=0, ge=0)
    corner_radius: float = Field(default=0, ge=0)


class ChartSeriesData(DomainModel):
    """One data series for a native or shape-baked chart."""

    name: str = Field(min_length=1)
    labels: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)


class ChartNode(BaseRenderNode):
    """Structured chart with series data (dual export: native vs cross-app stable)."""

    node_type: Literal["chart"] = "chart"
    chart_type: str = Field(default="bar", min_length=1)
    title: str | None = None
    series: list[ChartSeriesData] = Field(default_factory=list)
    show_legend: bool = True
    show_value: bool = False
    preview_storage_uri: str = ""
    preview_resolved_path: str | None = Field(default=None, exclude=True)

    @property
    def has_series_data(self) -> bool:
        return any(series.values for series in self.series)


class TableNode(BaseRenderNode):
    """Structured table grid (dual export: native table vs shape/text grid)."""

    node_type: Literal["table"] = "table"
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)

    @property
    def has_grid_data(self) -> bool:
        return bool(self.headers) and bool(self.rows)


RenderNode = Annotated[
    TextNode | ImageNode | DrawingNode | ShapeNode | ChartNode | TableNode,
    Field(discriminator="node_type"),
]


class RenderScene(IdentifiedModel, VersionedModel, TimestampedModel):
    """Unified visual scene — single source of truth for all renderers.

    Supports Text / Image / Drawing / Shape plus optional Chart / Table nodes
    for ``ChartExportMode`` dual export (cross-app stable vs native data-backed).

    Theme model: persist geometry + token references; resolve colors/fonts from
    the active DesignSystem at compile / preview time
    (``Base scene + DesignSystem → Resolved scene``). Do not bake deck-wide
    theme accepts into per-node SceneRevision spam.

    schema_version 1: ``storage_uri`` + mirrored ``asset_path`` (same URI).
    Planned schema_version 2 (P2): persist ``storage_uri`` only; drop
    ``asset_path`` from dump; keep ``resolved_path`` runtime-only.
    """

    schema_version: int = Field(default=1, ge=1)
    slide_id: UUID
    presentation_id: UUID | None = None
    layout_plan_id: UUID
    design_system_id: UUID | None = None
    page_width: float = Field(gt=0)
    page_height: float = Field(gt=0)
    background: BackgroundStyle
    nodes: list[RenderNode] = Field(default_factory=list)
    theme_tokens: ThemeTokens = Field(default_factory=ThemeTokens)
    font_assets: list[FontAsset] = Field(default_factory=list)
    asset_manifest: list[SceneAssetReference] = Field(default_factory=list)
    source_layout_family: str = ""
    source_layout_variant: str = ""
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_node_ids(self) -> RenderScene:
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate render node IDs are not allowed")
        return self

    def sorted_nodes(self) -> list[RenderNode]:
        return sorted(self.nodes, key=lambda node: node.z_index)

    def node_by_id(self, node_id: str) -> RenderNode | None:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def node_by_layout_element_id(self, layout_element_id: str) -> RenderNode | None:
        for node in self.nodes:
            if node.source_layout_element_id == layout_element_id:
                return node
        return None

    def scene_hash_input(self) -> str:
        """Stable serialization input for content hashing.

        Excludes identity/timestamps and runtime-only ``resolved_path``
        (Field exclude=True) so undo/reapply (version bump, same content) still
        matches the parent revision hash. Persisted asset fields must be portable
        ``storage_uri`` values so the hash is machine-independent.
        """
        return self.model_dump_json(
            exclude={"created_at", "updated_at", "id", "version"}
        )


def compute_scene_hash(scene: RenderScene) -> str:
    """Return a stable SHA-256 hex digest for a render scene."""
    import hashlib

    return hashlib.sha256(scene.scene_hash_input().encode("utf-8")).hexdigest()

"""RenderScene — unified final visual scene for all renderers.

    Supports Text / Image / Drawing / Shape / Group / Connector plus optional
    Chart / Table nodes for dual chart-export strategy (``ChartExportMode``).
    Chart/Table nodes carry structured data so exporters can choose cross-app
    stable shapes/images or native PowerPoint Chart/Table objects with embedded
    workbooks.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal, Self, TypedDict
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.visual.enums import LayoutFamily, OverflowPolicy, coerce_overflow_policy
from archium.domain.visual.layout_family_normalize import coerce_layout_family
from archium.domain.visual.structured_payload import ChartSeriesData


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


class GradientStop(DomainModel):
    """One stop on a linear/radial fill (position 0–1; transparency 0=opaque)."""

    position: float = Field(ge=0, le=1)
    color: str
    transparency: float = Field(default=0.0, ge=0, le=1)


class GradientFill(DomainModel):
    """Shape/image fill gradient (V1 export may approximate via layered rects)."""

    kind: Literal["linear", "radial"] = "linear"
    angle_deg: float = 0  # linear only; 0 = left→right, 90 = top→bottom
    stops: list[GradientStop] = Field(min_length=2)


class TextParagraph(DomainModel):
    text: str
    alignment: str = "left"


class TextRun(DomainModel):
    """Inline styled span within a TextNode (empty style fields inherit node defaults)."""

    # Preserve leading/trailing spaces between runs (e.g. " Title").
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=False,
        validate_assignment=True,
        extra="forbid",
    )

    text: str
    font_family: str = ""
    font_family_cjk: str = ""
    font_family_latin: str = ""
    font_size: float | None = Field(default=None, gt=0)
    font_weight: int | None = Field(default=None, ge=100, le=900)
    font_style: str = "normal"
    color: str = ""
    color_token: str = ""
    # v1.1 — per-run tracking / opacity / hollow outline (inherit when None / 0).
    letter_spacing: float | None = Field(default=None, ge=-0.1, le=0.5)
    opacity: float | None = Field(default=None, ge=0.05, le=1.0)
    outline: bool = False
    outline_width_pt: float = Field(default=0.0, ge=0.0, le=4.0)
    outline_color: str = ""
    fill_enabled: bool = True


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

    DOM-015 / schema v2: persist ``storage_uri`` only. ``asset_path`` is an
    in-memory read alias (excluded from dump); load still accepts legacy JSON
    that only has ``asset_path``. ``resolved_path`` is runtime-only.
    """

    asset_id: UUID | None = None
    storage_uri: str = ""
    asset_path: str = Field(
        default="",
        exclude=True,
        description=(
            "Deprecated in-memory alias of storage_uri (not persisted). "
            "Prefer storage_uri; renderers use resolved_path after resolve_scene."
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
    # When non-empty, per-run styling is authoritative; ``text`` is derived.
    runs: list[TextRun] = Field(default_factory=list)
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
    overflow_policy: OverflowPolicy = OverflowPolicy.SHRINK
    minimum_font_size: float = Field(default=8, gt=0)

    @field_validator("overflow_policy", mode="before")
    @classmethod
    def _coerce_overflow_policy(cls, value: object) -> object:
        return coerce_overflow_policy(value, default=OverflowPolicy.SHRINK)

    @model_validator(mode="after")
    def _sync_text_from_runs(self) -> Self:
        if self.runs:
            derived = "".join(run.text for run in self.runs)
            if self.text != derived:
                object.__setattr__(self, "text", derived)
        return self


def replace_text_node_content(node: TextNode, new_text: str) -> None:
    """Replace TextNode.text and collapse paragraphs/runs to one consistent source."""
    node.text = new_text
    alignment = node.paragraphs[0].alignment if node.paragraphs else node.alignment
    node.paragraphs = [TextParagraph(text=new_text, alignment=alignment)]
    if node.runs:
        first = node.runs[0]
        node.runs = [
            TextRun(
                text=new_text,
                font_family=first.font_family,
                font_family_cjk=first.font_family_cjk,
                font_family_latin=first.font_family_latin,
                font_size=first.font_size,
                font_weight=first.font_weight,
                font_style=first.font_style,
                color=first.color,
                color_token=first.color_token,
                letter_spacing=first.letter_spacing,
                opacity=first.opacity,
                outline=first.outline,
                outline_width_pt=first.outline_width_pt,
                outline_color=first.outline_color,
                fill_enabled=first.fill_enabled,
            )
        ]
    else:
        node.runs = []


def set_text_node_runs(node: TextNode, runs: list[TextRun]) -> None:
    """Replace inline runs and derive ``text`` / paragraphs from them."""
    if not runs:
        raise ValueError("set_text_node_runs requires at least one run")
    node.runs = list(runs)
    derived = "".join(run.text for run in node.runs)
    node.text = derived
    alignment = node.paragraphs[0].alignment if node.paragraphs else node.alignment
    node.paragraphs = [TextParagraph(text=derived, alignment=alignment)]


class EffectiveRunStyle(TypedDict):
    font_family: str
    font_family_cjk: str
    font_family_latin: str
    font_size: float
    font_weight: int
    font_style: str
    color: str
    color_token: str
    letter_spacing: float
    opacity: float
    outline: bool
    outline_width_pt: float
    outline_color: str
    fill_enabled: bool


def effective_run_style(node: TextNode, run: TextRun) -> EffectiveRunStyle:
    """Resolve a run's visual style with TextNode fallbacks."""
    return {
        "font_family": run.font_family or node.font_family,
        "font_family_cjk": run.font_family_cjk or node.font_family_cjk,
        "font_family_latin": run.font_family_latin or node.font_family_latin,
        "font_size": run.font_size if run.font_size is not None else node.font_size,
        "font_weight": run.font_weight if run.font_weight is not None else node.font_weight,
        "font_style": run.font_style or node.font_style,
        "color": run.color or node.color,
        "color_token": run.color_token or node.color_token,
        "letter_spacing": (
            run.letter_spacing if run.letter_spacing is not None else node.letter_spacing
        ),
        "opacity": run.opacity if run.opacity is not None else node.opacity,
        "outline": bool(run.outline),
        "outline_width_pt": float(run.outline_width_pt or 0.0),
        "outline_color": run.outline_color or run.color or node.color,
        "fill_enabled": bool(run.fill_enabled),
    }


class ImageNode(BaseRenderNode):
    node_type: Literal["image"] = "image"
    asset_id: UUID | None = None
    storage_uri: str = ""
    asset_path: str = Field(
        default="",
        exclude=True,
        description=(
            "Deprecated in-memory alias of storage_uri (not persisted, DOM-015). "
            "Renderers use resolved_path after AssetPathResolver.resolve_scene."
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
    # Architectural icon pack: token-bound stroke for theme re-resolution.
    icon_stroke_color: str | None = None
    icon_stroke_token: str = ""
    # Optional overlay / fade gradient (e.g. hero bottom fade). Does not replace the image.
    fill: GradientFill | None = None
    image_mask: str | None = None

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
        exclude=True,
        description=(
            "Deprecated in-memory alias of storage_uri (not persisted, DOM-015). "
            "Renderers use resolved_path after AssetPathResolver.resolve_scene."
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
    # When set, preferred over solid fill_color for export.
    fill: GradientFill | None = None
    stroke_color: str | None = None
    stroke_width: float = Field(default=0, ge=0)
    corner_radius: float = Field(default=0, ge=0)


ConnectorAnchor = Literal["center", "top", "bottom", "left", "right"]
ConnectorRouting = Literal["straight", "elbow", "curve"]


class ConnectorEndpoint(DomainModel):
    """Anchor attachment on a target scene node."""

    node_id: str = Field(min_length=1)
    anchor: ConnectorAnchor = "center"
    offset_x: float = 0
    offset_y: float = 0


class ConnectorNode(BaseRenderNode):
    """Analysis / flow link between two nodes (V1: approximate line export).

    ``x/y/width/height`` are the axis-aligned hit box derived from endpoints.
    True PowerPoint ``p:cxnSp`` connection sites are a stretch goal.
    """

    node_type: Literal["connector"] = "connector"
    start: ConnectorEndpoint
    end: ConnectorEndpoint
    routing: ConnectorRouting = "straight"
    stroke_color: str = "#333333"
    stroke_width: float = Field(default=1.5, ge=0)
    arrow_start: bool = False
    arrow_end: bool = True
    label: str = ""


class FreeformNode(BaseRenderNode):
    """Polygon / analysis zone (V1: absolute page coordinates).

    PPTX export uses stroked line segments (APPROXIMATE). Native ``a:custGeom``
    is deferred until the renderer supports it. Fill is authored but may not
    survive as a single editable fill in V1.
    """

    node_type: Literal["freeform"] = "freeform"
    points: list[Point] = Field(min_length=3)
    closed: bool = True
    fill_color: str | None = None
    stroke_color: str | None = "#333333"
    stroke_width: float = Field(default=1.0, ge=0)


MAX_GROUP_DEPTH = 4


class GroupNode(BaseRenderNode):
    """Logical group of sibling scene nodes (V1: absolute child coordinates).

    Children keep page-absolute geometry. ``group_id`` on each child must equal
    this node's ``id``. Nesting depth is capped at ``MAX_GROUP_DEPTH``.
    """

    node_type: Literal["group"] = "group"
    children: list[str] = Field(min_length=1)
    clip_children: bool = False


class ChartNode(BaseRenderNode):
    """Structured chart with series data (dual export: native vs cross-app stable).

    Data fields mirror ``ChartDataPayload`` (DOM-012 shared VO).
    """

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
    """Structured table grid (dual export: native table vs shape/text grid).

    Data fields mirror ``TableDataPayload`` (DOM-012 shared VO).
    """

    node_type: Literal["table"] = "table"
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)

    @property
    def has_grid_data(self) -> bool:
        return bool(self.headers) and bool(self.rows)


RenderNode = Annotated[
    TextNode
    | ImageNode
    | DrawingNode
    | ShapeNode
    | ConnectorNode
    | FreeformNode
    | GroupNode
    | ChartNode
    | TableNode,
    Field(discriminator="node_type"),
]


class RenderScene(IdentifiedModel, VersionedModel, TimestampedModel):
    """Unified visual scene — single source of truth for all renderers.

    Supports Text / Image / Drawing / Shape / Group plus optional Chart / Table
    nodes for ``ChartExportMode`` dual export (cross-app stable vs native
    data-backed).

    Theme model: persist geometry + token references; resolve colors/fonts from
    the active DesignSystem at compile / preview time
    (``Base scene + DesignSystem → Resolved scene``). Do not bake deck-wide
    theme accepts into per-node SceneRevision spam.

    schema_version 1: ``storage_uri`` + mirrored ``asset_path`` (legacy dumps).
    schema_version 2 (DOM-015): persist ``storage_uri`` only; ``asset_path`` is
    excluded from dump (in-memory alias); ``resolved_path`` runtime-only.
    """

    schema_version: int = Field(default=2, ge=1)
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
    source_layout_family: LayoutFamily | None = None
    source_layout_variant: str = ""
    warnings: list[str] = Field(default_factory=list)

    @field_validator("source_layout_family", mode="before")
    @classmethod
    def _coerce_source_layout_family(cls, value: object) -> object:
        return coerce_layout_family(value)

    @model_validator(mode="after")
    def _validate_unique_node_ids(self) -> RenderScene:
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate render node IDs are not allowed")
        _validate_group_structure(self.nodes)
        _validate_connector_structure(self.nodes)
        _validate_freeform_structure(self.nodes)
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


def _validate_group_structure(nodes: list[RenderNode]) -> None:
    """Fail closed on broken group membership, cycles, or excessive nesting."""
    by_id = {node.id: node for node in nodes}
    listed_by_group: dict[str, set[str]] = {}

    for node in nodes:
        if not isinstance(node, GroupNode):
            continue
        if len(set(node.children)) != len(node.children):
            raise ValueError(f"group `{node.id}` has duplicate child ids")
        if node.id in node.children:
            raise ValueError(f"group `{node.id}` cannot contain itself")
        child_ids: set[str] = set()
        for child_id in node.children:
            child = by_id.get(child_id)
            if child is None:
                raise ValueError(f"group `{node.id}` references missing child `{child_id}`")
            if child.group_id != node.id:
                raise ValueError(
                    f"child `{child_id}` group_id must equal parent group `{node.id}`"
                )
            child_ids.add(child_id)
        listed_by_group[node.id] = child_ids

    for node in nodes:
        if not node.group_id:
            continue
        parent = by_id.get(node.group_id)
        if parent is None or not isinstance(parent, GroupNode):
            raise ValueError(
                f"node `{node.id}` group_id `{node.group_id}` does not reference a GroupNode"
            )
        if node.id not in listed_by_group.get(parent.id, set()):
            raise ValueError(
                f"node `{node.id}` is not listed in group `{parent.id}` children"
            )

    for node in nodes:
        if not isinstance(node, GroupNode):
            continue
        depth = _group_nesting_depth(node.id, by_id, visiting=set())
        if depth > MAX_GROUP_DEPTH:
            raise ValueError(
                f"group nesting depth {depth} exceeds max {MAX_GROUP_DEPTH} "
                f"(leaf under `{node.id}`)"
            )


def _group_nesting_depth(
    node_id: str,
    by_id: dict[str, RenderNode],
    *,
    visiting: set[str],
) -> int:
    if node_id in visiting:
        raise ValueError(f"group cycle detected at `{node_id}`")
    node = by_id.get(node_id)
    if node is None or not isinstance(node, GroupNode):
        return 0
    visiting.add(node_id)
    try:
        if not node.children:
            return 1
        return 1 + max(
            _group_nesting_depth(child_id, by_id, visiting=visiting)
            for child_id in node.children
        )
    finally:
        visiting.remove(node_id)


def group_children(scene: RenderScene, group: GroupNode) -> list[RenderNode]:
    """Return child nodes for a group in scene order."""
    by_id = {node.id: node for node in scene.nodes}
    return [by_id[child_id] for child_id in group.children if child_id in by_id]


def compute_group_bounds(nodes: Sequence[BaseRenderNode]) -> tuple[float, float, float, float]:
    """Return (x, y, width, height) bounding box for the given nodes."""
    if not nodes:
        raise ValueError("cannot compute bounds for empty node list")
    left = min(node.x for node in nodes)
    top = min(node.y for node in nodes)
    right = max(node.x + node.width for node in nodes)
    bottom = max(node.y + node.height for node in nodes)
    return left, top, max(right - left, 0.05), max(bottom - top, 0.05)


def _validate_connector_structure(nodes: list[RenderNode]) -> None:
    """Fail closed on missing / self / connector-to-connector endpoints."""
    by_id = {node.id: node for node in nodes}
    for node in nodes:
        if not isinstance(node, ConnectorNode):
            continue
        if node.start.node_id == node.end.node_id:
            raise ValueError(f"connector `{node.id}` start and end must differ")
        for endpoint, label in ((node.start, "start"), (node.end, "end")):
            target = by_id.get(endpoint.node_id)
            if target is None:
                raise ValueError(
                    f"connector `{node.id}` {label} references missing node "
                    f"`{endpoint.node_id}`"
                )
            if isinstance(target, ConnectorNode):
                raise ValueError(
                    f"connector `{node.id}` {label} cannot target another connector"
                )
            if target.id == node.id:
                raise ValueError(f"connector `{node.id}` cannot attach to itself")


def resolve_anchor_point(
    node: BaseRenderNode,
    endpoint: ConnectorEndpoint,
) -> tuple[float, float]:
    """Return absolute page coordinates for an endpoint anchor."""
    if endpoint.anchor == "top":
        x = node.x + node.width / 2
        y = node.y
    elif endpoint.anchor == "bottom":
        x = node.x + node.width / 2
        y = node.y + node.height
    elif endpoint.anchor == "left":
        x = node.x
        y = node.y + node.height / 2
    elif endpoint.anchor == "right":
        x = node.x + node.width
        y = node.y + node.height / 2
    else:
        x = node.x + node.width / 2
        y = node.y + node.height / 2
    return x + endpoint.offset_x, y + endpoint.offset_y


def connector_endpoint_points(
    scene: RenderScene,
    connector: ConnectorNode,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Resolve start/end points, or None if either endpoint is missing."""
    start_node = scene.node_by_id(connector.start.node_id)
    end_node = scene.node_by_id(connector.end.node_id)
    if start_node is None or end_node is None:
        return None
    return (
        resolve_anchor_point(start_node, connector.start),
        resolve_anchor_point(end_node, connector.end),
    )


def refresh_connector_geometry(scene: RenderScene, connector: ConnectorNode) -> bool:
    """Update connector bbox from current endpoint node positions. Returns False if unresolved."""
    points = connector_endpoint_points(scene, connector)
    if points is None:
        return False
    (x1, y1), (x2, y2) = points
    left = min(x1, x2)
    top = min(y1, y2)
    connector.x = left
    connector.y = top
    connector.width = max(abs(x2 - x1), 0.05)
    connector.height = max(abs(y2 - y1), 0.05)
    return True


def refresh_connectors_for_nodes(scene: RenderScene, node_ids: set[str]) -> list[str]:
    """Refresh geometry for connectors attached to any of ``node_ids``. Returns connector ids."""
    updated: list[str] = []
    if not node_ids:
        return updated
    for node in scene.nodes:
        if not isinstance(node, ConnectorNode):
            continue
        if (node.start.node_id in node_ids or node.end.node_id in node_ids) and refresh_connector_geometry(scene, node):
            updated.append(node.id)
    return updated


def connector_path_points(
    scene: RenderScene,
    connector: ConnectorNode,
) -> list[tuple[float, float]]:
    """Return polyline points for export (straight / elbow; curve ≈ straight)."""
    points = connector_endpoint_points(scene, connector)
    if points is None:
        return []
    (x1, y1), (x2, y2) = points
    if connector.routing == "elbow":
        # Prefer mid-X elbow when horizontal span dominates; else mid-Y.
        if abs(x2 - x1) >= abs(y2 - y1):
            mid_x = (x1 + x2) / 2
            return [(x1, y1), (mid_x, y1), (mid_x, y2), (x2, y2)]
        mid_y = (y1 + y2) / 2
        return [(x1, y1), (x1, mid_y), (x2, mid_y), (x2, y2)]
    return [(x1, y1), (x2, y2)]


def compute_scene_hash(scene: RenderScene) -> str:
    """Return a stable SHA-256 hex digest for a render scene."""
    import hashlib

    return hashlib.sha256(scene.scene_hash_input().encode("utf-8")).hexdigest()


def bottom_fade_gradient(
    *,
    color: str = "#1A1A1A",
    opaque_from: float = 0.55,
) -> GradientFill:
    """Common hero-image bottom fade (transparent → opaque downward)."""
    start = max(0.0, min(opaque_from, 0.95))
    return GradientFill(
        kind="linear",
        angle_deg=90,
        stops=[
            GradientStop(position=0.0, color=color, transparency=1.0),
            GradientStop(position=start, color=color, transparency=0.85),
            GradientStop(position=1.0, color=color, transparency=0.35),
        ],
    )


def gradient_fill_to_payload(fill: GradientFill) -> dict[str, object]:
    """Serialize GradientFill for PPTX / preview instructions."""
    return {
        "kind": fill.kind,
        "angle_deg": fill.angle_deg,
        "stops": [
            {
                "position": stop.position,
                "color": stop.color.lstrip("#"),
                "transparency": stop.transparency,
            }
            for stop in fill.stops
        ],
    }


def _validate_freeform_structure(nodes: list[RenderNode]) -> None:
    """Fail closed on freeform polygons with too few points."""
    for node in nodes:
        if not isinstance(node, FreeformNode):
            continue
        if len(node.points) < 3:
            raise ValueError(f"freeform `{node.id}` requires at least 3 points")


def compute_freeform_bounds(points: list[Point]) -> tuple[float, float, float, float]:
    """Return (x, y, width, height) for absolute polygon points."""
    if not points:
        raise ValueError("cannot compute bounds for empty point list")
    left = min(point.x for point in points)
    top = min(point.y for point in points)
    right = max(point.x for point in points)
    bottom = max(point.y for point in points)
    return left, top, max(right - left, 0.05), max(bottom - top, 0.05)


def refresh_freeform_geometry(node: FreeformNode) -> None:
    """Sync FreeformNode bbox from absolute ``points``."""
    x, y, width, height = compute_freeform_bounds(node.points)
    node.x = x
    node.y = y
    node.width = width
    node.height = height


def is_polygon_convex(points: list[Point]) -> bool:
    """Return True when the polygon is convex (cross-product signs agree)."""
    if len(points) < 3:
        return False
    sign = 0
    count = len(points)
    for index in range(count):
        ax, ay = points[index].x, points[index].y
        bx, by = points[(index + 1) % count].x, points[(index + 1) % count].y
        cx, cy = points[(index + 2) % count].x, points[(index + 2) % count].y
        cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if cross == 0:
            continue
        current = 1 if cross > 0 else -1
        if sign == 0:
            sign = current
        elif sign != current:
            return False
    return True


FreeformPreset = Literal["triangle", "diamond", "rect_zone"]


def freeform_preset_points(
    preset: FreeformPreset,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> list[Point]:
    """Build absolute-coordinate presets inside the given box."""
    w = max(width, 0.05)
    h = max(height, 0.05)
    if preset == "triangle":
        return [
            Point(x=x + w / 2, y=y),
            Point(x=x + w, y=y + h),
            Point(x=x, y=y + h),
        ]
    if preset == "diamond":
        return [
            Point(x=x + w / 2, y=y),
            Point(x=x + w, y=y + h / 2),
            Point(x=x + w / 2, y=y + h),
            Point(x=x, y=y + h / 2),
        ]
    # rect_zone
    return [
        Point(x=x, y=y),
        Point(x=x + w, y=y),
        Point(x=x + w, y=y + h),
        Point(x=x, y=y + h),
    ]


def silhouette_overlay_frame(
    *,
    image_x: float,
    image_y: float,
    image_width: float,
    image_height: float,
    preset: FreeformPreset = "diamond",
    inset_ratio: float = 0.08,
) -> tuple[float, float, float, float, list[Point]]:
    """Inset freeform frame over an image bbox for silhouette rhetoric."""
    inset = max(min(image_width, image_height) * inset_ratio, 0.05)
    x = image_x + inset
    y = image_y + inset
    width = max(image_width - 2 * inset, 0.05)
    height = max(image_height - 2 * inset, 0.05)
    return x, y, width, height, freeform_preset_points(
        preset, x=x, y=y, width=width, height=height
    )


def translate_freeform_points(node: FreeformNode, *, dx: float, dy: float) -> None:
    """Shift all freeform vertices and refresh bbox."""
    node.points = [Point(x=point.x + dx, y=point.y + dy) for point in node.points]
    refresh_freeform_geometry(node)


def scale_freeform_points(
    node: FreeformNode,
    *,
    origin_x: float,
    origin_y: float,
    scale: float,
    new_origin_x: float,
    new_origin_y: float,
) -> None:
    """Uniform-scale freeform vertices about an origin, then place at new origin."""
    node.points = [
        Point(
            x=new_origin_x + (point.x - origin_x) * scale,
            y=new_origin_y + (point.y - origin_y) * scale,
        )
        for point in node.points
    ]
    refresh_freeform_geometry(node)


def remap_freeform_points_to_bbox(
    node: FreeformNode,
    *,
    old_x: float,
    old_y: float,
    old_width: float,
    old_height: float,
) -> None:
    """Remap absolute vertices from a previous bbox into the node's current bbox."""
    sx = node.width / max(old_width, 1e-6)
    sy = node.height / max(old_height, 1e-6)
    node.points = [
        Point(
            x=node.x + (point.x - old_x) * sx,
            y=node.y + (point.y - old_y) * sy,
        )
        for point in node.points
    ]
    refresh_freeform_geometry(node)


def move_freeform_to(node: FreeformNode, *, x: float, y: float) -> None:
    """Move freeform by translating vertices so bbox origin becomes (x, y)."""
    translate_freeform_points(node, dx=x - node.x, dy=y - node.y)


def resize_freeform_to(
    node: FreeformNode,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """Scale freeform vertices into a new absolute bbox."""
    old_x, old_y, old_w, old_h = node.x, node.y, node.width, node.height
    node.x = x
    node.y = y
    node.width = max(width, 0.05)
    node.height = max(height, 0.05)
    remap_freeform_points_to_bbox(
        node,
        old_x=old_x,
        old_y=old_y,
        old_width=old_w,
        old_height=old_h,
    )

"""RenderScene — unified final visual scene for all renderers."""

from __future__ import annotations

from typing import Annotated, Literal
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
    family: str
    path: str | None = None
    weight: int = 400
    style: str = "normal"


class SceneAssetReference(DomainModel):
    asset_id: UUID | None = None
    asset_path: str
    origin: str = "project_upload"
    content_ref: str | None = None


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
    font_size: float = Field(gt=0)
    font_weight: int = Field(default=400, ge=100, le=900)
    font_style: str = "normal"
    color: str
    alignment: str = "left"
    vertical_alignment: str = "top"
    line_height: float = Field(gt=0)
    letter_spacing: float = 0
    padding: BoxSpacing = Field(default_factory=BoxSpacing)
    overflow_policy: Literal["error", "shrink", "clip", "continue"] = "shrink"
    minimum_font_size: float = Field(default=8, gt=0)


class ImageNode(BaseRenderNode):
    node_type: Literal["image"] = "image"
    asset_id: UUID | None = None
    asset_path: str = ""
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
    asset_path: str = ""
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


class ShapeNode(BaseRenderNode):
    node_type: Literal["shape"] = "shape"
    shape_kind: Literal["rectangle", "ellipse", "line", "card"] = "rectangle"
    fill_color: str | None = None
    stroke_color: str | None = None
    stroke_width: float = Field(default=0, ge=0)
    corner_radius: float = Field(default=0, ge=0)


RenderNode = Annotated[
    TextNode | ImageNode | DrawingNode | ShapeNode,
    Field(discriminator="node_type"),
]


class RenderScene(IdentifiedModel, VersionedModel, TimestampedModel):
    """Unified visual scene — single source of truth for all renderers."""

    schema_version: int = Field(default=1, ge=1)
    slide_id: UUID
    presentation_id: UUID | None = None
    layout_plan_id: UUID
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

    def scene_hash_input(self) -> str:
        """Stable serialization input for content hashing."""
        return self.model_dump_json(exclude={"created_at", "updated_at"})


def compute_scene_hash(scene: RenderScene) -> str:
    """Return a stable SHA-256 hex digest for a render scene."""
    import hashlib

    return hashlib.sha256(scene.scene_hash_input().encode("utf-8")).hexdigest()

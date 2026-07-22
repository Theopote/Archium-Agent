"""Slide recovery infrastructure — region analysis adapters for the Phase 5 spike."""

from __future__ import annotations

from uuid import UUID, uuid4

from archium.domain.slide_recovery import (
    NormalizedBox,
    RecoveredPageRegion,
    RegionType,
    SlideRecoveryPageKind,
)
from archium.domain.visual.render_scene import (
    DrawingNode,
    ImageNode,
    RenderNode,
    RenderScene,
    ShapeNode,
    TextNode,
)

_VISUAL_REGION_TYPES: frozenset[RegionType] = frozenset(
    {"image", "drawing", "table", "chart", "background"}
)
_SHAPE_REGION_TYPES: frozenset[RegionType] = frozenset({"line", "shape"})


def classify_page_kind(scene: RenderScene) -> SlideRecoveryPageKind:
    """Heuristic page archetype from scene node composition."""
    drawings = sum(1 for node in scene.nodes if isinstance(node, DrawingNode))
    images = sum(1 for node in scene.nodes if isinstance(node, ImageNode))
    texts = sum(1 for node in scene.nodes if isinstance(node, TextNode))
    table_like = sum(
        1
        for node in scene.nodes
        if isinstance(node, TextNode) and node.semantic_role in {"table_cell", "metric"}
    )

    if drawings >= 1 and drawings >= images:
        return SlideRecoveryPageKind.DRAWING_DOMINANT
    if table_like >= 4:
        return SlideRecoveryPageKind.TABLE
    if images >= 2 and texts <= 2:
        return SlideRecoveryPageKind.PHOTO
    if images >= 1 and texts >= 2:
        return SlideRecoveryPageKind.IMAGE_TEXT
    if texts <= 2 and images == 0 and drawings == 0:
        return SlideRecoveryPageKind.TITLE
    if images >= 1:
        return SlideRecoveryPageKind.IMAGE_TEXT
    return SlideRecoveryPageKind.TITLE


def regions_from_render_scene(
    scene: RenderScene,
    *,
    page_kind: SlideRecoveryPageKind | None = None,
) -> list[RecoveredPageRegion]:
    """Spike adapter: simulate OCR + VLM region analysis from a known RenderScene."""
    resolved_kind = page_kind or classify_page_kind(scene)
    regions: list[RecoveredPageRegion] = []
    for node in scene.sorted_nodes():
        region = _region_from_node(scene, node, page_kind=resolved_kind)
        if region is not None:
            regions.append(region)
    return regions


def partition_regions(
    regions: list[RecoveredPageRegion],
) -> tuple[list[RecoveredPageRegion], list[RecoveredPageRegion], list[RecoveredPageRegion]]:
    text_regions = [region for region in regions if region.region_type == "text"]
    visual_regions = [region for region in regions if region.region_type in _VISUAL_REGION_TYPES]
    native_shapes = [region for region in regions if region.region_type in _SHAPE_REGION_TYPES]
    return text_regions, visual_regions, native_shapes


def _region_from_node(
    scene: RenderScene,
    node: RenderNode,
    *,
    page_kind: SlideRecoveryPageKind,
) -> RecoveredPageRegion | None:
    bbox = NormalizedBox.from_absolute(
        x=node.x,
        y=node.y,
        width=node.width,
        height=node.height,
        page_width=scene.page_width,
        page_height=scene.page_height,
    )
    region_id = uuid4()

    if isinstance(node, TextNode):
        return RecoveredPageRegion(
            id=region_id,
            bbox=bbox,
            region_type="text",
            semantic_role=node.semantic_role or None,
            confidence=0.98,
            recovered_text=node.text,
            source_node_id=node.id,
        )

    if isinstance(node, DrawingNode):
        return RecoveredPageRegion(
            id=region_id,
            bbox=bbox,
            region_type="drawing",
            semantic_role=node.semantic_role or node.drawing_type,
            confidence=0.95,
            source_asset_uri=node.storage_uri or None,
            keep_whole_drawing=True,
            source_node_id=node.id,
        )

    if isinstance(node, ImageNode):
        region_type: RegionType = "image"
        if page_kind == SlideRecoveryPageKind.PHOTO or node.semantic_role in {
            "project_photo",
            "site_photo",
            "photo",
        }:
            region_type = "image"
        return RecoveredPageRegion(
            id=region_id,
            bbox=bbox,
            region_type=region_type,
            semantic_role=node.semantic_role or None,
            confidence=0.94,
            source_asset_uri=node.storage_uri or None,
            source_node_id=node.id,
        )

    if isinstance(node, ShapeNode):
        region_type = "line" if node.shape_kind == "line" else "shape"
        return RecoveredPageRegion(
            id=region_id,
            bbox=bbox,
            region_type=region_type,
            semantic_role=node.semantic_role or node.shape_kind,
            confidence=0.90,
            source_node_id=node.id,
        )

    return None


def build_render_scene_from_regions(
    source: RenderScene,
    regions: list[RecoveredPageRegion],
    *,
    source_page_id: str,
    page_kind: SlideRecoveryPageKind,
) -> tuple[RenderScene, list[UUID]]:
    """Rebuild a hybrid RenderScene from recovered regions."""

    hybrid_bitmap_ids: list[UUID] = []
    nodes: list[RenderNode] = []
    source_by_id = {node.id: node for node in source.nodes}

    for index, region in enumerate(regions):
        node = _node_from_region(
            source,
            region,
            source_by_id=source_by_id,
            z_index=index,
        )
        if node is None:
            continue
        nodes.append(node)
        if region.bitmap_fallback:
            hybrid_bitmap_ids.append(region.id)

    scene = source.model_copy(
        update={
            "id": uuid4(),
            "nodes": nodes,
            "warnings": list(source.warnings),
        }
    )
    scene.warnings.append(f"slide_recovery:{source_page_id}:{page_kind.value}")
    return scene, hybrid_bitmap_ids


def _node_from_region(
    source: RenderScene,
    region: RecoveredPageRegion,
    *,
    source_by_id: dict[str, RenderNode],
    z_index: int,
) -> RenderNode | None:
    page_w = source.page_width
    page_h = source.page_height
    x = region.bbox.x * page_w
    y = region.bbox.y * page_h
    width = region.bbox.width * page_w
    height = region.bbox.height * page_h
    node_id = region.source_node_id or f"recovered_{region.id.hex[:8]}"

    if region.region_type == "text" and region.recovered_text:
        ref = source_by_id.get(region.source_node_id or "")
        font_family = "Microsoft YaHei"
        font_size = 24.0
        color = "#1A1A1A"
        line_height = 32.0
        if isinstance(ref, TextNode):
            font_family = ref.font_family
            font_size = ref.font_size
            color = ref.color
            line_height = ref.line_height
        return TextNode(
            id=node_id,
            x=x,
            y=y,
            width=width,
            height=height,
            z_index=z_index,
            text=region.recovered_text,
            semantic_role=region.semantic_role or "",
            font_family=font_family,
            font_size=font_size,
            color=color,
            line_height=line_height,
        )

    if region.region_type == "drawing" or (
        region.keep_whole_drawing and region.source_asset_uri
    ):
        ref = source_by_id.get(region.source_node_id or "")
        drawing_type = "site_plan"
        storage_uri = region.source_asset_uri or ""
        if isinstance(ref, DrawingNode):
            drawing_type = ref.drawing_type
            storage_uri = ref.storage_uri or storage_uri
        return DrawingNode(
            id=node_id,
            x=x,
            y=y,
            width=width,
            height=height,
            z_index=z_index,
            storage_uri=storage_uri,
            drawing_type=drawing_type,
            fit_mode="contain",
            crop_allowed=False,
            locked=True,
            lock_scopes=["drawing_integrity"],
            semantic_role=region.semantic_role or "drawing",
        )

    if region.region_type in {"image", "background"} or region.bitmap_fallback:
        ref = source_by_id.get(region.source_node_id or "")
        storage_uri = region.source_asset_uri or ""
        asset_origin = "project_upload"
        if isinstance(ref, ImageNode):
            storage_uri = ref.storage_uri or storage_uri
            asset_origin = ref.asset_origin
        return ImageNode(
            id=node_id,
            x=x,
            y=y,
            width=width,
            height=height,
            z_index=z_index,
            storage_uri=storage_uri,
            asset_origin=asset_origin,
            semantic_role=region.semantic_role or "",
        )

    if region.region_type == "table" and region.bitmap_fallback:
        return ImageNode(
            id=node_id,
            x=x,
            y=y,
            width=width,
            height=height,
            z_index=z_index,
            storage_uri=region.source_asset_uri or "",
            semantic_role="table_bitmap",
        )

    if region.region_type == "line":
        ref = source_by_id.get(region.source_node_id or "")
        stroke = "#333333"
        if isinstance(ref, ShapeNode):
            stroke = ref.stroke_color or stroke
        return ShapeNode(
            id=node_id,
            x=x,
            y=y,
            width=width,
            height=height,
            z_index=z_index,
            shape_kind="line",
            stroke_color=stroke,
            stroke_width=1.0,
            semantic_role=region.semantic_role or "line",
        )

    if region.region_type == "shape":
        ref = source_by_id.get(region.source_node_id or "")
        fill = None
        stroke = None
        if isinstance(ref, ShapeNode):
            fill = ref.fill_color
            stroke = ref.stroke_color
        return ShapeNode(
            id=node_id,
            x=x,
            y=y,
            width=width,
            height=height,
            z_index=z_index,
            shape_kind="rectangle",
            fill_color=fill,
            stroke_color=stroke,
            semantic_role=region.semantic_role or "shape",
        )

    return None

"""Bridge recovered page regions to the Studio canvas editor."""

from __future__ import annotations

from uuid import UUID, uuid4

from archium.application.slide_recovery_region_edit_service import normalize_bbox
from archium.application.visual.element_geometry import (
    layout_bounds_from_percent,
    layout_coords_from_percent,
)
from archium.domain.slide_recovery import (
    REGION_TYPE_LABELS_ZH,
    NormalizedBox,
    RecoveredPageRegion,
    RegionType,
)
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan

_STANDARD_PAGE_WIDTH = 10.0
_STANDARD_PAGE_HEIGHT = 5.625

_REGION_ROLE_MAP: dict[str, LayoutElementRole] = {
    "text": LayoutElementRole.BODY_TEXT,
    "image": LayoutElementRole.HERO_VISUAL,
    "drawing": LayoutElementRole.HERO_VISUAL,
    "table": LayoutElementRole.BODY_TEXT,
    "chart": LayoutElementRole.BODY_TEXT,
    "line": LayoutElementRole.DECORATION,
    "shape": LayoutElementRole.DECORATION,
    "background": LayoutElementRole.DECORATION,
    "unknown": LayoutElementRole.BODY_TEXT,
}


def layout_plan_from_regions(regions: list[RecoveredPageRegion]) -> LayoutPlan:
    """Build a temporary layout plan for interactive region editing."""
    design = default_presentation_design_system()
    elements: list[LayoutElement] = []
    reading_order: list[str] = []

    for index, region in enumerate(regions):
        element_id = str(region.id)
        role = _REGION_ROLE_MAP.get(region.region_type, LayoutElementRole.BODY_TEXT)
        if region.region_type == "text" and region.semantic_role in {"title", "subtitle"}:
            role = LayoutElementRole.TITLE

        label = REGION_TYPE_LABELS_ZH.get(region.region_type, region.region_type)
        text_content = region.recovered_text or f"{label} #{index + 1}"
        elements.append(
            LayoutElement(
                id=element_id,
                role=role,
                content_type=LayoutContentType.TEXT,
                text_content=text_content,
                x=region.bbox.x * _STANDARD_PAGE_WIDTH,
                y=region.bbox.y * _STANDARD_PAGE_HEIGHT,
                width=region.bbox.width * _STANDARD_PAGE_WIDTH,
                height=region.bbox.height * _STANDARD_PAGE_HEIGHT,
            )
        )
        reading_order.append(element_id)

    hero = next(
        (element.id for element in elements if element.role == LayoutElementRole.TITLE),
        elements[0].id if elements else "recovery-region",
    )
    return LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="recovery_region_edit",
        page_width=_STANDARD_PAGE_WIDTH,
        page_height=_STANDARD_PAGE_HEIGHT,
        hero_element_id=hero,
        reading_order=reading_order,
        elements=elements,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
    )


def region_index_for_element_id(
    regions: list[RecoveredPageRegion],
    element_id: str | None,
) -> int | None:
    if not element_id:
        return None
    for index, region in enumerate(regions):
        if str(region.id) == element_id:
            return index
    return None


def apply_canvas_move(
    region: RecoveredPageRegion,
    layout_plan: LayoutPlan,
    *,
    x_percent: float,
    y_percent: float,
) -> RecoveredPageRegion:
    x, y = layout_coords_from_percent(
        layout_plan,
        x_percent=x_percent,
        y_percent=y_percent,
    )
    bbox = normalize_bbox(
        x=x / layout_plan.page_width,
        y=y / layout_plan.page_height,
        width=region.bbox.width,
        height=region.bbox.height,
    )
    return region.model_copy(update={"bbox": bbox})


def apply_canvas_resize(
    region: RecoveredPageRegion,
    layout_plan: LayoutPlan,
    *,
    x_percent: float,
    y_percent: float,
    width_percent: float,
    height_percent: float,
) -> RecoveredPageRegion:
    x, y, width, height = layout_bounds_from_percent(
        layout_plan,
        x_percent=x_percent,
        y_percent=y_percent,
        width_percent=width_percent,
        height_percent=height_percent,
    )
    bbox = normalize_bbox(
        x=x / layout_plan.page_width,
        y=y / layout_plan.page_height,
        width=width / layout_plan.page_width,
        height=height / layout_plan.page_height,
    )
    return region.model_copy(update={"bbox": bbox})


def union_bbox(boxes: list[NormalizedBox]) -> NormalizedBox:
    min_x = min(box.x for box in boxes)
    min_y = min(box.y for box in boxes)
    max_x = max(box.x + box.width for box in boxes)
    max_y = max(box.y + box.height for box in boxes)
    return normalize_bbox(
        x=min_x,
        y=min_y,
        width=max_x - min_x,
        height=max_y - min_y,
    )


_MERGE_TYPE_PRIORITY: tuple[RegionType, ...] = (
    "drawing",
    "table",
    "chart",
    "image",
    "text",
    "shape",
    "line",
    "background",
    "unknown",
)


def resolve_merged_region_type(regions: list[RecoveredPageRegion]) -> RegionType:
    types = {region.region_type for region in regions}
    for region_type in _MERGE_TYPE_PRIORITY:
        if region_type in types:
            return region_type
    return "unknown"


def merge_regions(
    regions: list[RecoveredPageRegion],
    region_ids: list[UUID],
) -> list[RecoveredPageRegion]:
    """Merge selected regions into one union bbox region."""
    from archium.exceptions import WorkflowError

    if len(region_ids) < 2:
        raise WorkflowError("请至少选择两个区域进行合并。")

    selected = [region for region in regions if region.id in region_ids]
    if len(selected) < 2:
        raise WorkflowError("未找到足够的有效区域。")

    merged_bbox = union_bbox([region.bbox for region in selected])
    merged_type = resolve_merged_region_type(selected)
    text_parts = [
        region.recovered_text.strip()
        for region in selected
        if region.region_type == "text" and region.recovered_text and region.recovered_text.strip()
    ]
    roles = [region.semantic_role for region in selected if region.semantic_role]
    asset_uris = [region.source_asset_uri for region in selected if region.source_asset_uri]

    merged = RecoveredPageRegion(
        id=uuid4(),
        bbox=merged_bbox,
        region_type=merged_type,
        semantic_role=roles[0] if roles else "merged",
        confidence=min(region.confidence for region in selected),
        recovered_text="\n".join(text_parts) if text_parts else None,
        keep_whole_drawing=any(region.keep_whole_drawing for region in selected),
        bitmap_fallback=any(region.bitmap_fallback for region in selected),
        source_asset_uri=asset_uris[0] if asset_uris else None,
        source_node_id=None,
    )

    remaining = [region for region in regions if region.id not in region_ids]
    remaining.append(merged)
    return remaining


def split_region(
    region: RecoveredPageRegion,
    *,
    axis: str,
    ratio: float = 0.5,
) -> tuple[RecoveredPageRegion, RecoveredPageRegion]:
    """Split one region into two along a vertical or horizontal axis."""
    from archium.exceptions import WorkflowError

    if axis not in {"vertical", "horizontal"}:
        raise WorkflowError(f"不支持的拆分方向：{axis}")

    split_ratio = min(max(float(ratio), 0.1), 0.9)
    bbox = region.bbox

    if axis == "vertical":
        left_width = bbox.width * split_ratio
        right_width = bbox.width - left_width
        first_bbox = normalize_bbox(
            x=bbox.x,
            y=bbox.y,
            width=left_width,
            height=bbox.height,
        )
        second_bbox = normalize_bbox(
            x=bbox.x + left_width,
            y=bbox.y,
            width=right_width,
            height=bbox.height,
        )
        first_suffix, second_suffix = "left", "right"
    else:
        top_height = bbox.height * split_ratio
        bottom_height = bbox.height - top_height
        first_bbox = normalize_bbox(
            x=bbox.x,
            y=bbox.y,
            width=bbox.width,
            height=top_height,
        )
        second_bbox = normalize_bbox(
            x=bbox.x,
            y=bbox.y + top_height,
            width=bbox.width,
            height=bottom_height,
        )
        first_suffix, second_suffix = "top", "bottom"

    first_text, second_text = _split_text(region.recovered_text or "", split_ratio)
    role_base = region.semantic_role or region.region_type

    first = region.model_copy(
        update={
            "id": uuid4(),
            "bbox": first_bbox,
            "semantic_role": f"{role_base}_{first_suffix}",
            "recovered_text": first_text or region.recovered_text,
            "source_node_id": region.source_node_id,
        }
    )
    second = region.model_copy(
        update={
            "id": uuid4(),
            "bbox": second_bbox,
            "semantic_role": f"{role_base}_{second_suffix}",
            "recovered_text": second_text or None,
            "source_node_id": None,
        }
    )
    return first, second


def replace_region(
    regions: list[RecoveredPageRegion],
    original_id: UUID,
    replacements: list[RecoveredPageRegion],
) -> list[RecoveredPageRegion]:
    updated: list[RecoveredPageRegion] = []
    replaced = False
    for region in regions:
        if region.id == original_id:
            if not replaced:
                updated.extend(replacements)
                replaced = True
            continue
        updated.append(region)
    if not replaced:
        updated.extend(replacements)
    return updated


def _split_text(text: str, ratio: float) -> tuple[str, str]:
    cleaned = text.strip()
    if not cleaned:
        return "", ""

    split_at = max(1, min(len(cleaned) - 1, int(len(cleaned) * ratio)))
    for delta in range(0, max(split_at, len(cleaned) - split_at)):
        for index in (split_at + delta, split_at - delta):
            if 0 < index < len(cleaned) and cleaned[index] in {"\n", " ", "，", ",", "、"}:
                return cleaned[:index].strip(), cleaned[index + 1 :].strip()
    return cleaned[:split_at].strip(), cleaned[split_at:].strip()

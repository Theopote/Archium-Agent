"""Fill a LayoutPlan from ArchitecturalTemplate slots with real slide content."""

from __future__ import annotations

from uuid import UUID, uuid4

from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplateLayout,
    TemplatePageType,
    TemplateSlot,
    TemplateSlotRole,
)
from archium.domain.visual.enums import (
    CropPolicy,
    ImageFit,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.visual_intent import VisualIntent

SLOT_TO_LAYOUT_ROLE: dict[TemplateSlotRole, LayoutElementRole] = {
    TemplateSlotRole.TITLE: LayoutElementRole.TITLE,
    TemplateSlotRole.SUBTITLE: LayoutElementRole.SUBTITLE,
    TemplateSlotRole.BODY: LayoutElementRole.BODY_TEXT,
    TemplateSlotRole.HERO_IMAGE: LayoutElementRole.HERO_VISUAL,
    TemplateSlotRole.SUPPORTING_IMAGE: LayoutElementRole.SUPPORTING_VISUAL,
    TemplateSlotRole.DRAWING: LayoutElementRole.HERO_VISUAL,
    TemplateSlotRole.METRIC: LayoutElementRole.METRIC,
    TemplateSlotRole.CAPTION: LayoutElementRole.CAPTION,
    TemplateSlotRole.SOURCE: LayoutElementRole.SOURCE,
    TemplateSlotRole.CHART: LayoutElementRole.SUPPORTING_VISUAL,
    TemplateSlotRole.TABLE: LayoutElementRole.BODY_TEXT,
    TemplateSlotRole.DECORATION: LayoutElementRole.DECORATION,
}

PAGE_TYPE_TO_FAMILY: dict[TemplatePageType, LayoutFamily] = {
    TemplatePageType.COVER: LayoutFamily.HERO,
    TemplatePageType.SECTION: LayoutFamily.HERO,
    TemplatePageType.AGENDA: LayoutFamily.TEXTUAL_ARGUMENT,
    TemplatePageType.TEXT_ARGUMENT: LayoutFamily.TEXTUAL_ARGUMENT,
    TemplatePageType.DRAWING_FOCUS: LayoutFamily.DRAWING_FOCUS,
    TemplatePageType.PHOTO_GRID: LayoutFamily.EVIDENCE_BOARD,
    TemplatePageType.BEFORE_AFTER: LayoutFamily.COMPARATIVE_MATRIX,
    TemplatePageType.CASE_COMPARISON: LayoutFamily.COMPARATIVE_MATRIX,
    TemplatePageType.METRIC: LayoutFamily.METRIC_DASHBOARD,
    TemplatePageType.TIMELINE: LayoutFamily.PROCESS_NARRATIVE,
    TemplatePageType.PROCESS: LayoutFamily.PROCESS_NARRATIVE,
    TemplatePageType.CLOSING: LayoutFamily.HERO,
    TemplatePageType.UNKNOWN: LayoutFamily.TEXTUAL_ARGUMENT,
}


def _slot_content_type(slot: TemplateSlot) -> LayoutContentType:
    if slot.role == TemplateSlotRole.DRAWING:
        return LayoutContentType.DRAWING
    if slot.role in {
        TemplateSlotRole.HERO_IMAGE,
        TemplateSlotRole.SUPPORTING_IMAGE,
        TemplateSlotRole.CHART,
    }:
        return LayoutContentType.IMAGE
    if slot.role == TemplateSlotRole.TABLE:
        return LayoutContentType.TABLE
    if slot.role == TemplateSlotRole.METRIC:
        return LayoutContentType.METRIC
    if slot.role == TemplateSlotRole.DECORATION:
        return LayoutContentType.SHAPE
    return LayoutContentType.TEXT


def _text_for_slot(slot: TemplateSlot, slide: SlideSpec) -> str | None:
    if slot.role == TemplateSlotRole.TITLE:
        return slide.title
    if slot.role == TemplateSlotRole.SUBTITLE:
        return slide.key_points[0] if slide.key_points else slide.message[:80]
    if slot.role == TemplateSlotRole.BODY:
        points = "\n".join(f"· {point}" for point in slide.key_points[:4])
        return f"{slide.message}\n{points}".strip() if points else slide.message
    if slot.role == TemplateSlotRole.CAPTION:
        return slide.key_points[-1] if slide.key_points else f"{slide.title} · 图注"
    if slot.role == TemplateSlotRole.SOURCE:
        if slide.source_citations:
            citation = slide.source_citations[0]
            label = citation.quote or citation.document_name
            page = f" p.{citation.page_number}" if citation.page_number else ""
            return f"来源：{label}{page}"
        return "来源：项目资料"
    if slot.role == TemplateSlotRole.METRIC:
        for point in slide.key_points:
            if any(token in point for token in ("% ", "㎡", "m²", "万", "指标")):
                return point
        return slide.key_points[0] if slide.key_points else "—"
    return None


def fill_layout_plan_from_template(
    *,
    layout: ArchitecturalTemplateLayout,
    slide: SlideSpec,
    visual_intent: VisualIntent,
    design_system_id: UUID,
    template_id: UUID | None = None,
    test_fill: bool = False,
    test_text: dict[TemplateSlotRole, str] | None = None,
) -> LayoutPlan:
    """Map template slots to a LayoutPlan filled with slide content."""
    family = PAGE_TYPE_TO_FAMILY.get(layout.page_type, LayoutFamily.TEXTUAL_ARGUMENT)
    supporting = list(visual_intent.supporting_asset_ids)
    supporting_index = 0
    elements: list[LayoutElement] = []
    reading_order: list[str] = []
    hero_id: str | None = None

    for index, slot in enumerate(layout.slots):
        role = SLOT_TO_LAYOUT_ROLE.get(slot.role, LayoutElementRole.BODY_TEXT)
        content_type = _slot_content_type(slot)
        text_content: str | None = None
        content_ref: str | None = None
        fit_mode: ImageFit | None = None
        crop_policy: CropPolicy | None = None

        if content_type in {LayoutContentType.IMAGE, LayoutContentType.DRAWING}:
            if slot.role == TemplateSlotRole.DRAWING or content_type == LayoutContentType.DRAWING:
                fit_mode = ImageFit.CONTAIN
                crop_policy = CropPolicy.FORBIDDEN
                content_ref = (
                    str(visual_intent.hero_asset_id)
                    if visual_intent.hero_asset_id is not None
                    else None
                )
            elif slot.role == TemplateSlotRole.HERO_IMAGE:
                fit_mode = ImageFit.COVER
                crop_policy = CropPolicy.SAFE_TRIM
                content_ref = (
                    str(visual_intent.hero_asset_id)
                    if visual_intent.hero_asset_id is not None
                    else None
                )
            else:
                fit_mode = ImageFit.COVER
                crop_policy = CropPolicy.COVER_CROP
                if supporting_index < len(supporting):
                    content_ref = str(supporting[supporting_index])
                    supporting_index += 1
                elif visual_intent.hero_asset_id is not None and not any(
                    el.content_ref == str(visual_intent.hero_asset_id)
                    for el in elements
                    if el.content_ref
                ):
                    content_ref = str(visual_intent.hero_asset_id)
        else:
            if test_fill and test_text is not None:
                text_content = test_text.get(slot.role)
            else:
                text_content = _text_for_slot(slot, slide)

        # Architectural constraints from template slots.
        for constraint in slot.architectural_constraints:
            lowered = constraint.lower()
            if "no_crop" in lowered or "forbid_crop" in lowered:
                crop_policy = CropPolicy.FORBIDDEN
                fit_mode = ImageFit.CONTAIN

        element_id = slot.id or f"slot_{index}"
        elements.append(
            LayoutElement(
                id=element_id,
                role=role,
                content_type=content_type,
                content_ref=content_ref,
                text_content=text_content,
                x=slot.x,
                y=slot.y,
                width=slot.width,
                height=slot.height,
                z_index=index,
                fit_mode=fit_mode,
                crop_policy=crop_policy,
            )
        )
        reading_order.append(element_id)
        if hero_id is None and slot.role in {
            TemplateSlotRole.HERO_IMAGE,
            TemplateSlotRole.DRAWING,
            TemplateSlotRole.TITLE,
        }:
            hero_id = element_id

    variant = f"template:{layout.page_type.value}:{layout.id}"
    return LayoutPlan(
        slide_id=slide.id,
        layout_family=family,
        layout_variant=variant,
        page_width=layout.page_width,
        page_height=layout.page_height,
        hero_element_id=hero_id or (reading_order[0] if reading_order else None),
        reading_order=reading_order,
        whitespace_ratio=0.35,
        elements=elements,
        design_system_id=design_system_id,
        visual_intent_id=visual_intent.id,
        source_template_id=template_id,
        source_template_layout_id=layout.id,
    )

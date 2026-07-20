"""Unit tests for template → LayoutPlan content filling."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.template_layout_filler import fill_layout_plan_from_template
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplateLayout,
    TemplatePageType,
    TemplateSlot,
    TemplateSlotRole,
)
from archium.domain.visual.enums import CropPolicy, ImageFit, LayoutContentType, VisualContentType
from archium.domain.visual.visual_intent import VisualIntent


def test_fill_layout_plan_maps_slots_and_drawing_constraints() -> None:
    layout = ArchitecturalTemplateLayout(
        name="图纸主导",
        page_index=0,
        page_type=TemplatePageType.DRAWING_FOCUS,
        page_width=10,
        page_height=5.625,
        slots=[
            TemplateSlot(
                id="title",
                role=TemplateSlotRole.TITLE,
                x=0.8,
                y=0.4,
                width=8.0,
                height=0.6,
            ),
            TemplateSlot(
                id="hero",
                role=TemplateSlotRole.DRAWING,
                x=0.8,
                y=1.2,
                width=8.4,
                height=3.8,
                architectural_constraints=["no_crop"],
            ),
        ],
    )
    hero_id = uuid4()
    slide = SlideSpec(
        presentation_id=uuid4(),
        title="总平面",
        slide_type=SlideType.CONTENT,
        order=0,
        chapter_id="ch1",
        message="场地关系说明",
        key_points=["北侧入口", "南侧绿化"],
    )
    intent = VisualIntent(
        slide_id=slide.id,
        communication_goal="展示图纸",
        audience_takeaway="读懂总平面",
        visual_priority="drawing",
        dominant_content_type=VisualContentType.SITE_PLAN,
        hero_asset_id=hero_id,
    )
    template_id = uuid4()
    plan = fill_layout_plan_from_template(
        layout=layout,
        slide=slide,
        visual_intent=intent,
        design_system_id=uuid4(),
        template_id=template_id,
    )
    assert plan.source_template_id == template_id
    assert plan.source_template_layout_id == layout.id
    title = plan.element_by_id("title")
    hero = plan.element_by_id("hero")
    assert title is not None and title.text_content == "总平面"
    assert hero is not None
    assert hero.content_type == LayoutContentType.DRAWING
    assert hero.content_ref == str(hero_id)
    assert hero.fit_mode == ImageFit.CONTAIN
    assert hero.crop_policy == CropPolicy.FORBIDDEN

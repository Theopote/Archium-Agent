"""Adapter and text measurement smoke tests."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.visual import (
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
    default_presentation_design_system,
)
from archium.domain.visual.enums import LayoutContentType
from archium.infrastructure.layout.text_measurement import TextMeasurementService
from archium.infrastructure.renderers.pptxgen.design_token_adapter import (
    design_system_to_pptx_theme,
)
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import (
    PptxLayoutPlanAdapter,
    SlideContentBundle,
)


def test_text_measurement_cjk_and_latin() -> None:
    service = TextMeasurementService()
    style = default_presentation_design_system().typography.body
    assert service.estimate_lines("你好世界", box_width_in=2.0, style=style) >= 1
    assert service.fits("短句", box_width_in=4.0, box_height_in=1.0, style=style)


def test_pptx_layout_plan_adapter_preserves_coordinates() -> None:
    design = default_presentation_design_system()
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="lead_and_points",
        page_width=10,
        page_height=5.625,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        reading_order=["title"],
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=0.7,
                y=0.45,
                width=8.6,
                height=0.5,
                style_token="title",
            )
        ],
    )
    instruction = PptxLayoutPlanAdapter().render_slide(
        plan,
        design,
        SlideContentBundle(page_number=3),
    )
    assert instruction.elements[0]["x"] == 0.7
    assert instruction.elements[0]["y"] == 0.45
    assert instruction.elements[0]["w"] == 8.6
    assert instruction.to_dict()["layout_family"] == "textual_argument"
    theme = design_system_to_pptx_theme(design)
    assert theme["slide_size"]["width"] == 10.0
    assert "primary" in theme["colors"]

"""Layout Quality Score naming / scope tests."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.domain.visual import (
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
    LayoutQualityScore,
    LayoutScore,
    default_presentation_design_system,
)
from archium.domain.visual.enums import LayoutContentType


def test_layout_quality_score_alias_and_kind() -> None:
    assert LayoutQualityScore is LayoutScore
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="lead_and_points",
        page_width=10,
        page_height=5.625,
        design_system_id=uuid4(),
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
                width=8,
                height=0.5,
                style_token="title",
            )
        ],
    )
    report = LayoutValidationService().validate(
        plan, default_presentation_design_system(), require_source=False
    )
    assert report.layout_score is not None
    assert report.layout_score.score_kind == "layout_quality"
    assert report.layout_quality_score == report.score
    assert "Layout Quality Score" in (LayoutScore.__doc__ or "")
    assert "not** a Visual Quality Score" in (LayoutScore.__doc__ or "")
    assert "Visual Critic" in (LayoutScore.__doc__ or "")

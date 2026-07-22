"""Tests for SlideCapacityBudget pre-layout capacity gate."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.layout_repair_service import LayoutRepairService
from archium.application.visual.slide_capacity_service import SlideCapacityService
from archium.domain.content_adaptation import (
    ContentAdaptationAction,
    suggest_content_adaptations,
)
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import (
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    LayoutIssueSeverity,
    VisualContentType,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.slide_capacity_budget import CAPACITY_OVERLOAD_RULE
from archium.domain.visual.validation import (
    LAYOUT_TEXT_OVERFLOW,
    LayoutValidationIssue,
    LayoutValidationReport,
)
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.geometry import safe_area


def _slide(
    *,
    title: str = "结论",
    message: str = "短句。",
    key_points: list[str] | None = None,
) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title=title,
        message=message,
        slide_type=SlideType.CONTENT,
        key_points=key_points or [],
    )


def _overloaded_slide() -> SlideSpec:
    """Bypass SlideSpec editorial validators to stress capacity math."""
    return SlideSpec.model_construct(
        id=uuid4(),
        presentation_id=uuid4(),
        lineage_id=uuid4(),
        logical_key="ch1-p0",
        chapter_id="ch1",
        order=0,
        title="容量超载页",
        message=("这是需要占据大量垂直空间的冗长论述内容" * 40),
        slide_type=SlideType.CONTENT,
        layout_id="default",
        key_points=[("要点说明" * 30) for _ in range(8)],
        visual_requirements=[],
        source_citations=[],
        version=1,
    )


def _site_plan_intent(*, slide_id=None, presentation_id=None) -> VisualIntent:
    return VisualIntent(
        slide_id=slide_id or uuid4(),
        presentation_id=presentation_id or uuid4(),
        communication_goal="展示总平面更新策略",
        audience_takeaway="看清分区与流线",
        visual_priority="图纸主导",
        dominant_content_type=VisualContentType.SITE_PLAN,
        preferred_layout_families=[LayoutFamily.DRAWING_FOCUS],
    )


def test_usable_matches_safe_area() -> None:
    design = default_presentation_design_system()
    safe = safe_area(design)
    budget = SlideCapacityService().estimate(_slide(), design)
    assert abs(budget.usable_width - safe.width) < 1e-6
    assert abs(budget.usable_height - safe.height) < 1e-6
    assert budget.capacity_ratio < 1.0
    assert budget.recommended_action == "proceed"


def test_short_content_fits() -> None:
    design = default_presentation_design_system()
    budget = SlideCapacityService().estimate(
        _slide(title="标题", message="一页一个中心结论。"),
        design,
    )
    assert budget.capacity_ratio < 1.0
    assert budget.overflow_risk < 0.5


def test_long_body_overloads_and_recommends_adaptation() -> None:
    design = default_presentation_design_system()
    budget = SlideCapacityService().estimate(_overloaded_slide(), design)
    assert budget.capacity_ratio > 1.0
    assert budget.recommended_action in {"adapt_content", "split_slide"}
    assert budget.is_overloaded


def test_drawing_family_requires_image_area() -> None:
    design = default_presentation_design_system()
    intent = _site_plan_intent()
    budget = SlideCapacityService().estimate(
        _slide(),
        design,
        visual_intent=intent,
        layout_family=LayoutFamily.DRAWING_FOCUS,
    )
    assert budget.image_area_required > 0
    assert budget.annotation_area_required > 0


def test_content_adaptation_uses_capacity_gate() -> None:
    design = default_presentation_design_system()
    slide = _overloaded_slide()
    budget = SlideCapacityService().estimate(slide, design)
    assert budget.is_overloaded
    suggestions = suggest_content_adaptations(slide, capacity_budget=budget)
    assert suggestions
    assert any(CAPACITY_OVERLOAD_RULE in item.trigger_rule_codes for item in suggestions)
    assert suggestions[0].action in {
        ContentAdaptationAction.SHORTEN,
        ContentAdaptationAction.SPLIT_SLIDE,
    }


def test_repair_forbids_font_shrink_when_capacity_overloaded() -> None:
    design = default_presentation_design_system()
    long_text = "溢出文字" * 60
    element = LayoutElement(
        id="body",
        role=LayoutElementRole.BODY_TEXT,
        content_type=LayoutContentType.TEXT,
        x=0.5,
        y=1.0,
        width=2.0,
        height=0.4,
        z_index=1,
        text_content=long_text,
        style_token="body",
    )
    plan = LayoutPlan(
        slide_id=uuid4(),
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="lead_and_points",
        page_width=design.page.width,
        page_height=design.page.height,
        reading_order=["body"],
        whitespace_ratio=0.4,
        elements=[element],
    )
    report = LayoutValidationReport(
        score=0.2,
        issues=[
            LayoutValidationIssue(
                rule_code=LAYOUT_TEXT_OVERFLOW,
                severity=LayoutIssueSeverity.ERROR,
                message="overflow",
                element_ids=["body"],
                auto_repairable=True,
            )
        ],
    )
    budget = SlideCapacityService().estimate(_overloaded_slide(), design)
    assert budget.is_overloaded
    before_token = element.style_token
    before_override = element.font_size_override
    result = LayoutRepairService().repair(
        plan,
        report,
        design,
        capacity_budget=budget,
    )
    repaired = next(el for el in result.plan.elements if el.id == "body")
    assert repaired.style_token == before_token
    assert repaired.font_size_override == before_override
    assert result.plan.overflow_policy.value == "split"

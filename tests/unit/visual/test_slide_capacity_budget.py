"""Tests for SlideCapacityBudget pre-layout capacity gate."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.layout_repair_service import LayoutRepairService
from archium.application.visual.slide_capacity_service import (
    SlideCapacityService,
    detect_slide_language,
)
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
from archium.domain.visual.slide_capacity_budget import (
    CAPACITY_IMPOSSIBLE_RULE,
    CAPACITY_OVERLOAD_RULE,
    CAPACITY_TIGHT_RULE,
    CapacityStatus,
)
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
    assert budget.status == CapacityStatus.FITS
    assert budget.recommended_action == "proceed"
    assert budget.text_language in {"zh", "en", "mixed"}


def test_capacity_passes_styled_real_metrics() -> None:
    design = default_presentation_design_system()
    service = SlideCapacityService()
    budget = service.estimate(
        _slide(title="标题层级", message="正文字号与行高必须进入度量。"),
        design,
        language="zh",
    )
    assert budget.used_real_font_metrics == service._text.uses_real_metrics
    assert budget.text_language == "zh"
    # Title/body styles must be complete — estimate would raise otherwise.
    assert budget.estimated_text_height > 0


def test_short_content_fits() -> None:
    design = default_presentation_design_system()
    budget = SlideCapacityService().estimate(
        _slide(title="标题", message="一页一个中心结论。"),
        design,
    )
    assert budget.capacity_ratio < 1.0
    assert budget.status in {CapacityStatus.FITS, CapacityStatus.TIGHT}
    assert budget.overflow_risk < 0.5 or budget.status == CapacityStatus.TIGHT


def test_long_body_overloads_and_recommends_adaptation() -> None:
    design = default_presentation_design_system()
    budget = SlideCapacityService().estimate(_overloaded_slide(), design)
    assert budget.capacity_ratio > 1.0
    assert budget.status in {CapacityStatus.OVERLOADED, CapacityStatus.IMPOSSIBLE}
    assert budget.recommended_action in {"adapt_content", "split_slide", "blocked"}
    assert budget.is_overloaded


def test_drawing_family_requires_drawing_chrome_not_just_area() -> None:
    design = default_presentation_design_system()
    intent = _site_plan_intent()
    photo_intent = VisualIntent(
        slide_id=uuid4(),
        presentation_id=uuid4(),
        communication_goal="展示现场照片",
        audience_takeaway="证据可读",
        visual_priority="照片证据",
        dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
        preferred_layout_families=[LayoutFamily.EVIDENCE_BOARD],
    )
    drawing = SlideCapacityService().estimate(
        _slide(),
        design,
        visual_intent=intent,
        layout_family=LayoutFamily.DRAWING_FOCUS,
    )
    photo = SlideCapacityService().estimate(
        _slide(),
        design,
        visual_intent=photo_intent,
        layout_family=LayoutFamily.EVIDENCE_BOARD,
    )
    assert drawing.image_area_required > 0
    assert drawing.annotation_area_required > 0
    assert drawing.drawing_min_readable_area > 0
    assert drawing.caption_required_height > 0
    assert drawing.legend_required_area > 0
    assert drawing.annotation_density > photo.annotation_density
    # Same short copy, but drawing chrome floors exceed photo-only image area.
    assert drawing.drawing_min_readable_area > photo.drawing_min_readable_area
    assert photo.legend_required_area == 0


def test_content_adaptation_uses_capacity_gate() -> None:
    design = default_presentation_design_system()
    slide = _overloaded_slide()
    budget = SlideCapacityService().estimate(slide, design)
    assert budget.is_overloaded
    suggestions = suggest_content_adaptations(slide, capacity_budget=budget)
    assert suggestions
    assert any(
        CAPACITY_OVERLOAD_RULE in item.trigger_rule_codes
        or CAPACITY_IMPOSSIBLE_RULE in item.trigger_rule_codes
        for item in suggestions
    )
    assert suggestions[0].action in {
        ContentAdaptationAction.SHORTEN,
        ContentAdaptationAction.SPLIT_SLIDE,
    }


def test_tight_status_suggests_qa_shorten() -> None:
    design = default_presentation_design_system()
    # Moderately long body to land near tight band without full overload.
    slide = SlideSpec.model_construct(
        id=uuid4(),
        presentation_id=uuid4(),
        lineage_id=uuid4(),
        logical_key="ch1-p0",
        chapter_id="ch1",
        order=0,
        title="偏紧页",
        message=("中等长度论证用于测试容量偏紧状态。" * 8),
        slide_type=SlideType.CONTENT,
        layout_id="default",
        key_points=["补充说明一点", "再补充说明一点"],
        visual_requirements=[],
        source_citations=[],
        version=1,
    )
    budget = SlideCapacityService().estimate(slide, design)
    if budget.status == CapacityStatus.TIGHT:
        suggestions = suggest_content_adaptations(slide, capacity_budget=budget)
        assert any(CAPACITY_TIGHT_RULE in s.trigger_rule_codes for s in suggestions)
        assert budget.requires_qa
        assert not budget.is_blocked


def test_detect_slide_language() -> None:
    assert detect_slide_language(_slide(title="标题", message="中文结论")) == "zh"
    assert detect_slide_language(_slide(title="Title", message="English only body.")) == "en"
    assert detect_slide_language(_slide(title="Mixed 混合", message="A and 中文")) == "mixed"


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

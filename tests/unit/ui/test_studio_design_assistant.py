"""Unit tests for Studio page intelligence and design assistant."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.slide import SlideSpec
from archium.domain.slide_role import SlideRole, VisualStrategy
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.validation import LayoutValidationReport
from archium.ui.label_map import slide_role_label
from archium.ui.studio.deck_overview_panel import role_color
from archium.ui.studio.design_assistant_panel import (
    collect_assistant_findings,
    DEFAULT_QUICK_ACTIONS,
)
from archium.ui.studio.page_intelligence_strip import build_page_intelligence
from archium.ui.visual_service import SlideVisualSnapshot


def test_slide_role_label_user_mode() -> None:
    assert slide_role_label(SlideRole.PROBLEM_ANALYSIS) == "问题分析"
    assert slide_role_label(SlideRole.STRATEGY) == "策略"


def test_build_page_intelligence_from_slide_spec() -> None:
    slide_id = uuid4()
    presentation_id = uuid4()
    slide = SlideSpec(
        id=slide_id,
        presentation_id=presentation_id,
        chapter_id="ch-1",
        order=2,
        title="交通冲突",
        message="基地东侧人车混行",
        slide_role=SlideRole.PROBLEM_ANALYSIS,
        visual_strategy=VisualStrategy(graphic_language="分析叠加图"),
    )
    plan = LayoutPlan(
        slide_id=slide_id,
        visual_intent_id=uuid4(),
        design_system_id=uuid4(),
        layout_family=LayoutFamily.ANALYTICAL_DIAGRAM,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
    )
    snapshot = SlideVisualSnapshot(
        slide=slide,
        visual_intent=None,
        layout_plan=plan,
        validation=LayoutValidationReport(score=0.86, issues=[]),
    )
    intel = build_page_intelligence(snapshot)
    assert intel is not None
    assert "P3" in intel.page_label
    assert intel.role == "问题分析"
    assert "人车混行" in intel.expression
    assert intel.visual_language == "分析叠加图"
    assert intel.layout_family == "分析图"
    assert intel.score == 86


def test_collect_assistant_findings_includes_partner_tips() -> None:
    slide = SlideSpec(
        id=uuid4(),
        presentation_id=uuid4(),
        chapter_id="ch-1",
        order=0,
        title="现状",
        message="x" * 140,
        key_points=["a", "b", "c", "d", "e"],
        slide_role=SlideRole.PROBLEM_ANALYSIS,
    )
    snapshot = SlideVisualSnapshot(slide=slide, visual_intent=None, layout_plan=None)
    findings = collect_assistant_findings(snapshot)
    assert findings
    assert any("信息过多" in item.message for item in findings)


def test_role_color_maps_problem_to_red_tone() -> None:
    assert role_color(SlideRole.PROBLEM_ANALYSIS) == "#d92d20"
    assert role_color(SlideRole.STRATEGY) == "#12b76a"


def test_default_quick_actions_present() -> None:
    labels = {item.label for item in DEFAULT_QUICK_ACTIONS}
    assert "扩大主图" in labels
    assert "减少文字" in labels

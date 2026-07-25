"""Unit tests for page / outline partner AI suggestions."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.slide import SlideSpec
from archium.domain.slide_intent import SlideIntent
from archium.domain.slide_role import SlideRole, VisualStrategy
from archium.ui.studio.page_ai_suggestions import (
    outline_partner_suggestions,
    page_partner_suggestions,
)


def test_page_partner_suggestions_flags_dense_copy() -> None:
    slide = SlideSpec(
        id=uuid4(),
        presentation_id=uuid4(),
        chapter_id="ch-1",
        order=0,
        title="现状问题",
        message="x" * 140,
        key_points=["a", "b", "c", "d", "e"],
        slide_role=SlideRole.PROBLEM_ANALYSIS,
    )
    tips = page_partner_suggestions(slide)
    assert any("信息过多" in tip for tip in tips)
    assert any("剖面" in tip or "图解" in tip for tip in tips)


def test_page_partner_suggestions_uses_visual_strategy() -> None:
    slide = SlideSpec(
        id=uuid4(),
        presentation_id=uuid4(),
        chapter_id="ch-1",
        order=1,
        title="策略",
        message="核心策略一句",
        key_points=["一项"],
        slide_role=SlideRole.STRATEGY,
        visual_strategy=VisualStrategy(recommended_diagram="剖面叠合"),
    )
    tips = page_partner_suggestions(slide)
    assert any("剖面叠合" in tip for tip in tips)


def test_outline_partner_suggestions_missing_conclusion() -> None:
    intent = SlideIntent(
        order=0,
        page_task="基地分析",
        central_conclusion="",
        slide_role=SlideRole.SITE_ANALYSIS,
    )
    tips = outline_partner_suggestions(intent)
    assert any("中心结论" in tip for tip in tips)
    assert any("证据" in tip or "剖面" in tip or "流线" in tip for tip in tips)

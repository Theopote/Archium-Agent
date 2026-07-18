"""Unit tests for read-only Visual Critic (Visual Quality, not Layout Quality)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from archium.application.visual.visual_critic_service import VisualCriticService
from archium.domain.visual import (
    CRITIC_HERO_WEAK,
    CRITIC_PAGE_REPETITION,
    CRITIC_READING_ORDER_AWKWARD,
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
    VisualCriticReport,
)
from archium.domain.visual.enums import LayoutContentType


def _plan(*elements: LayoutElement, family: LayoutFamily = LayoutFamily.HERO) -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        layout_family=family,
        layout_variant="split",
        page_width=10,
        page_height=5.625,
        hero_element_id="hero" if any(el.id == "hero" for el in elements) else None,
        reading_order=[el.id for el in elements],
        whitespace_ratio=0.3,
        elements=list(elements),
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )


class TestVisualCriticService:
    def test_report_is_visual_quality_not_layout_quality(self) -> None:
        plan = _plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=0.7,
                y=0.4,
                width=8,
                height=0.5,
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=0.7,
                y=1.1,
                width=8.0,
                height=3.6,
            ),
        )
        report = VisualCriticService().evaluate_plan(plan)
        assert isinstance(report, VisualCriticReport)
        assert report.score_kind == "visual_quality"
        assert report.method == "heuristic_v0"
        assert report.total_score is not None
        assert report.dimensions.hero_prominence is not None
        assert report.dimensions.hero_prominence >= 0.5

    def test_weak_hero_emits_finding(self) -> None:
        plan = _plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=0.7,
                y=1.2,
                width=1.5,
                height=1.0,
            ),
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="大量正文占位",
                x=3.0,
                y=1.2,
                width=6.0,
                height=3.5,
            ),
        )
        report = VisualCriticService().evaluate_plan(plan)
        assert any(item.rule_code == CRITIC_HERO_WEAK for item in report.findings)

    def test_awkward_reading_order_emits_finding(self) -> None:
        plan = _plan(
            LayoutElement(
                id="first",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="应在上",
                x=0.7,
                y=4.0,
                width=8,
                height=0.5,
            ),
            LayoutElement(
                id="second",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="应在下",
                x=0.7,
                y=0.5,
                width=8,
                height=1.0,
            ),
        )
        report = VisualCriticService().evaluate_plan(plan)
        assert any(
            item.rule_code == CRITIC_READING_ORDER_AWKWARD for item in report.findings
        )
        assert report.dimensions.reading_order_naturalness is not None
        assert report.dimensions.reading_order_naturalness < 0.55

    def test_deck_repetition_finding(self) -> None:
        shared = (
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="A",
                x=0.7,
                y=0.4,
                width=8,
                height=0.5,
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=0.7,
                y=1.1,
                width=8.0,
                height=3.6,
            ),
        )
        plan_a = _plan(*shared)
        plan_b = _plan(
            *[el.model_copy(deep=True) for el in shared],
        )
        reports = VisualCriticService().evaluate_deck([plan_a, plan_b])
        assert len(reports) == 2
        assert any(
            item.rule_code == CRITIC_PAGE_REPETITION
            for report in reports
            for item in report.findings
        )

    def test_color_chaos_from_screenshot(self, tmp_path) -> None:  # noqa: ANN001
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        # Highly varied palette → lower color_calm → COLOR_CHAOS finding.
        image = Image.new("RGB", (200, 120))
        pixels = image.load()
        assert pixels is not None
        for x in range(200):
            for y in range(120):
                pixels[x, y] = ((x * 17) % 256, (y * 31) % 256, (x * y) % 256)
        path = tmp_path / "chaos.png"
        image.save(path)

        plan = _plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=0.7,
                y=1.0,
                width=8,
                height=3.5,
            )
        )
        report = VisualCriticService().evaluate_plan(plan, image_path=path)
        assert report.source_image is not None
        assert report.dimensions.color_chaos is not None
        assert report.dimensions.color_chaos < 0.7

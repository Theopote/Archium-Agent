"""Phase 3 Visual Critic — adversarial golden + false-positive budget."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.visual_critic_service import VisualCriticService
from archium.domain.visual import (
    CRITIC_ALIGNMENT_DRIFT,
    CRITIC_COPY_DENSITY_HIGH,
    CRITIC_HERO_WEAK,
    CRITIC_TITLE_WEAK,
    CRITIC_VISUAL_NOISE_HIGH,
    CRITIC_WHITESPACE_WEAK,
    LayoutContentType,
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
)


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


# Intentionally broken pages → expected rule codes (screenshot_v1 structure).
_ADVERSARIAL_CASES: list[tuple[str, LayoutPlan, frozenset[str]]] = [
    (
        "title_weak",
        _plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="弱标题",
                x=0.7,
                y=0.3,
                width=2.0,
                height=0.25,
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=0.7,
                y=1.0,
                width=8.0,
                height=3.8,
            ),
        ),
        frozenset({CRITIC_TITLE_WEAK}),
    ),
    (
        "copy_density_high",
        _plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="信息过载",
                x=0.5,
                y=0.3,
                width=9.0,
                height=0.5,
            ),
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="长文占位 " * 40,
                x=0.5,
                y=1.0,
                width=9.0,
                height=4.0,
            ),
        ),
        frozenset({CRITIC_COPY_DENSITY_HIGH}),
    ),
    (
        "hero_weak",
        _plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="主图过小",
                x=0.5,
                y=0.3,
                width=9.0,
                height=0.5,
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=0.5,
                y=1.2,
                width=1.8,
                height=1.2,
            ),
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="旁注",
                x=3.0,
                y=1.2,
                width=6.0,
                height=2.0,
            ),
        ),
        frozenset({CRITIC_HERO_WEAK}),
    ),
    (
        "title_and_copy",
        _plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="双伤",
                x=0.5,
                y=0.2,
                width=1.5,
                height=0.2,
            ),
            LayoutElement(
                id="lead",
                role=LayoutElementRole.LEAD_STATEMENT,
                content_type=LayoutContentType.TEXT,
                text_content="主张过长",
                x=0.5,
                y=0.6,
                width=9.0,
                height=1.2,
            ),
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="正文过密",
                x=0.5,
                y=2.0,
                width=9.0,
                height=3.0,
            ),
        ),
        frozenset({CRITIC_TITLE_WEAK, CRITIC_COPY_DENSITY_HIGH}),
    ),
    (
        "hero_and_copy",
        _plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="弱主图+密文",
                x=0.5,
                y=0.3,
                width=9.0,
                height=0.55,
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=0.5,
                y=1.0,
                width=2.0,
                height=1.0,
            ),
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="正文墙",
                x=2.8,
                y=1.0,
                width=6.7,
                height=4.0,
            ),
        ),
        frozenset({CRITIC_HERO_WEAK, CRITIC_COPY_DENSITY_HIGH}),
    ),
]


def _good_page() -> LayoutPlan:
    return _plan(
        LayoutElement(
            id="title",
            role=LayoutElementRole.TITLE,
            content_type=LayoutContentType.TEXT,
            text_content="基地策略",
            x=0.7,
            y=0.35,
            width=8.5,
            height=0.55,
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
        LayoutElement(
            id="caption",
            role=LayoutElementRole.CAPTION,
            content_type=LayoutContentType.TEXT,
            text_content="北向城市界面",
            x=0.7,
            y=4.9,
            width=5.0,
            height=0.35,
        ),
    )


class TestVisualCriticScreenshotV03:
    def test_adversarial_hit_rate_at_least_80_percent(self) -> None:
        critic = VisualCriticService()
        expected_hits = 0
        actual_hits = 0
        misses: list[str] = []
        for name, plan, expected in _ADVERSARIAL_CASES:
            report = critic.evaluate_plan(plan)
            codes = {item.rule_code for item in report.findings}
            for code in expected:
                expected_hits += 1
                if code in codes:
                    actual_hits += 1
                else:
                    misses.append(f"{name}:{code}")
            assert report.method == "screenshot_v1"
            # Actionable % language for structure findings.
            for item in report.findings:
                if item.rule_code in {
                    CRITIC_TITLE_WEAK,
                    CRITIC_COPY_DENSITY_HIGH,
                    CRITIC_HERO_WEAK,
                }:
                    assert item.suggestion is not None
                    assert "~" in item.suggestion
        rate = actual_hits / max(expected_hits, 1)
        assert rate >= 0.8, f"hit_rate={rate:.2%} misses={misses}"

    def test_good_page_false_positive_budget(self) -> None:
        """Human-acceptable pages: allow incidental findings, not title/copy spam."""
        report = VisualCriticService().evaluate_plan(_good_page())
        codes = {item.rule_code for item in report.findings}
        assert CRITIC_TITLE_WEAK not in codes
        assert CRITIC_COPY_DENSITY_HIGH not in codes
        assert CRITIC_HERO_WEAK not in codes
        assert CRITIC_WHITESPACE_WEAK not in codes
        assert CRITIC_ALIGNMENT_DRIFT not in codes
        assert CRITIC_VISUAL_NOISE_HIGH not in codes
        # Budget: at most one incidental non-structure warning on a good page.
        structure_codes = {CRITIC_TITLE_WEAK, CRITIC_COPY_DENSITY_HIGH}
        incidental = [
            item
            for item in report.findings
            if item.rule_code not in structure_codes
        ]
        assert len(incidental) <= 1

    def test_structure_suggestions_are_actionable_percentages(self) -> None:
        plan = _ADVERSARIAL_CASES[0][1]
        report = VisualCriticService().evaluate_plan(plan)
        title = next(item for item in report.findings if item.rule_code == CRITIC_TITLE_WEAK)
        assert title.suggestion is not None
        assert "~25%" in title.suggestion

        dense = _ADVERSARIAL_CASES[1][1]
        dense_report = VisualCriticService().evaluate_plan(dense)
        copy = next(
            item
            for item in dense_report.findings
            if item.rule_code == CRITIC_COPY_DENSITY_HIGH
        )
        assert copy.suggestion is not None
        assert "~30%" in copy.suggestion

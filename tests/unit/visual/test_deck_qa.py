"""Unit tests for deck-level consistency QA."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.deck_qa_service import DeckQAService
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual import (
    DECK_CHROME_INCONSISTENT,
    DECK_FOOTER_INCONSISTENT,
    DECK_IMAGE_SCALE_INCONSISTENT,
    DECK_REPEATED_LAYOUT_FAMILY,
    DECK_TYPOGRAPHY_INCONSISTENT,
    DECK_WEAK_SECTION_TRANSITION,
    DeckQAReport,
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
)
from archium.domain.visual.enums import LayoutContentType


def _plan(
    *elements: LayoutElement,
    family: LayoutFamily = LayoutFamily.HERO,
    slide_id=None,  # noqa: ANN001
) -> LayoutPlan:
    return LayoutPlan(
        slide_id=slide_id or uuid4(),
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


def _chrome(*, y: float = 5.1, page_x: float = 9.0) -> list[LayoutElement]:
    return [
        LayoutElement(
            id="source",
            role=LayoutElementRole.SOURCE,
            content_type=LayoutContentType.TEXT,
            text_content="来源",
            x=0.7,
            y=y,
            width=6.0,
            height=0.25,
            style_token="source",
        ),
        LayoutElement(
            id="page",
            role=LayoutElementRole.PAGE_NUMBER,
            content_type=LayoutContentType.TEXT,
            text_content="1",
            x=page_x,
            y=y,
            width=0.5,
            height=0.25,
            style_token="source",
        ),
    ]


class TestDeckQAService:
    def test_skips_single_slide(self) -> None:
        report = DeckQAService().evaluate(
            [
                _plan(
                    LayoutElement(
                        id="title",
                        role=LayoutElementRole.TITLE,
                        content_type=LayoutContentType.TEXT,
                        text_content="A",
                        x=0.7,
                        y=0.4,
                        width=8,
                        height=0.5,
                        style_token="title",
                    )
                )
            ]
        )
        assert isinstance(report, DeckQAReport)
        assert report.score_kind == "deck_consistency"
        assert report.total_score == 1.0
        assert not report.findings

    def test_repeated_family_run(self) -> None:
        plans = [
            _plan(
                LayoutElement(
                    id="hero",
                    role=LayoutElementRole.HERO_VISUAL,
                    content_type=LayoutContentType.IMAGE,
                    x=0.7,
                    y=1.0,
                    width=8,
                    height=3.5,
                ),
                family=LayoutFamily.HERO,
            )
            for _ in range(3)
        ]
        report = DeckQAService().evaluate(plans)
        assert any(item.rule_code == DECK_REPEATED_LAYOUT_FAMILY for item in report.findings)
        assert report.dimensions.layout_variety is not None
        assert report.dimensions.layout_variety < 1.0

    def test_footer_drift(self) -> None:
        plans = [
            _plan(*_chrome(y=5.1)),
            _plan(*_chrome(y=4.4)),
        ]
        report = DeckQAService().evaluate(plans)
        assert any(item.rule_code == DECK_FOOTER_INCONSISTENT for item in report.findings)

    def test_typography_inconsistent(self) -> None:
        plans = [
            _plan(
                LayoutElement(
                    id="title",
                    role=LayoutElementRole.TITLE,
                    content_type=LayoutContentType.TEXT,
                    text_content="A",
                    x=0.7,
                    y=0.4,
                    width=8,
                    height=0.5,
                    style_token="title",
                )
            ),
            _plan(
                LayoutElement(
                    id="title",
                    role=LayoutElementRole.TITLE,
                    content_type=LayoutContentType.TEXT,
                    text_content="B",
                    x=0.7,
                    y=0.4,
                    width=8,
                    height=0.5,
                    style_token="display",
                )
            ),
            _plan(
                LayoutElement(
                    id="title",
                    role=LayoutElementRole.TITLE,
                    content_type=LayoutContentType.TEXT,
                    text_content="C",
                    x=0.7,
                    y=0.4,
                    width=8,
                    height=0.5,
                    style_token="heading",
                )
            ),
        ]
        report = DeckQAService().evaluate(plans)
        assert any(
            item.rule_code == DECK_TYPOGRAPHY_INCONSISTENT for item in report.findings
        )

    def test_image_scale_inconsistent(self) -> None:
        plans = [
            _plan(
                LayoutElement(
                    id="hero",
                    role=LayoutElementRole.HERO_VISUAL,
                    content_type=LayoutContentType.IMAGE,
                    x=0.7,
                    y=1.0,
                    width=8.5,
                    height=3.5,
                )
            ),
            _plan(
                LayoutElement(
                    id="hero",
                    role=LayoutElementRole.HERO_VISUAL,
                    content_type=LayoutContentType.IMAGE,
                    x=0.7,
                    y=1.0,
                    width=2.0,
                    height=2.0,
                )
            ),
        ]
        report = DeckQAService().evaluate(plans)
        assert any(
            item.rule_code == DECK_IMAGE_SCALE_INCONSISTENT for item in report.findings
        )

    def test_chrome_intermittent(self) -> None:
        plans = [
            _plan(*_chrome()),
            _plan(
                LayoutElement(
                    id="title",
                    role=LayoutElementRole.TITLE,
                    content_type=LayoutContentType.TEXT,
                    text_content="无页脚",
                    x=0.7,
                    y=0.4,
                    width=8,
                    height=0.5,
                    style_token="title",
                )
            ),
        ]
        report = DeckQAService().evaluate(plans)
        assert any(item.rule_code == DECK_CHROME_INCONSISTENT for item in report.findings)

    def test_weak_section_transition(self) -> None:
        slide_id = uuid4()
        plan = _plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=0.7,
                y=1.0,
                width=8,
                height=3.5,
            ),
            family=LayoutFamily.METRIC_DASHBOARD,
            slide_id=slide_id,
        )
        # Need a second plan so deck QA runs.
        other = _plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="内容",
                x=0.7,
                y=0.4,
                width=8,
                height=0.5,
                style_token="title",
            ),
            family=LayoutFamily.HERO,
        )
        slides = [
            SlideSpec(
                presentation_id=uuid4(),
                chapter_id="ch1",
                order=0,
                title="章节",
                message="过渡",
                slide_type=SlideType.SECTION,
                id=slide_id,
            )
        ]
        # Force slide_id match — SlideSpec may generate its own id; rebuild.
        slides[0] = slides[0].model_copy(update={"id": slide_id})
        report = DeckQAService().evaluate([plan, other], slides=slides)
        assert any(
            item.rule_code == DECK_WEAK_SECTION_TRANSITION for item in report.findings
        )

    def test_palette_drift_unknown_token(self) -> None:
        from archium.domain.visual import DECK_PALETTE_DRIFT, default_presentation_design_system

        design = default_presentation_design_system()
        plans = [
            _plan(
                LayoutElement(
                    id="title",
                    role=LayoutElementRole.TITLE,
                    content_type=LayoutContentType.TEXT,
                    text_content="A",
                    x=0.7,
                    y=0.4,
                    width=8,
                    height=0.5,
                    style_token="title",
                )
            ),
            _plan(
                LayoutElement(
                    id="title",
                    role=LayoutElementRole.TITLE,
                    content_type=LayoutContentType.TEXT,
                    text_content="B",
                    x=0.7,
                    y=0.4,
                    width=8,
                    height=0.5,
                    style_token="not_a_real_token",
                )
            ),
        ]
        # Force a made-up color token via typography mutation on a copy is hard;
        # instead inject unknown by using a style that resolve will fail — patch
        # color_tokens_for_plan path: empty second set vs first still scores high.
        # Use design_system with evaluate; unknown comes when token name is valid
        # typography name but color_token is bogus — set body.color_token temporarily.
        design.typography.title.color_token = "primary_text"
        design.typography.body.color_token = "totally_unknown_hex_token"
        plans[1].elements[0].style_token = "body"
        report = DeckQAService().evaluate(
            plans,
            design_system=design,
            palette_strategy="克制中性色，避免高饱和跳变",
        )
        assert any(item.rule_code == DECK_PALETTE_DRIFT for item in report.findings)
        assert report.dimensions.palette_consistency is not None

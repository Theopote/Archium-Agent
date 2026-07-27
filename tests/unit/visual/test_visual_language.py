"""Unit tests for Visual Language Engine v1."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.page_direction_service import PageDirectionService
from archium.application.visual.showcase_case_001 import build_case_001_render_bundle
from archium.application.visual.visual_language_apply import apply_visual_language_to_plan
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
from archium.domain.visual.visual_concept import VisualMetaphor
from archium.domain.visual.visual_language import TypographyRecipeId


def _slide(title: str, message: str, *, order: int = 0) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="demo",
        order=order,
        title=title,
        message=message,
        key_points=["要点"],
    )


def test_cover_gets_giant_bilingual_language() -> None:
    slide = _slide("封面", "老院区更新：不停业实施的空间策略")
    direction = PageDirectionService().direct(slide)
    assert direction.visual_language is not None
    typo = direction.visual_language.typography
    assert typo.recipe == TypographyRecipeId.GIANT_BILINGUAL
    assert typo.bilingual is True
    assert typo.english_label
    assert typo.title_font_size_pt and typo.title_font_size_pt >= 48
    assert "thin_line" in [
        d.value for d in direction.visual_language.decoration.decorations
    ]


def test_strategy_gets_architectural_title_and_section_index() -> None:
    slide = _slide("设计策略", "策略回应问题：分流、补面积、分期围合。")
    direction = PageDirectionService().direct(slide)
    assert direction.visual_language is not None
    assert (
        direction.visual_language.typography.recipe
        == TypographyRecipeId.ARCHITECTURAL_TITLE
    )
    assert direction.visual_language.decoration.section_index == "01"
    assert direction.visual_language.decoration.card_style.value == "technical_card"


def test_conflict_gets_color_story_and_circulation_symbol() -> None:
    slide = _slide(
        "流线冲突",
        "医患流线交叉与洁污混行是当前最大安全风险。",
        order=5,
    )
    direction = PageDirectionService().direct(slide)
    assert direction.visual_concept is not None
    assert (
        direction.visual_concept.visual_metaphor
        == VisualMetaphor.FRAGMENT_TO_NETWORK
    )
    language = direction.visual_language
    assert language is not None
    assert language.color_story.roles.get("existing") == "gray"
    assert language.color_story.roles.get("conflict") == "red"
    assert language.color_story.meaning.get("red") == "conflict"
    assert any(s.value == "circulation_flow" for s in language.symbols)


def test_overview_does_not_get_giant_title() -> None:
    slide = _slide(
        "现状问题总览",
        "现状问题：拥堵、交叉、老化三类并存。",
        order=4,
    )
    direction = PageDirectionService().direct(slide)
    assert direction.visual_language is not None
    assert (
        direction.visual_language.typography.recipe == TypographyRecipeId.DEFAULT
    )


def test_apply_injects_decoration_elements_on_plan() -> None:
    slide = _slide("封面", "老院区更新")
    direction = PageDirectionService().direct(slide)
    language = direction.visual_language
    assert language is not None
    from archium.domain.visual.enums import LayoutFamily
    from archium.domain.visual.layout import LayoutElement, LayoutPlan

    plan = LayoutPlan(
        slide_id=slide.id,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="full_bleed",
        page_width=13.333,
        page_height=7.5,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="封面",
                x=0.8,
                y=2.0,
                width=8.0,
                height=0.8,
                style_token="title",
            )
        ],
        reading_order=["title"],
    )
    updated = apply_visual_language_to_plan(plan, language, page_order=0)
    ids = {el.id for el in updated.elements}
    assert "vl_thin_line" in ids
    assert "vl_title_en" in ids
    title = next(el for el in updated.elements if el.id == "title")
    assert title.font_size_override and title.font_size_override >= 48


def test_case_001_cover_plan_carries_visual_language_elements() -> None:
    bundle = build_case_001_render_bundle()
    cover_idx = next(i for i, s in enumerate(bundle.slides) if s.title == "封面")
    intent = bundle.intents[cover_idx]
    plan = bundle.plans[cover_idx]
    assert intent.page_direction is not None
    assert intent.page_direction.visual_language is not None
    assert (
        intent.page_direction.visual_language.typography.recipe
        == TypographyRecipeId.GIANT_BILINGUAL
    )
    ids = {el.id for el in plan.elements}
    assert "vl_thin_line" in ids or "vl_title_en" in ids

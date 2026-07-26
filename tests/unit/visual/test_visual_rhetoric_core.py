"""Visual Rhetoric Core — Narrative + Budget + Primitives."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.page_direction_service import PageDirectionService
from archium.application.visual.visual_language_apply import apply_visual_language_to_plan
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.primitives import get_primitive, list_primitives
from archium.domain.visual.visual_budget import VisualBudget
from archium.domain.visual.visual_concept import VisualMetaphor
from archium.domain.visual.visual_language import TypographyRecipeId
from archium.domain.visual.visual_narrative import MotionDirection


def _slide(title: str, message: str, *, order: int = 0) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="demo",
        order=order,
        title=title,
        message=message,
        key_points=["要点"],
    )


def test_fragment_concept_carries_full_visual_narrative() -> None:
    slide = _slide("流线冲突", "医患流线交叉与洁污混行是当前最大安全风险。")
    direction = PageDirectionService().direct(slide)
    concept = direction.visual_concept
    assert concept is not None
    assert concept.narrative is not None
    assert concept.narrative.name == "fragment_to_network"
    assert "connection" in concept.narrative.metaphor
    assert (
        concept.narrative.graphic_language.geometry == "broken_lines_to_curve"
    )
    assert concept.narrative.graphic_language.direction == MotionDirection.CONVERGING
    assert "flow_line" in concept.narrative.recommended_components
    assert direction.visual_budget is not None
    assert direction.visual_budget.decorative_lines <= 2
    assert direction.visual_budget.icons <= 2
    language = direction.visual_language
    assert language is not None
    assert "flow_line" in language.primitive_ids or "circulation" in language.primitive_ids
    card = direction.as_page_claim()
    assert card["visual_budget"] is not None
    assert card["visual_concept"]["narrative"]["name"] == "fragment_to_network"


def test_atmosphere_page_gets_existing_to_transformation() -> None:
    slide = _slide("效果表达", "更新后的城市界面与庭院氛围。", order=17)
    direction = PageDirectionService().direct(slide)
    assert direction.visual_concept is not None
    assert (
        direction.visual_concept.visual_metaphor
        == VisualMetaphor.EXISTING_TO_TRANSFORMATION
    )
    assert direction.visual_concept.narrative is not None
    assert "intervention" in direction.visual_concept.narrative.metaphor
    assert direction.visual_language is not None
    assert direction.visual_language.typography.recipe == TypographyRecipeId.DEFAULT


def test_visual_budget_caps_decoration_injection() -> None:
    slide = _slide("封面", "老院区更新")
    direction = PageDirectionService().direct(slide)
    language = direction.visual_language
    assert language is not None
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
    zero = VisualBudget(
        hero_ratio=0.7,
        accent_elements=0,
        decorative_lines=0,
        icons=0,
        color_blocks=0,
    )
    updated = apply_visual_language_to_plan(
        plan, language, page_order=0, visual_budget=zero
    )
    ids = {el.id for el in updated.elements}
    assert "vl_thin_line" not in ids
    assert not any(i.startswith("vl_symbol_") for i in ids)


def test_primitive_catalog_has_architectural_symbols_not_emoji_pack() -> None:
    assert get_primitive("axis_line") is not None
    assert get_primitive("flow_line") is not None
    assert get_primitive("hero_statement") is not None
    ids = {p.id for p in list_primitives()}
    assert "circulation" in ids
    assert "entrance" in ids
    # Guard against drifting into generic emoji icon libraries.
    assert "car" not in ids
    assert "home" not in ids

"""TypographyRole catalog + LayoutPlan application."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.page_direction_service import PageDirectionService
from archium.application.visual.showcase_case_001 import build_case_001_render_bundle
from archium.application.visual.visual_language_apply import apply_visual_language_to_plan
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.visual_language import (
    ROLE_CATALOG,
    DecorationId,
    DecorationRecipe,
    TitleScale,
    Tracking,
    TypographyRecipe,
    TypographyRecipeId,
    TypographyRole,
    TypographyRoleSpec,
    VisualLanguageSpec,
    primary_role_for_recipe,
    role_spec,
)


def _slide(title: str, message: str, *, order: int = 0) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="demo",
        order=order,
        title=title,
        message=message,
        key_points=["要点"],
    )


def _plan_with_title(title: str = "封面") -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
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
                text_content=title,
                x=0.8,
                y=1.2,
                width=6.0,
                height=0.9,
                z_index=10,
            ),
            LayoutElement(
                id="caption",
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                text_content="图注说明",
                x=0.8,
                y=6.5,
                width=4.0,
                height=0.3,
                z_index=5,
            ),
        ],
        reading_order=["title", "caption"],
    )


def test_role_catalog_covers_all_seven_roles() -> None:
    assert set(ROLE_CATALOG.keys()) == set(TypographyRole)
    for role, spec in ROLE_CATALOG.items():
        assert isinstance(spec, TypographyRoleSpec)
        assert spec.role == role
        assert 8 <= spec.font_size_pt <= 120


def test_recipe_maps_to_primary_role() -> None:
    assert primary_role_for_recipe(TypographyRecipeId.GIANT_BILINGUAL) == TypographyRole.HERO_TITLE
    assert (
        primary_role_for_recipe(TypographyRecipeId.ARCHITECTURAL_TITLE)
        == TypographyRole.SECTION_TITLE
    )


def test_cover_direction_uses_hero_title_role() -> None:
    direction = PageDirectionService().direct(_slide("封面", "老院区更新"))
    assert direction.visual_language is not None
    typo = direction.visual_language.typography
    assert typo.primary_role == TypographyRole.HERO_TITLE
    hero = typo.resolve_role(TypographyRole.HERO_TITLE)
    assert hero.font_size_pt >= 48
    assert hero.style_token == "display"


def test_strategy_direction_uses_section_title_and_index() -> None:
    direction = PageDirectionService().direct(
        _slide("设计策略", "策略回应问题。")
    )
    assert direction.visual_language is not None
    typo = direction.visual_language.typography
    assert typo.primary_role == TypographyRole.SECTION_TITLE
    index = typo.resolve_role(TypographyRole.INDEX)
    assert index.tracking.value == "wide"
    assert index.position.value == "above_title"


def test_apply_stamps_hero_title_and_tech_note_english() -> None:
    language = VisualLanguageSpec(
        typography=TypographyRecipe(
            recipe=TypographyRecipeId.GIANT_BILINGUAL,
            primary_role=TypographyRole.HERO_TITLE,
            scale=TitleScale.GIANT,
            tracking=Tracking.WIDE,
            bilingual=True,
            english_label="HOSPITAL RENEWAL",
            title_font_size_pt=54,
            english_font_size_pt=14,
            letter_spacing_em=0.08,
            opacity=0.95,
        )
    )
    plan = apply_visual_language_to_plan(_plan_with_title(), language)
    title = next(el for el in plan.elements if el.role == LayoutElementRole.TITLE)
    assert title.font_size_override == 54
    assert title.style_token == "display"
    en = next(el for el in plan.elements if el.id == "vl_title_en")
    assert en.font_size_override == 14
    assert en.text_content == "HOSPITAL RENEWAL"
    assert (en.letter_spacing or 0) >= 0.1


def test_section_index_uses_index_role_spec() -> None:
    language = VisualLanguageSpec(
        typography=TypographyRecipe(
            recipe=TypographyRecipeId.ARCHITECTURAL_TITLE,
            primary_role=TypographyRole.SECTION_TITLE,
            scale=TitleScale.LARGE,
            tracking=Tracking.WIDE,
            title_font_size_pt=36,
        ),
        decoration=DecorationRecipe(
            decorations=[DecorationId.SECTION_LABEL_01],
            section_index="01",
            section_label="STRATEGY",
        ),
    )
    plan = apply_visual_language_to_plan(_plan_with_title("设计策略"), language)
    index = next(el for el in plan.elements if el.id == "vl_section_index")
    assert index.font_size_override == ROLE_CATALOG[TypographyRole.INDEX].font_size_pt
    assert (index.letter_spacing or 0) >= 0.12
    assert "01" in (index.text_content or "")


def test_case_001_cover_plan_has_hero_typography() -> None:
    bundle = build_case_001_render_bundle()
    cover_idx = next(i for i, s in enumerate(bundle.slides) if s.title == "封面")
    direction = bundle.intents[cover_idx].page_direction
    assert direction is not None
    assert direction.visual_language is not None
    assert (
        direction.visual_language.typography.primary_role == TypographyRole.HERO_TITLE
    )
    plan = bundle.plans[cover_idx]
    title = next(
        (el for el in plan.elements if el.role == LayoutElementRole.TITLE), None
    )
    assert title is not None
    assert title.font_size_override is not None and title.font_size_override >= 48

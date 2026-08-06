"""Unit tests for VQ-001 Semantic Typography Composition."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.application.visual.typography_composition import (
    compose_metric_typography,
    compose_title_typography,
    composition_to_text_runs,
    infer_typography_page_kind,
    select_title_arrangement,
)
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import (
    ContinuityRole,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import TextNode
from archium.domain.visual.visual_intent import VisualIntent
from archium.domain.visual.visual_language.typography_composition import (
    TypographyArrangement,
    TypographyPageKind,
    TypographyRunRole,
)


def _slide(*, title: str, slide_type: SlideType = SlideType.CONTENT) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="demo",
        order=0,
        title=title,
        message="takeaway",
        slide_type=slide_type,
        key_points=["要点"],
    )


def _plan(
    *,
    family: LayoutFamily = LayoutFamily.HERO,
    variant: str = "full_bleed",
    title: str = "标题",
) -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        layout_family=family,
        layout_variant=variant,
        page_width=10,
        page_height=5.625,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content=title,
                x=0.5,
                y=0.4,
                width=9,
                height=1.0,
                style_token="display",
            )
        ],
        reading_order=["title"],
    )


def test_infer_cover_section_thesis_metric_closing() -> None:
    assert infer_typography_page_kind(slide=_slide(title="封面", slide_type=SlideType.TITLE)) == (
        TypographyPageKind.COVER
    )
    assert infer_typography_page_kind(
        slide=_slide(title="现状问题", slide_type=SlideType.SECTION)
    ) == TypographyPageKind.SECTION
    assert infer_typography_page_kind(slide=_slide(title="核心理念")) == TypographyPageKind.THESIS
    assert (
        infer_typography_page_kind(
            slide=_slide(title="指标"),
            layout_plan=_plan(family=LayoutFamily.METRIC_DASHBOARD, variant="metric_cards"),
        )
        == TypographyPageKind.METRIC
    )
    assert infer_typography_page_kind(
        slide=_slide(title="结语", slide_type=SlideType.CLOSING)
    ) == TypographyPageKind.CLOSING


def test_select_title_arrangement_six_recipes() -> None:
    assert (
        select_title_arrangement("航运", page_kind=TypographyPageKind.COVER)
        == TypographyArrangement.OUTLINE_STATEMENT
    )
    assert (
        select_title_arrangement("南沙航运城", page_kind=TypographyPageKind.COVER)
        == TypographyArrangement.GIANT_BACKGROUND
    )
    assert (
        select_title_arrangement(
            "南沙国际航运科技融合示范区总体城市设计",
            page_kind=TypographyPageKind.COVER,
        )
        == TypographyArrangement.SPLIT_KEYWORD
    )
    assert (
        select_title_arrangement("现状问题", page_kind=TypographyPageKind.SECTION)
        == TypographyArrangement.INDEX_TITLE
    )
    assert (
        select_title_arrangement("更新不是修补", page_kind=TypographyPageKind.THESIS)
        == TypographyArrangement.SPLIT_KEYWORD
    )
    assert (
        select_title_arrangement("致谢", page_kind=TypographyPageKind.CLOSING)
        == TypographyArrangement.VERTICAL_EDGE
    )


def test_title_composition_splits_connector_and_sets_ghost() -> None:
    composition = compose_title_typography(
        "更新不是修补",
        page_kind=TypographyPageKind.THESIS,
        base_size_pt=20,
    )
    assert composition.arrangement == TypographyArrangement.SPLIT_KEYWORD
    assert len(composition.runs) >= 3
    roles = {run.semantic_role for run in composition.runs}
    assert TypographyRunRole.HERO_WORD in roles
    assert TypographyRunRole.CONNECTOR in roles
    assert composition.ghost_text
    assert composition.base_size_pt is not None
    assert composition.base_size_pt > 20
    assert composition.title_band_height_ratio is not None


def test_index_title_composition_emits_index_run() -> None:
    composition = compose_title_typography(
        "现状问题",
        page_kind=TypographyPageKind.SECTION,
        base_size_pt=22,
        section_index=3,
    )
    assert composition.arrangement == TypographyArrangement.INDEX_TITLE
    assert composition.runs[0].semantic_role == TypographyRunRole.INDEX
    assert composition.runs[0].text == "03"


def test_outline_statement_marks_hollow_hero() -> None:
    composition = compose_title_typography(
        "航运",
        page_kind=TypographyPageKind.COVER,
        base_size_pt=24,
    )
    assert composition.arrangement == TypographyArrangement.OUTLINE_STATEMENT
    hero = composition.runs[0]
    assert hero.outline is True
    assert hero.fill_enabled is False
    design = default_presentation_design_system()
    runs = composition_to_text_runs(
        composition,
        design_system=design,
        fallback_color="#132533",
        fallback_weight=400,
    )
    assert runs[0].outline is True
    assert runs[0].fill_enabled is False
    assert runs[0].letter_spacing is not None


def test_metric_composition_enlarges_value() -> None:
    composition = compose_metric_typography("2.5 容积率上限", base_size_pt=18)
    assert composition.arrangement == TypographyArrangement.METRIC_MONUMENT
    assert composition.runs
    value = composition.runs[0]
    assert value.semantic_role == TypographyRunRole.METRIC_VALUE
    assert "2.5" in value.text
    assert value.size_scale >= 2.0
    design = default_presentation_design_system()
    runs = composition_to_text_runs(
        composition,
        design_system=design,
        fallback_color="#132533",
        fallback_weight=400,
    )
    assert runs[0].font_size is not None
    assert runs[0].font_size >= 40


def test_compiler_emits_multi_scale_title_and_ghost() -> None:
    design = default_presentation_design_system()
    slide = _slide(title="更新不是修补", slide_type=SlideType.TITLE)
    plan = _plan(title="更新不是修补")
    plan = plan.model_copy(update={"slide_id": slide.id})
    intent = VisualIntent(
        slide_id=slide.id,
        communication_goal="cover statement",
        audience_takeaway="更新主张",
        visual_priority="title",
        dominant_content_type=VisualContentType.HERO_IMAGE,
        continuity_role=ContinuityRole.OPENING,
    )
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
        visual_intent=intent,
    )
    title = next(n for n in scene.nodes if isinstance(n, TextNode) and n.id == "title")
    assert title.runs
    sizes = {float(run.font_size or 0) for run in title.runs}
    assert len(sizes) >= 2
    ghost = next(
        (
            n
            for n in scene.nodes
            if isinstance(n, TextNode) and n.semantic_role == "typography_ghost"
        ),
        None,
    )
    assert ghost is not None
    assert ghost.opacity < 0.2
    assert any(w.startswith("typography_composition:cover") for w in scene.warnings)

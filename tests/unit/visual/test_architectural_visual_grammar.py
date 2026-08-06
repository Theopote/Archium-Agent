"""VQ-005 Architectural Visual Grammar Library tests."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.architectural_grammar import (
    apply_grammar_to_scene,
    select_architectural_grammar,
)
from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.application.visual.visual_language_service import VisualLanguageService
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_visual_grammar import (
    ArchitecturalGrammarId,
    list_architectural_grammars,
)
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import (
    ContinuityRole,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.page_direction import NarrativeEmotion, PageDirection
from archium.domain.visual.page_visual_grammar import PageGrammarId
from archium.domain.visual.render_scene import TextNode
from archium.domain.visual.visual_intent import VisualIntent


def _slide(title: str, *, slide_type: SlideType = SlideType.CONTENT) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="demo",
        order=0,
        title=title,
        message="主张",
        slide_type=slide_type,
        key_points=["要点"],
    )


def test_catalog_has_twelve_grammars_and_p0_showcase() -> None:
    all_g = list_architectural_grammars()
    p0 = list_architectural_grammars(p0_only=True)
    assert len(all_g) == 12
    assert len(p0) >= 8
    ids = {g.grammar_id for g in p0}
    assert ArchitecturalGrammarId.MONUMENTAL_STATEMENT in ids
    assert ArchitecturalGrammarId.ARCHITECTURAL_EDITORIAL in ids
    assert ArchitecturalGrammarId.ANALYTICAL_OVERLAY in ids
    assert ArchitecturalGrammarId.DRAWING_ATLAS in ids
    assert ArchitecturalGrammarId.SPATIAL_SEQUENCE in ids
    assert ArchitecturalGrammarId.BEFORE_INTERVENTION_AFTER in ids
    assert ArchitecturalGrammarId.METRIC_MONUMENT in ids
    assert ArchitecturalGrammarId.FINAL_VISION in ids
    # v1.1: every grammar declares a preferred color arrangement.
    assert all(g.color_arrangement is not None for g in all_g)


def test_select_cover_and_closing_grammars() -> None:
    cover = select_architectural_grammar(slide=_slide("封面", slide_type=SlideType.TITLE))
    assert cover.grammar_id == ArchitecturalGrammarId.MONUMENTAL_STATEMENT
    closing = select_architectural_grammar(slide=_slide("结语", slide_type=SlideType.CLOSING))
    assert closing.grammar_id == ArchitecturalGrammarId.FINAL_VISION
    metric = select_architectural_grammar(slide=_slide("关键指标", slide_type=SlideType.DATA))
    assert metric.grammar_id == ArchitecturalGrammarId.METRIC_MONUMENT


def test_title_keywords_select_distinct_grammars() -> None:
    spatial = select_architectural_grammar(slide=_slide("空间体验动线"))
    assert spatial.grammar_id == ArchitecturalGrammarId.SPATIAL_SEQUENCE
    before = select_architectural_grammar(slide=_slide("原状与介入"))
    assert before.grammar_id == ArchitecturalGrammarId.BEFORE_INTERVENTION_AFTER
    timeline = select_architectural_grammar(slide=_slide("分期时序"))
    assert timeline.grammar_id == ArchitecturalGrammarId.TIMELINE_RIBBON
    drawing = select_architectural_grammar(slide=_slide("总图与剖面"))
    assert drawing.grammar_id == ArchitecturalGrammarId.DRAWING_ATLAS


def test_formula_maps_to_product_grammar() -> None:
    g = select_architectural_grammar(formula_id=PageGrammarId.LAYER_ANALYSIS)
    assert g.grammar_id == ArchitecturalGrammarId.ANALYTICAL_OVERLAY
    g2 = select_architectural_grammar(formula_id=PageGrammarId.DRAWING_DOMINANT)
    assert g2.grammar_id == ArchitecturalGrammarId.DRAWING_ATLAS


def test_language_compose_stamps_vq5_source() -> None:
    slide = _slide("封面", slide_type=SlideType.TITLE)
    direction = PageDirection(
        single_message="主张",
        narrative_emotion=NarrativeEmotion.CLIMAX,
        must_show=["hero"],
        must_hide=[],
    )
    language = VisualLanguageService().compose(slide, direction)
    assert language.source.startswith("vq5:")
    assert language.graphic_motif is not None
    stamped = VisualLanguageService().apply(direction, language, slide=slide)
    assert any(e.startswith("arch_grammar:") for e in stamped.evidence)
    assert stamped.background_mode is not None


def test_compiler_applies_monumental_title_boost() -> None:
    design = default_presentation_design_system()
    slide = _slide("更新不是修补", slide_type=SlideType.TITLE)
    plan = LayoutPlan(
        slide_id=slide.id,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="full_bleed",
        page_width=10,
        page_height=5.625,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="更新不是修补",
                x=0.55,
                y=0.4,
                width=8.9,
                height=1.2,
                style_token="display",
            )
        ],
        reading_order=["title"],
    )
    intent = VisualIntent(
        slide_id=slide.id,
        communication_goal="cover",
        audience_takeaway="claim",
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
    assert any(w.startswith("arch_grammar:monumental_statement") for w in scene.warnings)
    assert any(w.startswith("vq5_p0:") for w in scene.warnings)
    assert any(w.startswith("composition:") for w in scene.warnings)
    assert any(w.startswith("grammar_color:") for w in scene.warnings)
    title = next(n for n in scene.nodes if isinstance(n, TextNode) and n.id == "title")
    assert title.font_size >= 28
    assert title.runs  # typography composition still present
    # Monumental → accent_edge color geometry when accent ratio allows.
    assert any(
        getattr(n, "id", "") == "color_accent_edge" or "accent_edge" in str(getattr(n, "id", ""))
        for n in scene.nodes
    ) or any("color_arrangement:accent_edge" in str(w) for w in scene.warnings)


def test_apply_grammar_to_scene_is_idempotent() -> None:
    design = default_presentation_design_system()
    slide = _slide("封面", slide_type=SlideType.TITLE)
    plan = LayoutPlan(
        slide_id=slide.id,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="full_bleed",
        page_width=10,
        page_height=5.625,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="封面",
                x=0.5,
                y=0.4,
                width=9,
                height=1.0,
            )
        ],
        reading_order=["title"],
    )
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
    )
    grammar = select_architectural_grammar(slide=slide)
    again = apply_grammar_to_scene(scene, grammar)
    assert again.warnings.count(f"arch_grammar:{grammar.grammar_id.value}") == 1


def test_metric_grammar_forces_metric_panel_arrangement() -> None:
    from archium.domain.visual.architectural_visual_grammar import get_architectural_grammar
    from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, ThemeTokens

    grammar = get_architectural_grammar(ArchitecturalGrammarId.METRIC_MONUMENT)
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10.0,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        theme_tokens=ThemeTokens(colors={"background": "#FFFFFF", "accent": "#C45C26"}),
        nodes=[
            TextNode(
                id="title",
                x=0.5,
                y=0.4,
                width=9.0,
                height=0.8,
                text="关键指标",
                font_family="Arial",
                font_size=22.0,
                font_weight=400,
                color="#111111",
                line_height=1.2,
                semantic_role="title",
            )
        ],
        warnings=[],
    )
    out = apply_grammar_to_scene(scene, grammar)
    assert "grammar_color:metric_panel" in out.warnings
    assert any(getattr(n, "id", "") == "color_metric_panel" for n in out.nodes)

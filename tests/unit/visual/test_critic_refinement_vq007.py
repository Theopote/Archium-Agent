"""VQ-007: bounded Visual Critic refinement loop."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.critic_refinement_service import CriticRefinementService
from archium.application.visual.visual_critic_service import VisualCriticService
from archium.domain.visual.critic import (
    CRITIC_HERO_WEAK,
    CRITIC_PAGE_REPETITION,
    CRITIC_TITLE_WEAK,
    CRITIC_VISUAL_NOISE_HIGH,
    VisualCriticFinding,
    VisualCriticReport,
)
from archium.domain.visual.critic_refinement import (
    MAX_ACTIONS_PER_PAGE,
    MAX_REFINEMENT_ROUNDS,
    VisualRefinementAction,
    VisualRefinementActionType,
)
from archium.domain.visual.enums import (
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    LayoutIssueSeverity,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    ImageNode,
    RenderScene,
    ShapeNode,
    TextNode,
    TextParagraph,
    ThemeTokens,
)


def _title_node(text: str = "弱标题", size: float = 18.0) -> TextNode:
    return TextNode(
        id="title",
        semantic_role="title",
        x=0.5,
        y=0.3,
        width=4.0,
        height=0.4,
        z_index=2,
        text=text,
        paragraphs=[TextParagraph(text=text)],
        font_family="Arial",
        font_family_cjk="Microsoft YaHei",
        font_family_latin="Arial",
        font_size=size,
        font_weight=400,
        color="#222222",
        line_height=size * 1.2,
    )


def _body_node() -> TextNode:
    text = "长文占位 " * 20
    return TextNode(
        id="body",
        semantic_role="body_text",
        x=0.5,
        y=1.2,
        width=9.0,
        height=3.5,
        z_index=2,
        text=text,
        paragraphs=[TextParagraph(text=text)],
        font_family="Arial",
        font_family_cjk="Microsoft YaHei",
        font_family_latin="Arial",
        font_size=14,
        font_weight=400,
        color="#333333",
        opacity=1.0,
        line_height=18,
    )


def _hero_node(*, width: float = 2.5, height: float = 1.5) -> ImageNode:
    return ImageNode(
        id="hero",
        semantic_role="hero_visual",
        x=1.0,
        y=2.0,
        width=width,
        height=height,
        z_index=1,
        storage_uri="asset://hero.jpg",
    )


def _scene(*nodes: object) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10.0,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),
        theme_tokens=ThemeTokens(),
    )


def _plan_for(scene: RenderScene, *elements: LayoutElement) -> LayoutPlan:
    return LayoutPlan(
        id=scene.layout_plan_id,
        slide_id=scene.slide_id,
        layout_family=LayoutFamily.HERO,
        layout_variant="split",
        page_width=10,
        page_height=5.625,
        reading_order=[el.id for el in elements],
        whitespace_ratio=0.2,
        elements=list(elements),
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        hero_element_id="hero" if any(el.id == "hero" for el in elements) else None,
    )


def test_propose_maps_only_allowlisted_codes() -> None:
    scene = _scene(_title_node(), _hero_node())
    report = VisualCriticReport(
        method="screenshot_v1",
        slide_id=str(scene.slide_id),
        layout_plan_id=str(scene.layout_plan_id),
        findings=[
            VisualCriticFinding(
                rule_code=CRITIC_TITLE_WEAK,
                severity=LayoutIssueSeverity.WARNING,
                message="title weak",
                suggestion="boost title",
            ),
            VisualCriticFinding(
                rule_code=CRITIC_PAGE_REPETITION,
                severity=LayoutIssueSeverity.WARNING,
                message="repeats",
            ),
            VisualCriticFinding(
                rule_code=CRITIC_HERO_WEAK,
                severity=LayoutIssueSeverity.WARNING,
                message="hero weak",
            ),
        ],
        total_score=0.4,
    )
    proposal = CriticRefinementService().propose(report, scene, max_actions=3)
    types = {a.action_type for a in proposal.actions}
    assert VisualRefinementActionType.BOOST_TITLE_SCALE in types
    assert VisualRefinementActionType.ENLARGE_HERO in types
    assert CRITIC_PAGE_REPETITION in proposal.deferred_codes
    assert len(proposal.actions) <= MAX_ACTIONS_PER_PAGE


def test_apply_boosts_title_and_enlarges_hero() -> None:
    scene = _scene(_title_node(size=18), _hero_node(width=2.0, height=1.2))
    actions = [
        VisualRefinementAction(
            action_type=VisualRefinementActionType.BOOST_TITLE_SCALE,
            rule_code=CRITIC_TITLE_WEAK,
            target_node_id="title",
            magnitude=0.15,
        ),
        VisualRefinementAction(
            action_type=VisualRefinementActionType.ENLARGE_HERO,
            rule_code=CRITIC_HERO_WEAK,
            target_node_id="hero",
            magnitude=0.12,
        ),
    ]
    patched, applied = CriticRefinementService().apply(scene, actions)
    assert len(applied) == 2
    title = next(n for n in patched.nodes if n.id == "title")
    hero = next(n for n in patched.nodes if n.id == "hero")
    assert isinstance(title, TextNode)
    assert title.font_size > 18
    assert isinstance(hero, ImageNode)
    assert hero.width > 2.0
    assert "vq7_refinement:applied=2" in patched.warnings


def test_quiet_motif_drops_connector_noise() -> None:
    scene = _scene(
        _title_node(),
        ShapeNode(
            id="vl_motif_node_0",
            semantic_role="graphic_motif",
            x=1,
            y=1,
            width=0.2,
            height=0.2,
            opacity=0.9,
            shape_kind="ellipse",
            fill_color="#C45C26",
            stroke_color="#C45C26",
            stroke_width=1,
        ),
        ShapeNode(
            id="vl_motif_connector_0",
            semantic_role="graphic_motif_connector",
            x=1,
            y=1,
            width=2,
            height=0.1,
            opacity=0.8,
            shape_kind="rectangle",
            fill_color="#C45C26",
            stroke_color="#C45C26",
            stroke_width=0,
        ),
    )
    report = VisualCriticReport(
        findings=[
            VisualCriticFinding(
                rule_code=CRITIC_VISUAL_NOISE_HIGH,
                severity=LayoutIssueSeverity.INFO,
                message="noisy",
            )
        ],
        total_score=0.5,
    )
    service = CriticRefinementService()
    proposal = service.propose(report, scene)
    patched, applied = service.apply(scene, proposal.actions)
    assert applied
    ids = {n.id for n in patched.nodes}
    assert "vl_motif_connector_0" not in ids
    assert "vl_motif_node_0" in ids


def test_refine_page_respects_round_and_action_caps() -> None:
    scene = _scene(_title_node(size=16), _body_node(), _hero_node(width=2.0, height=1.0))
    plan = _plan_for(
        scene,
        LayoutElement(
            id="title",
            role=LayoutElementRole.TITLE,
            content_type=LayoutContentType.TEXT,
            text_content="弱标题",
            x=0.5,
            y=0.3,
            width=2.0,
            height=0.25,
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
        LayoutElement(
            id="hero",
            role=LayoutElementRole.HERO_VISUAL,
            content_type=LayoutContentType.IMAGE,
            x=1.0,
            y=2.0,
            width=2.0,
            height=1.0,
        ),
    )
    result = CriticRefinementService(VisualCriticService()).refine_page(
        scene,
        plan,
        max_rounds=MAX_REFINEMENT_ROUNDS,
        max_actions=2,
    )
    assert result.applied_count <= 2 * MAX_REFINEMENT_ROUNDS
    assert len(result.rounds) <= MAX_REFINEMENT_ROUNDS
    assert result.before_report is not None
    assert result.after_report is not None
    # Title or hero should have moved if findings triggered.
    if result.applied_count:
        assert any("vq7_action:" in w for w in result.scene.warnings)


def test_unknown_action_type_cannot_be_smuggled() -> None:
    scene = _scene(_title_node())
    # Construct via model with a valid enum only — closed set.
    assert set(VisualRefinementActionType) == {
        VisualRefinementActionType.BOOST_TITLE_SCALE,
        VisualRefinementActionType.ENLARGE_HERO,
        VisualRefinementActionType.SOFTEN_SECONDARY_TEXT,
        VisualRefinementActionType.QUIET_MOTIF,
        VisualRefinementActionType.TRIM_BODY_BOX,
        VisualRefinementActionType.SOFTEN_ACCENT_SHAPES,
        VisualRefinementActionType.FIX_TEXT_CONTRAST,
    }
    patched, applied = CriticRefinementService().apply(scene, [])
    assert applied == []
    assert patched.nodes[0].font_size == scene.nodes[0].font_size

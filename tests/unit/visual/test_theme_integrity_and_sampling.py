"""Theme integrity QA and explainable sample selection tests."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.deck_theme_apply import apply_tokens_to_design_system
from archium.application.visual.theme_integrity_qa import (
    THEME_CHART_SEMANTIC_COLOR,
    THEME_CITATION_CONTRAST,
    THEME_DRAWING_COLOR_INTEGRITY,
    THEME_EVIDENCE_PHOTO_TREATMENT,
    run_theme_integrity_qa,
)
from archium.application.visual.theme_proposal_service import ThemeProposalService
from archium.application.visual.theme_scene_resolve import resolve_scene_with_design_system
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.deck_theme_tokens import DeckThemeTokens
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import ImageFit, LayoutFamily, PhotoTreatment
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    RenderScene,
    TextNode,
)
from archium.domain.visual.style_binding import ExplicitStyleValue, ThemeTokenReference


def test_style_binding_kinds() -> None:
    ref = ThemeTokenReference(token_key="primary_text")
    explicit = ExplicitStyleValue(value="#FF0000")
    assert ref.kind == "token"
    assert explicit.kind == "explicit"


def test_resolve_scene_updates_token_bound_colors_only() -> None:
    design = default_presentation_design_system()
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="title",
                x=1,
                y=1,
                width=4,
                height=0.6,
                z_index=1,
                text="标题",
                font_family="Arial",
                font_size=24,
                color="#111111",
                color_token="primary_text",
                typography_token="title",
                line_height=1.2,
            ),
            TextNode(
                id="pinned",
                x=1,
                y=2,
                width=4,
                height=0.4,
                z_index=1,
                text="局部覆盖",
                font_family="Arial",
                font_size=12,
                color="#ABCDEF",
                color_token="",  # explicit local pin
                line_height=1.2,
            ),
        ],
    )
    themed = apply_tokens_to_design_system(
        design, DeckThemeTokens(primary="#112233", background="#FEFEFE")
    )
    themed.colors.primary_text = "#445566"
    resolved = resolve_scene_with_design_system(scene, themed)
    title = resolved.node_by_id("title")
    pinned = resolved.node_by_id("pinned")
    assert title is not None and title.color == "#445566"
    assert pinned is not None and pinned.color == "#ABCDEF"
    assert resolved.design_system_id == themed.id
    assert resolved.background.color == themed.colors.background


def test_resolve_scene_updates_icon_stroke_token() -> None:
    from archium.domain.visual.render_scene import ImageNode

    design = default_presentation_design_system().model_copy(deep=True)
    design.colors.accent = "#E63946"
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="icon",
                semantic_role="icon",
                x=1.0,
                y=1.0,
                width=0.2,
                height=0.2,
                storage_uri="assets/icons/traffic/pedestrian_flow.svg",
                asset_path="assets/icons/traffic/pedestrian_flow.svg",
                fit_mode="contain",
                icon_stroke_color="#111111",
                icon_stroke_token="accent",
            )
        ],
    )
    themed = apply_tokens_to_design_system(
        design, DeckThemeTokens(accent="#6BA3D0")
    )
    resolved = resolve_scene_with_design_system(scene, themed)
    icon = resolved.node_by_id("icon")
    assert isinstance(icon, ImageNode)
    assert icon.icon_stroke_color == "#6BA3D0"
    assert icon.icon_stroke_token == "accent"


def test_drawing_integrity_blocks_non_contain() -> None:
    base = default_presentation_design_system()
    proposed = base.model_copy(deep=True)
    proposed.image_style.default_fit = ImageFit.COVER
    issues = run_theme_integrity_qa(base=base, proposed=proposed)
    assert any(issue.code == THEME_DRAWING_COLOR_INTEGRITY for issue in issues)


def test_evidence_photo_historical_is_flagged() -> None:
    base = default_presentation_design_system()
    proposed = apply_tokens_to_design_system(
        base, DeckThemeTokens(photo_treatment=PhotoTreatment.HISTORICAL)
    )
    issues = run_theme_integrity_qa(base=base, proposed=proposed)
    assert any(issue.code == THEME_EVIDENCE_PHOTO_TREATMENT for issue in issues)


def test_chart_palette_collapse_is_flagged() -> None:
    base = default_presentation_design_system()
    proposed = base.model_copy(deep=True)
    proposed.chart_style.palette_tokens = ["primary", "primary", "primary"]
    issues = run_theme_integrity_qa(base=base, proposed=proposed)
    assert any(issue.code == THEME_CHART_SEMANTIC_COLOR for issue in issues)


def test_citation_contrast_flags_low_contrast() -> None:
    base = default_presentation_design_system()
    proposed = base.model_copy(deep=True)
    proposed.colors.background = "#FFFFFF"
    proposed.colors.muted_text = "#F5F5F5"
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="src",
                semantic_role="citation",
                x=1,
                y=5,
                width=3,
                height=0.3,
                z_index=1,
                text="来源",
                font_family="Arial",
                font_size=9,
                color="#F5F5F5",
                color_token="muted_text",
                line_height=1.1,
            )
        ],
    )
    issues = run_theme_integrity_qa(base=base, proposed=proposed, sample_scenes=[scene])
    assert any(issue.code == THEME_CITATION_CONTRAST for issue in issues)


def test_sample_selection_prefers_role_coverage() -> None:
    service = ThemeProposalService.__new__(ThemeProposalService)
    ds_id = uuid4()
    intent_id = uuid4()

    def _plan(
        *,
        plan_id,
        slide_id,
        family: LayoutFamily,
    ) -> LayoutPlan:
        return LayoutPlan(
            id=plan_id,
            slide_id=slide_id,
            design_system_id=ds_id,
            visual_intent_id=intent_id,
            layout_family=family,
            layout_variant="default",
            page_width=10,
            page_height=5.625,
        )

    slides = [
        SlideSpec(
            presentation_id=uuid4(),
            title="封面",
            slide_type=SlideType.TITLE,
            order=0,
            chapter_id="c",
            message="开篇",
            layout_plan_id=uuid4(),
        ),
        SlideSpec(
            presentation_id=uuid4(),
            title="总平面",
            slide_type=SlideType.CONTENT,
            order=1,
            chapter_id="c",
            message="图纸",
            layout_plan_id=uuid4(),
        ),
        SlideSpec(
            presentation_id=uuid4(),
            title="数据",
            slide_type=SlideType.DATA,
            order=2,
            chapter_id="c",
            message="指标",
            layout_plan_id=uuid4(),
        ),
    ]
    plans = {
        slides[0].layout_plan_id: _plan(
            plan_id=slides[0].layout_plan_id,
            slide_id=slides[0].id,
            family=LayoutFamily.HERO,
        ),
        slides[1].layout_plan_id: _plan(
            plan_id=slides[1].layout_plan_id,
            slide_id=slides[1].id,
            family=LayoutFamily.DRAWING_FOCUS,
        ),
        slides[2].layout_plan_id: _plan(
            plan_id=slides[2].layout_plan_id,
            slide_id=slides[2].id,
            family=LayoutFamily.METRIC_DASHBOARD,
        ),
    }
    service._plans = type("P", (), {"get": staticmethod(lambda pid: plans.get(pid))})()

    picks = ThemeProposalService._select_sample_slides(
        service, slides, preferred_slide_id=None
    )
    reasons = [pick.reason for pick in picks]
    assert any(reason.startswith("cover:") for reason in reasons)
    assert any(reason.startswith("drawing_focus:") for reason in reasons)
    assert any(reason.startswith("data:") for reason in reasons)

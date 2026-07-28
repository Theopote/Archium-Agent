"""Tests for variant layout proportion tokens."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual import LayoutFamily, VisualContentType, VisualIntent, default_presentation_design_system
from archium.infrastructure.layout.generators.base import LayoutGeneratorContext, content_from_slide
from archium.infrastructure.layout.geometry import Rect, safe_area
from archium.infrastructure.layout.layout_solver import LayoutSolver
from archium.infrastructure.layout.variant_layout_tokens import (
    VariantLayoutTokens,
    compute_hero_split_text_ratio,
    resolve_layout_tokens,
)


def _hero_context(*, variant: str = "split") -> LayoutGeneratorContext:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="方案封面：内院视角效果图",
        message="以一张效果图建立项目气质与汇报开场记忆点。",
        key_points=["要点一"],
        visual_requirements=[VisualRequirement(type=VisualType.RENDERING, description="hero")],
    )
    intent = VisualIntent(
        slide_id=slide.id,
        communication_goal="封面",
        audience_takeaway=slide.message,
        visual_priority="hero > title",
        dominant_content_type=VisualContentType.HERO_IMAGE,
        preferred_layout_families=[LayoutFamily.HERO],
        hero_asset_id=uuid4(),
    )
    design = default_presentation_design_system()
    return LayoutGeneratorContext(
        slide=slide,
        visual_intent=intent,
        art_direction=None,
        design_system=design,
        content=content_from_slide(slide, intent, source_text="项目任务书.pdf"),
        variant=variant,
    )


class TestVariantLayoutTokens:
    def test_hero_split_tokens(self) -> None:
        tokens = resolve_layout_tokens(LayoutFamily.HERO, "split")
        assert tokens.text_panel_max_width_ratio == 0.28
        assert tokens.hero_min_body_area_ratio == 0.58

    def test_drawing_focus_tokens(self) -> None:
        tokens = resolve_layout_tokens(LayoutFamily.DRAWING_FOCUS, "drawing_with_metrics")
        assert tokens.primary_visual_width_ratio == 0.72

    def test_compute_hero_split_text_ratio_respects_cap(self) -> None:
        tokens = resolve_layout_tokens(LayoutFamily.HERO, "split")
        body = Rect(0.7, 1.2, 8.6, 3.5)
        ratio = compute_hero_split_text_ratio(body, tokens, gap=0.24)
        assert ratio == 0.28

    def test_hero_split_meets_body_area_floor(self) -> None:
        ctx = _hero_context(variant="split")
        plan = LayoutSolver().generate(LayoutFamily.HERO, ctx)
        hero = plan.element_by_id("hero")
        assert hero is not None
        title = plan.element_by_id("title")
        assert title is not None
        spacing = ctx.design_system.spacing
        body_top = title.y + title.height + spacing.md
        body = Rect(title.x, body_top, title.width, hero.y + hero.height - body_top)
        hero_share = hero.area / max(body.area, 1e-6)
        tokens = resolve_layout_tokens(LayoutFamily.HERO, "split")
        assert hero_share + 1e-6 >= tokens.hero_min_body_area_ratio

    def test_hero_split_wider_than_legacy_042(self) -> None:
        ctx = _hero_context(variant="split")
        plan = LayoutSolver().generate(LayoutFamily.HERO, ctx)
        hero = plan.element_by_id("hero")
        assert hero is not None
        assert hero.width > 4.891

    def test_hero_split_improves_safe_area_dominance(self) -> None:
        ctx = _hero_context(variant="split")
        plan = LayoutSolver().generate(LayoutFamily.HERO, ctx)
        hero = plan.element_by_id("hero")
        assert hero is not None
        safe = safe_area(ctx.design_system)
        ratio = hero.area / safe.area
        assert ratio > 0.48

    def test_drawing_focus_footer_from_safe_ratios(self) -> None:
        tokens = resolve_layout_tokens(LayoutFamily.DRAWING_FOCUS, "drawing_with_metrics")
        design = default_presentation_design_system()
        safe = safe_area(design)
        caption_h = safe.height * tokens.caption_max_height_ratio
        source_h = safe.height * tokens.source_max_height_ratio
        assert abs(caption_h - 0.28) < 0.03
        assert abs(source_h - 0.22) < 0.03

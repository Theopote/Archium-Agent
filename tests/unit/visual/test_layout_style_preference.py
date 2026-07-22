"""Unit tests for ReferenceStyle layout_cues → LayoutPlan preferences."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.layout_planning_service import LayoutPlanningService
from archium.application.visual.layout_style_preference import (
    LayoutStylePreference,
    derive_layout_style_preference,
    merge_preferred_families,
)
from archium.domain.reference_style import ReferenceStyleProfile, StyleLayoutCue
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.enums import LayoutFamily, VisualContentType
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.validation import LayoutValidationReport
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.llm.visual_schemas import LayoutDecisionDraft


def _art(**kwargs: object) -> ArtDirection:
    defaults = {
        "project_id": uuid4(),
        "concept_name": "test",
        "rationale": "test rationale",
        "palette_strategy": "neutral",
        "typography_strategy": "balanced",
        "grid_strategy": "standard",
        "image_strategy": "contain",
        "drawing_strategy": "clean",
        "diagram_strategy": "simple",
        "annotation_strategy": "minimal",
        "cover_strategy": "hero",
        "section_strategy": "divider",
        "content_strategy": "balanced",
        "closing_strategy": "summary",
        "pacing_strategy": "steady",
    }
    defaults.update(kwargs)
    return ArtDirection(**defaults)  # type: ignore[arg-type]


def test_derive_prefers_full_bleed_hero_from_layout_cue() -> None:
    profile = ReferenceStyleProfile(
        project_id=uuid4(),
        style_name="bleed",
        layout_cues=[
            StyleLayoutCue(
                id="c1",
                pattern="asymmetric-bleed",
                description="Full-bleed hero photography on cover pages",
            )
        ],
    )
    pref = derive_layout_style_preference(reference_style=profile)
    assert LayoutFamily.HERO in pref.preferred_families
    assert pref.preferred_families[0] == LayoutFamily.HERO
    assert (LayoutFamily.HERO, "full_bleed") in pref.preferred_variants
    assert pref.selection_bonus(LayoutFamily.HERO, "full_bleed") > pref.selection_bonus(
        LayoutFamily.TEXTUAL_ARGUMENT, "lead_and_points"
    )


def test_derive_photo_grid_and_drawing_cues() -> None:
    profile = ReferenceStyleProfile(
        project_id=uuid4(),
        style_name="mixed",
        layout_cues=[
            StyleLayoutCue(
                id="g",
                pattern="photo_grid",
                description="Numbered evidence photo grid",
            ),
            StyleLayoutCue(
                id="d",
                pattern="drawing-canvas",
                description="总平面图纸主导页面",
            ),
        ],
    )
    pref = derive_layout_style_preference(reference_style=profile)
    assert pref.preferred_families[0] == LayoutFamily.EVIDENCE_BOARD
    assert LayoutFamily.DRAWING_FOCUS in pref.preferred_families


def test_art_direction_image_strategy_full_bleed() -> None:
    art = _art(image_strategy="full bleed hero cover", cover_strategy="hero full-bleed")
    pref = derive_layout_style_preference(art_direction=art)
    assert LayoutFamily.HERO in pref.preferred_families
    assert any(family == LayoutFamily.HERO and variant == "full_bleed" for family, variant in pref.preferred_variants)


def test_merge_preferred_families_order() -> None:
    merged = merge_preferred_families(
        [LayoutFamily.HERO],
        [LayoutFamily.EVIDENCE_BOARD, LayoutFamily.HERO],
        [LayoutFamily.TEXTUAL_ARGUMENT],
    )
    assert merged == [
        LayoutFamily.HERO,
        LayoutFamily.EVIDENCE_BOARD,
        LayoutFamily.TEXTUAL_ARGUMENT,
    ]


def test_select_best_prefers_style_family_over_higher_score() -> None:
    service = LayoutPlanningService.__new__(LayoutPlanningService)
    service._last_style_preference = LayoutStylePreference()
    style = LayoutStylePreference(
        preferred_families=(LayoutFamily.HERO,),
        preferred_variants=((LayoutFamily.HERO, "full_bleed"),),
    )

    def plan(family: LayoutFamily, variant: str) -> LayoutPlan:
        return LayoutPlan(
            slide_id=uuid4(),
            layout_family=family,
            layout_variant=variant,
            page_width=10,
            page_height=5.625,
            reading_order=[],
            whitespace_ratio=0.3,
            elements=[],
            design_system_id=uuid4(),
            visual_intent_id=uuid4(),
        )

    candidates = [
        (plan(LayoutFamily.TEXTUAL_ARGUMENT, "lead_and_points"), LayoutValidationReport(issues=[], score=0.96)),
        (plan(LayoutFamily.HERO, "full_bleed"), LayoutValidationReport(issues=[], score=0.86)),
    ]
    selected = service.select_best_for_deck(candidates, style_preference=style)
    assert selected.layout_family == LayoutFamily.HERO
    assert selected.layout_variant == "full_bleed"


def test_rule_decisions_surface_style_preferred_variant_first() -> None:
    service = LayoutPlanningService.__new__(LayoutPlanningService)
    service._registry = get_layout_family_registry()
    intent = VisualIntent(
        slide_id=uuid4(),
        communication_goal="show hero",
        audience_takeaway="memorable image",
        visual_priority="hero",
        dominant_content_type=VisualContentType.HERO_IMAGE,
        preferred_layout_families=[],
    )
    style = LayoutStylePreference(
        preferred_families=(LayoutFamily.HERO,),
        preferred_variants=((LayoutFamily.HERO, "full_bleed"),),
    )
    decisions = service._rule_decisions(
        intent,
        asset_count=1,
        candidate_count=3,
        style_preference=style,
    )
    assert decisions
    assert decisions[0].layout_family == LayoutFamily.HERO.value
    assert decisions[0].layout_variant == "full_bleed"


def test_apply_preference_orders_variant_before_sibling() -> None:
    decisions = [
        LayoutDecisionDraft(layout_family="hero", layout_variant="split"),
        LayoutDecisionDraft(layout_family="hero", layout_variant="full_bleed"),
        LayoutDecisionDraft(layout_family="textual_argument", layout_variant="lead_and_points"),
    ]
    style = LayoutStylePreference(
        preferred_families=(LayoutFamily.HERO,),
        preferred_variants=((LayoutFamily.HERO, "full_bleed"),),
    )
    ordered = LayoutPlanningService._apply_preference_to_decisions(
        decisions,
        None,
        style,
        candidate_count=3,
    )
    assert ordered[0].layout_variant == "full_bleed"

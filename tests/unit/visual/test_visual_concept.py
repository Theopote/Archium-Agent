"""Unit tests for page-level VisualConcept (Grammar v1 slice)."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.page_direction_service import PageDirectionService
from archium.application.visual.showcase_case_001 import build_case_001_render_bundle
from archium.application.visual.visual_concept_service import VisualConceptService
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.visual_concept import VisualMetaphor


def test_traffic_conflict_gets_fragment_to_network_concept() -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="site",
        order=5,
        title="流线冲突",
        message="医患流线交叉与洁污混行是当前最大安全风险。",
        key_points=["急诊与物流冲突"],
    )
    direction = PageDirectionService().direct(slide)
    assert direction.situation_rule_id == "site_traffic_conflict"
    assert direction.visual_concept is not None
    assert (
        direction.visual_concept.visual_metaphor
        == VisualMetaphor.FRAGMENT_TO_NETWORK
    )
    assert direction.visual_concept.color_story[:3] == ["gray", "red", "renew_green"]
    assert LayoutFamily.ANALYTICAL_DIAGRAM in direction.preferred_layout_families
    assert LayoutFamily.STRATEGY_CARDS in direction.forbidden_layout_families
    card = direction.as_page_claim()
    assert card["visual_concept"]["visual_metaphor"] == "fragment_to_network"


def test_case_001_circulation_page_uses_concept_family() -> None:
    bundle = build_case_001_render_bundle()
    idx = next(i for i, s in enumerate(bundle.slides) if s.title == "流线冲突")
    intent = bundle.intents[idx]
    plan = bundle.plans[idx]
    assert intent.page_direction is not None
    assert intent.page_direction.visual_concept is not None
    assert (
        intent.page_direction.visual_concept.visual_metaphor
        == VisualMetaphor.FRAGMENT_TO_NETWORK
    )
    assert plan.layout_family in {
        LayoutFamily.ANALYTICAL_DIAGRAM,
        LayoutFamily.EVIDENCE_BOARD,
        LayoutFamily.HYBRID_CANVAS,
    }
    assert plan.layout_family != LayoutFamily.STRATEGY_CARDS


def test_unrelated_slide_has_no_forced_fragment_concept() -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="intro",
        order=1,
        title="项目背景",
        message="院区老化与接诊压力叠加。",
        key_points=["建设年代久"],
    )
    direction = PageDirectionService().direct(slide)
    concept = VisualConceptService().recognize(slide, direction)
    assert concept is None or concept.visual_metaphor != VisualMetaphor.FRAGMENT_TO_NETWORK


def test_overview_mentioning_circulation_does_not_force_fragment() -> None:
    """Overview pages that mention 交叉 must not steal fragment_to_network."""
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="site",
        order=4,
        title="现状问题总览",
        message="现状问题：拥堵、交叉、老化三类并存。",
        key_points=["门诊大厅拥堵", "医患动线混杂", "后勤空间老化"],
    )
    direction = PageDirectionService().direct(slide)
    assert direction.situation_rule_id != "site_traffic_conflict"
    assert (
        direction.visual_concept is None
        or direction.visual_concept.visual_metaphor
        != VisualMetaphor.FRAGMENT_TO_NETWORK
    )

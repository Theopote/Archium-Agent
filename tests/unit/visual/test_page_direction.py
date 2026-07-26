"""Unit tests for PageDirectionService (v0.3 Showcase Phase 1.3)."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.page_direction_service import (
    PageDirectionService,
    apply_page_direction_to_intent,
)
from archium.application.visual.visual_grammar_intent import forbidden_families_for_intent
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import DensityLevel, LayoutFamily, VisualContentType
from archium.domain.visual.page_direction import CompositionBias, NarrativeEmotion
from archium.domain.visual.style import StylePresetId, get_style_preset
from archium.domain.visual.visual_grammar import PageArchetype
from archium.domain.visual.visual_intent import VisualIntent


def _slide(**kwargs: object) -> SlideSpec:
    defaults: dict[str, object] = {
        "presentation_id": uuid4(),
        "chapter_id": "site",
        "order": 4,
        "title": "基地交通",
        "message": "基地交通复杂，人车混行。",
        "key_points": ["入口拥堵", "步行不安全", "车行绕行"],
    }
    defaults.update(kwargs)
    return SlideSpec(**defaults)  # type: ignore[arg-type]


def _intent(slide: SlideSpec, **kwargs: object) -> VisualIntent:
    defaults: dict[str, object] = {
        "slide_id": slide.id,
        "communication_goal": "说明基地问题",
        "audience_takeaway": slide.message,
        "visual_priority": "photo > text",
        "dominant_content_type": VisualContentType.TEXT_ARGUMENT,
        "preferred_layout_families": [LayoutFamily.TEXTUAL_ARGUMENT],
        "density_level": DensityLevel.COMPACT,
        "page_archetype": PageArchetype.SITE_PROBLEM_DIAGNOSIS,
    }
    defaults.update(kwargs)
    return VisualIntent(**defaults)  # type: ignore[arg-type]


def test_traffic_conflict_predictable_copy_budget_and_family() -> None:
    slide = _slide(
        title="基地交通矛盾",
        message="基地交通复杂，人车混行。需要分流而不是加宽道路。",
        key_points=["车行", "人行", "交叉口", "多余第四点", "第五点"],
    )
    direction = PageDirectionService().direct(
        slide,
        page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS,
    )
    assert direction.situation_rule_id == "site_traffic_conflict"
    assert direction.copy_budget.max_key_points == 1
    assert direction.copy_budget.max_body_blocks == 1
    assert direction.copy_budget.max_message_chars <= 72
    assert LayoutFamily.EVIDENCE_BOARD in direction.preferred_layout_families
    assert LayoutFamily.TEXTUAL_ARGUMENT in direction.forbidden_layout_families
    assert CompositionBias.PHOTO_LEFT in direction.composition_bias
    assert CompositionBias.DIAGRAM_CENTER in direction.composition_bias
    assert CompositionBias.CONCLUSION_BAR in direction.composition_bias
    assert "site_photo" in direction.must_show
    assert direction.evidence_priority[0] == "site_photo"
    assert "three_column_text" in direction.avoid
    assert direction.claim == direction.single_message
    assert direction.narrative_emotion == NarrativeEmotion.PROBLEM
    card = direction.as_page_claim()
    assert card["claim"] == direction.claim
    assert card["emotion"] == "problem"
    assert card["evidence_priority"][0] == "site_photo"
    assert "derived_composition_bias" in card
    # Single message is first sentence only.
    assert "分流" not in direction.single_message or "人车混行" in direction.single_message
    assert "。" not in direction.single_message


def test_director_overrides_archetype_on_conflict() -> None:
    """Situation rule forbids TEXTUAL_ARGUMENT even if archetype liked it."""
    slide = _slide(message="基地交通复杂，人车混行。")
    # SITE_PROBLEM typically prefers evidence; force merge path with narrative opening
    # which forbids textual too — use SITE_CONTEXT which may prefer drawing.
    direction = PageDirectionService().direct(
        slide,
        page_archetype=PageArchetype.SITE_CONTEXT_ANALYSIS,
    )
    assert direction.situation_rule_id == "site_traffic_conflict"
    assert any("director_overrides_archetype" in item for item in direction.evidence)
    assert LayoutFamily.TEXTUAL_ARGUMENT in direction.forbidden_layout_families
    assert direction.density_override == DensityLevel.BALANCED


def test_apply_to_intent_writes_page_direction_and_forbidden() -> None:
    slide = _slide()
    intent = _intent(slide)
    direction = PageDirectionService().direct(slide)
    updated = apply_page_direction_to_intent(intent, direction)
    assert updated.page_direction is not None
    assert updated.page_direction.situation_rule_id == "site_traffic_conflict"
    assert updated.audience_takeaway == direction.single_message
    assert LayoutFamily.TEXTUAL_ARGUMENT not in updated.preferred_layout_families
    blocked = forbidden_families_for_intent(updated)
    assert LayoutFamily.TEXTUAL_ARGUMENT in blocked


def test_minimal_style_tightens_copy_budget() -> None:
    slide = _slide(message="基地交通复杂，人车混行。")
    base = PageDirectionService().direct(slide)
    tight = PageDirectionService().direct(
        slide,
        style_preset=get_style_preset(StylePresetId.ARCHITECTURE_MINIMAL),
    )
    assert tight.copy_budget.max_key_points <= base.copy_budget.max_key_points
    assert tight.copy_budget.max_message_chars <= base.copy_budget.max_message_chars


def test_drawing_story_rule() -> None:
    slide = _slide(
        title="总平面布局",
        message="总平面确立院落轴线与核心公服节点。",
        key_points=["轴线", "绿地", "入口"],
    )
    direction = PageDirectionService().direct(slide)
    assert direction.situation_rule_id == "drawing_story"
    assert LayoutFamily.DRAWING_FOCUS in direction.preferred_layout_families
    assert CompositionBias.DRAWING_DOMINANT in direction.composition_bias

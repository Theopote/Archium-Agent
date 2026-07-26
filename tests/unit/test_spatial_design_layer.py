"""Tests for SpatialIntent / DesignRule / DesignDecision layer."""

from __future__ import annotations

from uuid import uuid4

from archium.application.design_intent_from_direction import design_intent_from_direction
from archium.application.spatial_design_layer import (
    design_decision_from_direction_selection,
    design_rules_from_direction,
    ensure_direction_spatial_layer,
    spatial_intent_from_direction,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_rationale import DesignRationale
from archium.domain.enums import ConceptDirectionStatus
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.intent.intent_evolution import IntentEvolution, IntentEvolutionKind


def _mountain_direction() -> ConceptDirection:
    return ConceptDirection(
        project_id=uuid4(),
        title="山地嵌入",
        summary="文化中心弱化体量、顺应台地",
        theme="融入山体",
        spatial_strategy="建筑嵌入地形，公共空间沿等高线展开，入口作为地景切口",
        formal_language="水平延展、低矮体量、连续屋面",
        material_strategy="自然材料与石材层叠",
        experience_focus="慢行与山体对话",
        risks=["冬季采光不足", "施工难度高"],
        design_rationale=DesignRationale(
            statement="以嵌入而非对峙回应山地",
            reasons=["减少暴露面积", "保持地形连续"],
            evidence=["基地坡度较大"],
            observation="场地为坡地台地",
            problem="大体量对地貌破坏强",
            hypothesis="嵌入可弱化视觉影响",
            strategy="等高线展开 + 地景切口入口",
            risks=["采光"],
            confidence=0.7,
        ),
        status=ConceptDirectionStatus.DRAFT,
    )


def test_spatial_intent_and_rules_from_mountain_concept() -> None:
    direction = _mountain_direction()
    intent = spatial_intent_from_direction(direction)
    assert intent is not None
    assert not intent.is_empty()
    assert "嵌入" in intent.landscape_relation or "地形" in intent.landscape_relation
    assert intent.spatial_relationships

    rules = design_rules_from_direction(direction)
    assert len(rules) >= 2
    assert any("嵌入" in r.spatial_translation or "等高" in r.spatial_translation for r in rules)
    assert any(r.evaluation_method for r in rules)

    enriched = ensure_direction_spatial_layer(direction)
    assert enriched.spatial_intent is not None
    assert enriched.design_rules


def test_design_intent_carries_spatial_layer() -> None:
    direction = ensure_direction_spatial_layer(_mountain_direction())
    intent = design_intent_from_direction(direction, base=DesignIntent(theme="旧主题"))
    assert intent.spatial_intent is not None
    assert not intent.spatial_intent.is_empty()
    assert intent.design_rules
    block = intent.to_prompt_block()
    assert "SpatialIntent" in block or "空间意图" in block
    assert "设计规则" in block


def test_design_decision_and_evolution_payload() -> None:
    direction = ensure_direction_spatial_layer(_mountain_direction())
    decision = design_decision_from_direction_selection(
        direction, previous_theme="开放商业空间"
    )
    assert not decision.is_empty()
    assert "山地嵌入" in decision.chosen
    assert decision.impact

    evo = IntentEvolution().append(
        IntentEvolutionKind.DESIGN_DECISION,
        decision.decision,
        trigger="选定方向",
        previous_summary="开放商业空间",
        new_summary=decision.chosen,
        reason=decision.reason,
        design_decision=decision.as_dict(),
    )
    assert evo.events[-1].design_decision is not None
    assert evo.events[-1].kind == IntentEvolutionKind.DESIGN_DECISION


def test_ensure_idempotent() -> None:
    direction = ensure_direction_spatial_layer(_mountain_direction())
    again = ensure_direction_spatial_layer(direction)
    assert again.spatial_intent == direction.spatial_intent
    assert len(again.design_rules) == len(direction.design_rules)

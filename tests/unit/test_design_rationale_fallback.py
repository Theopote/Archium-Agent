"""Unit tests for DesignRationale fallback and DesignIntent propagation."""

from __future__ import annotations

from uuid import uuid4

from archium.application.design_intent_from_direction import design_intent_from_direction
from archium.application.design_rationale_fallback import (
    ensure_direction_design_rationale,
    synthesize_design_rationale_from_direction,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_rationale import DesignRationale
from archium.domain.enums import ConceptDirectionStatus


def _direction(**kwargs) -> ConceptDirection:
    defaults = {
        "project_id": uuid4(),
        "title": "微创更新",
        "summary": "保留立面与结构，局部加建",
        "spatial_strategy": "保留南北主轴线，点状加建",
        "formal_language": "新旧并置，克制体量",
        "material_strategy": "保留砖墙，局部玻璃连廊",
        "experience_focus": "医护与患者流线清晰",
        "status": ConceptDirectionStatus.DRAFT,
    }
    defaults.update(kwargs)
    return ConceptDirection(**defaults)


def test_synthesize_design_rationale_from_direction() -> None:
    direction = _direction()
    rationale = synthesize_design_rationale_from_direction(
        direction,
        known_facts={"location": "西安"},
        idea_text="医院老院区改造",
    )
    assert rationale is not None
    assert "南北主轴线" in rationale.statement
    assert any("形式语言" in item for item in rationale.reasons)
    assert any("西安" in item for item in rationale.evidence)
    assert rationale.has_reasoning_chain()
    assert "医院老院区" in rationale.observation
    assert "保留立面" in rationale.problem
    assert rationale.strategy.startswith("保留南北")


def test_ensure_direction_design_rationale_preserves_llm_chain() -> None:
    existing = DesignRationale(
        statement="LLM 判断",
        reasons=["理由 A"],
        confidence=0.8,
        observation="LLM 观察",
        problem="LLM 问题",
        hypothesis="LLM 假设",
        strategy="LLM 策略",
    )
    direction = _direction(design_rationale=existing)
    updated = ensure_direction_design_rationale(direction, known_facts={"location": "西安"})
    assert updated.design_rationale is not None
    assert updated.design_rationale.statement == "LLM 判断"
    assert updated.design_rationale.observation == "LLM 观察"
    assert updated.design_rationale.strategy == "LLM 策略"


def test_ensure_backfills_chain_without_overwriting_claim() -> None:
    existing = DesignRationale(statement="LLM 判断", reasons=["理由 A"], confidence=0.8)
    direction = _direction(design_rationale=existing)
    updated = ensure_direction_design_rationale(
        direction,
        known_facts={"location": "西安"},
        idea_text="医院老院区改造",
    )
    assert updated.design_rationale is not None
    assert updated.design_rationale.statement == "LLM 判断"
    assert updated.design_rationale.reasons == ["理由 A"]
    assert updated.design_rationale.has_reasoning_chain()
    assert "医院老院区" in updated.design_rationale.observation
    assert updated.design_rationale.strategy.startswith("保留南北")


def test_design_intent_from_direction_copies_rationale() -> None:
    rationale = DesignRationale(
        statement="保留主轴线",
        reasons=["资料有限时仍可推进讨论"],
        evidence=["location：西安"],
        confidence=0.7,
        observation="南北轴线清晰",
        problem="更新与轴线保留冲突",
        hypothesis="轴线可承载分期更新",
        strategy="保留南北主轴线",
    )
    direction = _direction(design_rationale=rationale)
    intent = design_intent_from_direction(direction)
    assert intent.design_rationale is not None
    assert intent.design_rationale.statement == "保留主轴线"
    assert intent.design_rationale.has_reasoning_chain()
    assert "设计判断" in intent.to_prompt_block()

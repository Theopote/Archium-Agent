"""Smoke tests: shared frameworks are injected into building task prompts."""

from __future__ import annotations

from archium.prompts import autonomous_research as research_prompts
from archium.prompts import concept_direction as concept_prompts
from archium.prompts import design_critique as critique_prompts
from archium.prompts import project_mission as mission_prompts
from archium.prompts.frameworks import (
    ARCHITECTURAL_REASONING_FRAMEWORK,
    ARCHITECTURAL_REASONING_VERSION,
    DESIGN_CRITIQUE_FRAMEWORK,
    RESEARCH_KNOWLEDGE_FRAMEWORK,
)


def test_architectural_reasoning_framework_has_required_steps() -> None:
    text = ARCHITECTURAL_REASONING_FRAMEWORK
    assert "Step 1" in text and "Context" in text
    assert "Step 2" in text and "Problem" in text
    assert "Spatial Translation" in text or "空间转译" in text
    assert "为什么需要" in text
    assert ARCHITECTURAL_REASONING_VERSION.startswith("architectural_reasoning.")


def test_concept_prompt_injects_reasoning_framework() -> None:
    assert concept_prompts.PROMPT_VERSION == "concept_direction.v5"
    assert ARCHITECTURAL_REASONING_FRAMEWORK in concept_prompts.CONCEPT_DIRECTION_SYSTEM_PROMPT
    assert "spatial_strategy、formal_language、risks 不得留空" in (
        concept_prompts.CONCEPT_DIRECTION_SYSTEM_PROMPT
    )
    assert "design_rationale.observation" in concept_prompts.CONCEPT_DIRECTION_SYSTEM_PROMPT
    assert "design_rationale.problem" in concept_prompts.CONCEPT_DIRECTION_SYSTEM_PROMPT
    assert "design_rationale.strategy" in concept_prompts.CONCEPT_DIRECTION_SYSTEM_PROMPT
    user = concept_prompts.build_exploration_direction_user_prompt(
        project_name="山地文化中心",
        idea_text="山地文化中心",
        count=2,
    )
    assert "建筑推理框架" in user
    assert "回应的问题" in user
    assert "observation→problem→hypothesis→strategy" in user


def test_concept_mission_addendum_injects_reasoning() -> None:
    assert mission_prompts.PROMPT_VERSION == "project_mission.v2"
    addendum = mission_prompts.build_concept_mission_addendum()
    assert ARCHITECTURAL_REASONING_FRAMEWORK in addendum
    assert "为什么需要" in addendum


def test_research_prompt_injects_knowledge_framework() -> None:
    assert research_prompts.PROMPT_VERSION == "autonomous_research.v3"
    assert RESEARCH_KNOWLEDGE_FRAMEWORK in research_prompts.AUTONOMOUS_RESEARCH_SYSTEM_PROMPT
    assert "可迁移设计原则" in research_prompts.AUTONOMOUS_RESEARCH_SYSTEM_PROMPT
    assert "spatial_translation" in research_prompts.AUTONOMOUS_RESEARCH_SYSTEM_PROMPT
    user = research_prompts.build_autonomous_research_user_prompt(
        project_name="测试",
        design_context="概念探索",
        research_topics=["山地文化建筑"],
    )
    assert "研究知识提炼" in user


def test_critique_prompt_uses_shared_framework() -> None:
    assert critique_prompts.PROMPT_VERSION == "design_critique.v2"
    assert DESIGN_CRITIQUE_FRAMEWORK in critique_prompts.DESIGN_CRITIQUE_SYSTEM_PROMPT
    assert "Form-only" in critique_prompts.DESIGN_CRITIQUE_SYSTEM_PROMPT or (
        "形式语言" in critique_prompts.DESIGN_CRITIQUE_SYSTEM_PROMPT
    )
    user = critique_prompts.build_design_critique_user_prompt(
        direction_block="方向A",
        design_intent_block="意图",
        research_block="",
    )
    assert "建筑批判框架" in user

"""Tests for presentation cognition gate (Narrative ↔ KnowledgeState)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from archium.application.context.presentation_cognition_gate import (
    enforce_presentation_cognition_gate,
)
from archium.application.context.presentation_readiness import (
    PresentationGateVerdict,
    format_readiness_for_prompt,
    presentation_readiness_from_context,
)
from archium.config.settings import Settings
from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState
from archium.domain.intent.next_best_action import NextBestActionType
from archium.exceptions import WorkflowError


def test_readiness_verdict_block_when_sparse() -> None:
    state = KnowledgeState(
        completeness_score=0.18,
        maturity_stage=KnowledgeMaturityStage.CONCEPT_FORMATION,
        unknown=["用地面积"],
    )
    ctx = ProjectContext(
        knowledge_state=state,
        lifecycle_stage=ProjectLifecycleStage.CONCEPT,
        recommended_workflow=RecommendedWorkflow.RESEARCH,
        confidence=0.2,
    )
    ready = presentation_readiness_from_context(ctx)
    assert ready.verdict == PresentationGateVerdict.BLOCK
    assert ready.suggested_action == NextBestActionType.RESEARCH
    assert ready.blocks_generation is True
    assert "门禁" in ready.summary


def test_readiness_verdict_proceed_when_healthy() -> None:
    state = KnowledgeState(
        completeness_score=0.72,
        maturity_stage=KnowledgeMaturityStage.TECHNICAL_PRESENTATION,
        unknown=[],
    )
    ctx = ProjectContext(
        knowledge_state=state,
        lifecycle_stage=ProjectLifecycleStage.DESIGN,
        recommended_workflow=RecommendedWorkflow.DESIGN,
        confidence=0.7,
    )
    ready = presentation_readiness_from_context(ctx)
    assert ready.verdict == PresentationGateVerdict.PROCEED
    assert ready.suggested_action is None


def test_format_readiness_for_prompt_includes_action() -> None:
    ready = presentation_readiness_from_context(None)
    text = format_readiness_for_prompt(ready)
    assert "知识完备性" in text
    assert "upload_materials" in text or "建议" in text


def test_gate_warn_mode_never_raises(monkeypatch) -> None:
    sparse = presentation_readiness_from_context(
        ProjectContext(
            knowledge_state=KnowledgeState(completeness_score=0.1),
            lifecycle_stage=ProjectLifecycleStage.CONCEPT,
            recommended_workflow=RecommendedWorkflow.RESEARCH,
            confidence=0.1,
        )
    )
    monkeypatch.setattr(
        "archium.application.context.presentation_cognition_gate.evaluate_presentation_cognition",
        lambda *_a, **_k: sparse,
    )
    settings = Settings(_env_file=None, presentation_cognition_gate="warn")
    result = enforce_presentation_cognition_gate(
        MagicMock(),
        uuid4(),
        llm=MagicMock(),
        settings=settings,
    )
    assert result.blocked is False
    assert result.readiness.verdict == PresentationGateVerdict.BLOCK


def test_gate_block_mode_raises(monkeypatch) -> None:
    sparse = presentation_readiness_from_context(
        ProjectContext(
            knowledge_state=KnowledgeState(completeness_score=0.1),
            lifecycle_stage=ProjectLifecycleStage.CONCEPT,
            recommended_workflow=RecommendedWorkflow.RESEARCH,
            confidence=0.1,
        )
    )
    monkeypatch.setattr(
        "archium.application.context.presentation_cognition_gate.evaluate_presentation_cognition",
        lambda *_a, **_k: sparse,
    )
    settings = Settings(_env_file=None, presentation_cognition_gate="block")
    with pytest.raises(WorkflowError, match="认知门禁"):
        enforce_presentation_cognition_gate(
            MagicMock(),
            uuid4(),
            llm=MagicMock(),
            settings=settings,
        )


def test_gate_block_mode_force_bypasses(monkeypatch) -> None:
    sparse = presentation_readiness_from_context(
        ProjectContext(
            knowledge_state=KnowledgeState(completeness_score=0.1),
            lifecycle_stage=ProjectLifecycleStage.CONCEPT,
            recommended_workflow=RecommendedWorkflow.RESEARCH,
            confidence=0.1,
        )
    )
    monkeypatch.setattr(
        "archium.application.context.presentation_cognition_gate.evaluate_presentation_cognition",
        lambda *_a, **_k: sparse,
    )
    settings = Settings(_env_file=None, presentation_cognition_gate="block")
    result = enforce_presentation_cognition_gate(
        MagicMock(),
        uuid4(),
        llm=MagicMock(),
        settings=settings,
        force=True,
    )
    assert result.blocked is False
    assert any("强制" in m for m in result.messages)


def test_gate_auto_research_runs_nba(monkeypatch) -> None:
    before = presentation_readiness_from_context(
        ProjectContext(
            knowledge_state=KnowledgeState(completeness_score=0.2),
            lifecycle_stage=ProjectLifecycleStage.CONCEPT,
            recommended_workflow=RecommendedWorkflow.RESEARCH,
            confidence=0.2,
        )
    )
    after = presentation_readiness_from_context(
        ProjectContext(
            knowledge_state=KnowledgeState(completeness_score=0.55),
            lifecycle_stage=ProjectLifecycleStage.CONCEPT,
            recommended_workflow=RecommendedWorkflow.DESIGN,
            confidence=0.5,
        )
    )
    calls = {"n": 0}

    def fake_eval(*_a, **_k):
        calls["n"] += 1
        return before if calls["n"] == 1 else after

    class FakeNba:
        def __init__(self, *_a, **_k):
            pass

        def execute(self, *_a, **_k):
            from archium.application.context.nba_action_executor import NbaExecutionResult

            return NbaExecutionResult(
                action=NextBestActionType.RESEARCH,
                executed=True,
                success=True,
                message="researched 2 topics",
            )

    monkeypatch.setattr(
        "archium.application.context.presentation_cognition_gate.evaluate_presentation_cognition",
        fake_eval,
    )
    monkeypatch.setattr(
        "archium.application.context.nba_action_executor.NbaActionExecutor",
        FakeNba,
    )
    settings = Settings(_env_file=None, presentation_cognition_gate="auto_research")
    result = enforce_presentation_cognition_gate(
        MagicMock(),
        uuid4(),
        llm=MagicMock(),
        settings=settings,
    )
    assert result.auto_research_ran is True
    assert result.readiness.completeness_pct == 55
    assert any("自动执行研究" in m for m in result.messages)

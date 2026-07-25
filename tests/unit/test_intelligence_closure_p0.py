"""Unit tests for Intelligence Closure P0 — reassess hooks + presentation readiness."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from archium.application.context.knowledge_reassess import (
    ReassessMode,
    best_effort_reassess_knowledge,
    classify_reassess_mode,
)
from archium.application.context.presentation_readiness import (
    presentation_readiness_from_context,
)
from archium.application.context.types import ContextAssessment
from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState


def test_classify_reassess_mode_fact_confirmed_is_index() -> None:
    assert classify_reassess_mode("fact_confirmed") == ReassessMode.INDEX
    assert classify_reassess_mode("fact_rejected") == ReassessMode.INDEX
    assert classify_reassess_mode("knowledge_item_confirmed") == ReassessMode.INDEX
    assert classify_reassess_mode("knowledge_item_rejected") == ReassessMode.INDEX
    assert classify_reassess_mode("mission_approved") == ReassessMode.FULL
    assert classify_reassess_mode("document_uploaded") == ReassessMode.FULL
    assert classify_reassess_mode("direction_selected") == ReassessMode.FULL


def test_best_effort_reassess_returns_none_on_failure(monkeypatch) -> None:
    def boom(*_a, **_k):  # noqa: ANN002, ANN003
        raise RuntimeError("llm down")

    monkeypatch.setattr(
        "archium.application.context.context_analyzer.ContextAnalyzer.reassess",
        boom,
    )
    monkeypatch.setattr(
        "archium.infrastructure.llm.factory.create_llm_provider",
        lambda _settings: MagicMock(),
    )
    monkeypatch.setattr(
        "archium.application.context.knowledge_claim_index.refresh_claim_index_only",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no ks")),
    )
    assert best_effort_reassess_knowledge(MagicMock(), uuid4(), reason="test") is None


def test_best_effort_reassess_returns_assessment(monkeypatch) -> None:
    assessment = ContextAssessment(
        knowledge_state=KnowledgeState(completeness_score=0.42),
        understanding_summary="ok",
    )

    class FakeAnalyzer:
        def __init__(self, *_a, **_k):  # noqa: ANN002, ANN003
            pass

        def reassess(self, _project_id, **_kwargs):  # noqa: ANN001
            return assessment

    monkeypatch.setattr(
        "archium.application.context.context_analyzer.ContextAnalyzer",
        FakeAnalyzer,
    )
    monkeypatch.setattr(
        "archium.infrastructure.llm.factory.create_llm_provider",
        lambda _settings: MagicMock(),
    )
    out = best_effort_reassess_knowledge(MagicMock(), uuid4(), reason="mission_approved")
    assert out is assessment


def test_best_effort_fact_confirmed_uses_index_path(monkeypatch) -> None:
    calls: list[str] = []
    state = KnowledgeState(completeness_score=0.5, claims=[])

    def fake_index(*_a, **_k):  # noqa: ANN002, ANN003
        calls.append("index")
        return state

    def fake_build(*_a, **_k):  # noqa: ANN002, ANN003
        return ProjectContext.compose(
            knowledge_state=state,
            next_actions=[],
            understanding_summary="indexed",
        )

    def boom_analyzer(*_a, **_k):  # noqa: ANN002, ANN003
        raise AssertionError("full LLM path should not run for fact_confirmed")

    monkeypatch.setattr(
        "archium.application.context.knowledge_claim_index.refresh_claim_index_only",
        fake_index,
    )
    monkeypatch.setattr(
        "archium.application.context.project_context_builder.build_project_context",
        fake_build,
    )
    monkeypatch.setattr(
        "archium.application.context.context_analyzer.ContextAnalyzer",
        boom_analyzer,
    )
    out = best_effort_reassess_knowledge(
        MagicMock(), uuid4(), reason="fact_confirmed"
    )
    assert out is not None
    assert calls == ["index"]
    assert out.understanding_summary == "indexed"


def test_presentation_readiness_without_context() -> None:
    ready = presentation_readiness_from_context(None)
    assert ready.has_context is False
    assert ready.warnings
    assert "ProjectContext" in ready.warnings[0] or "知识状态" in ready.summary


def test_presentation_readiness_warns_on_sparse_knowledge() -> None:
    state = KnowledgeState(
        completeness_score=0.18,
        maturity_stage=KnowledgeMaturityStage.CONCEPT_FORMATION,
        unknown=["用地面积", "消防间距", "预算上限"],
        missing_information=["总平面"],
    )
    ctx = ProjectContext(
        knowledge_state=state,
        lifecycle_stage=ProjectLifecycleStage.CONCEPT,
        recommended_workflow=RecommendedWorkflow.RESEARCH,
        confidence=0.2,
    )
    ready = presentation_readiness_from_context(ctx)
    assert ready.has_context is True
    assert ready.completeness_pct == 18
    assert any("完整度" in w for w in ready.warnings)
    assert any("未知项" in w for w in ready.warnings)
    assert any("研究" in w for w in ready.warnings)


def test_approve_mission_triggers_reassess(monkeypatch) -> None:
    from archium.application.project_mission_service import ProjectMissionService
    from archium.domain.enums import ApprovalStatus
    from archium.domain.project_mission import ProjectMission

    mission = ProjectMission(
        project_id=uuid4(),
        title="测试任务",
        task_statement="做概念汇报",
        approval_status=ApprovalStatus.DRAFT,
    )
    calls: list[str] = []

    def fake_reassess(*_a, **kwargs):  # noqa: ANN002, ANN003
        calls.append(str(kwargs.get("reason") or ""))
        return None

    monkeypatch.setattr(
        "archium.application.context.best_effort_reassess_knowledge",
        fake_reassess,
    )

    service = ProjectMissionService(MagicMock(), MagicMock())
    service._require_mission = lambda _mid: mission  # noqa: SLF001
    service._missions = MagicMock()  # noqa: SLF001
    service._missions.save_mission.side_effect = lambda m: m
    service._history = MagicMock()  # noqa: SLF001

    monkeypatch.setattr(
        "archium.application.project_mission_service.suggest_narrative_mode",
        lambda _m: MagicMock(mode=None),
    )

    service.approve_mission(mission.id)
    assert "mission_approved" in calls

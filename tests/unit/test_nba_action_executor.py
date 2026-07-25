"""Unit tests for NbaActionExecutor (Intelligence Closure P2)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from archium.application.context.nba_action_executor import (
    NbaActionExecutor,
    nba_execute_label,
)
from archium.domain.intent.next_best_action import NextBestActionType


def test_nba_execute_labels() -> None:
    assert nba_execute_label(NextBestActionType.RESEARCH) == "开始研究"
    assert (
        nba_execute_label(NextBestActionType.RESEARCH, reason="补充当地文化研究")
        == "开始文化研究"
    )
    assert nba_execute_label(NextBestActionType.EXPLORE_DIRECTIONS) == "开始推演方向"
    assert nba_execute_label(NextBestActionType.GENERATE_MISSION) == "生成任务理解"
    assert nba_execute_label(NextBestActionType.ASK, has_pending_facts=True).startswith(
        "确认"
    )


def test_ask_with_pending_facts_navigates_only() -> None:
    executor = NbaActionExecutor(MagicMock(), MagicMock())
    result = executor.execute(
        uuid4(),
        NextBestActionType.ASK,
        pending_fact_count=2,
    )
    assert result.executed is False
    assert result.success is True
    assert result.page_key == "materials"
    assert result.focus == "pending_facts"


def test_upload_is_navigate_only() -> None:
    executor = NbaActionExecutor(MagicMock(), MagicMock())
    result = executor.execute(uuid4(), NextBestActionType.UPLOAD_MATERIALS)
    assert result.executed is False
    assert result.page_key == "materials"


def test_research_success_stays_for_reassess_loop(monkeypatch) -> None:
    executor = NbaActionExecutor(MagicMock(), MagicMock())

    class FakeAnalyzer:
        def __init__(self, *_a, **_k):  # noqa: ANN002, ANN003
            pass

        def try_execute_research(self, _pid):  # noqa: ANN001
            return True, "已生成 2 条公开研究摘要。知识状态已刷新，下一步建议已更新。"

    monkeypatch.setattr(
        "archium.application.context.context_analyzer.ContextAnalyzer",
        FakeAnalyzer,
    )
    result = executor.execute(uuid4(), NextBestActionType.RESEARCH)
    assert result.executed is True
    assert result.success is True
    assert result.stay_after_execute is True
    assert result.should_navigate is False
    assert result.orchestration_action == "none"
    assert result.reassessed is True
    assert "研究" in result.message or "摘要" in result.message


def test_generate_mission_when_none_exists(monkeypatch) -> None:
    project_id = uuid4()
    executor = NbaActionExecutor(MagicMock(), MagicMock())

    class FakeMissions:
        def list_missions_by_project(self, _pid):  # noqa: ANN001
            return []

    class FakeMissionService:
        def __init__(self, *_a, **_k):  # noqa: ANN002, ANN003
            pass

        def generate_mission(self, _pid, _text):  # noqa: ANN001
            mission = MagicMock()
            mission.title = "医院改造"
            return MagicMock(mission=mission, warnings=[])

    class FakeProjects:
        def get_by_id(self, _pid):  # noqa: ANN001
            project = MagicMock()
            project.description = "西安医院改造"
            project.name = "医院"
            return project

    monkeypatch.setattr(
        "archium.infrastructure.database.mission_repositories.MissionRepository",
        lambda _s: FakeMissions(),
    )
    monkeypatch.setattr(
        "archium.application.project_mission_service.ProjectMissionService",
        FakeMissionService,
    )
    monkeypatch.setattr(
        "archium.infrastructure.database.repositories.ProjectRepository",
        lambda _s: FakeProjects(),
    )
    monkeypatch.setattr(
        "archium.application.context.nba_action_executor.best_effort_reassess_knowledge",
        lambda *_a, **_k: MagicMock(),
    )

    result = executor.execute(
        project_id,
        NextBestActionType.GENERATE_MISSION,
        user_task_description="西安医院改造",
    )
    assert result.executed is True
    assert result.success is True
    assert "医院改造" in result.message


def test_explore_starts_session_and_generates(monkeypatch) -> None:
    project_id = uuid4()
    executor = NbaActionExecutor(MagicMock(), MagicMock())
    exploration = MagicMock()
    exploration.id = uuid4()
    exploration.status = MagicMock()
    # Use real enum
    from archium.domain.enums import ExplorationSessionStatus

    exploration.status = ExplorationSessionStatus.EXPLORING

    class FakeExplorationService:
        def __init__(self, *_a, **_k):  # noqa: ANN002, ANN003
            pass

        def get_latest_for_project(self, _pid):  # noqa: ANN001
            return None

        def start_session(self, _pid, _idea, **_k):  # noqa: ANN001
            return MagicMock(exploration=exploration, warnings=[])

        def list_directions(self, _eid):  # noqa: ANN001
            return []

        def generate_directions(self, _eid, **_k):  # noqa: ANN001
            return MagicMock(directions=[MagicMock(), MagicMock()], warnings=[])

    monkeypatch.setattr(
        "archium.application.exploration_service.ExplorationService",
        FakeExplorationService,
    )
    monkeypatch.setattr(
        "archium.application.context.nba_action_executor.best_effort_reassess_knowledge",
        lambda *_a, **_k: MagicMock(),
    )
    monkeypatch.setattr(
        "archium.infrastructure.database.repositories.ProjectRepository",
        lambda _s: MagicMock(
            get_by_id=lambda _pid: MagicMock(description="台地聚落", name="项目")
        ),
    )

    result = executor.execute(
        project_id,
        NextBestActionType.EXPLORE_DIRECTIONS,
        user_task_description="台地聚落想法",
    )
    assert result.executed is True
    assert result.success is True
    assert result.page_key == "concept-exploration"
    assert "2" in result.message

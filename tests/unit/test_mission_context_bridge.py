"""Tests for mission context bridge helpers."""

from __future__ import annotations

from uuid import uuid4

from archium.application.mission_context_bridge import merge_mission_project_context
from archium.domain.project_mission import ProjectMission


def test_merge_mission_project_context_appends_supplement() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="测试",
        task_statement="探索文化中心",
        project_context="【已确认公开研究】\n- 关中乡村公共文化空间案例",
    )

    merged = merge_mission_project_context("资料摘要", mission)

    assert "资料摘要" in merged
    assert "【任务理解语境】" in merged
    assert "关中乡村" in merged


def test_merge_mission_project_context_skips_duplicate() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="测试",
        task_statement="探索",
        project_context="已有研究语境",
    )

    merged = merge_mission_project_context("前缀\n\n已有研究语境", mission)

    assert merged == "前缀\n\n已有研究语境"

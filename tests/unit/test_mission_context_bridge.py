"""Tests for mission context bridge helpers."""

from __future__ import annotations

from uuid import uuid4

from archium.application.mission_context_bridge import (
    enrich_mission_generation_context,
    merge_concept_direction_context,
    merge_design_intent_context,
    merge_mission_project_context,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import ConceptDirectionStatus, ProjectOriginMode
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.project import Project
from archium.domain.project_mission import ProjectMission
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    ConceptDirectionRepository,
    ProjectRepository,
)


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


def test_merge_design_intent_and_concept_direction() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="测试",
        task_statement="探索",
        design_intent=DesignIntent(theme="地域再生", problem_statement="如何建立方向？"),
    )
    direction = ConceptDirection(
        project_id=mission.project_id,
        mission_id=mission.id,
        title="窑洞再生",
        summary="以窑洞原型转译公共空间",
        theme="窑洞当代化",
        spatial_idea="半地下拱廊",
        differentiator="窑洞构造作为主叙事",
        status=ConceptDirectionStatus.SELECTED,
    )

    with_intent = merge_design_intent_context("资料", mission)
    assert "【设计使命】" in with_intent
    assert "地域再生" in with_intent

    merged = merge_concept_direction_context(with_intent, direction)
    assert "【当前概念方向】" in merged
    assert "窑洞再生" in merged
    assert "半地下拱廊" in merged


def test_enrich_mission_generation_context_includes_selected_direction(
    db_session,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="概念注入", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    mission = MissionRepository(db_session).save_mission(
        ProjectMission(
            project_id=project.id,
            title="文化中心",
            task_statement="探索概念",
            design_intent=DesignIntent(theme="初稿主题"),
            project_context="研究补充",
        )
    )
    ConceptDirectionRepository(db_session).create(
        ConceptDirection(
            project_id=project.id,
            mission_id=mission.id,
            title="台地聚落",
            summary="沿台地展开",
            theme="台地生活",
            spatial_idea="分散院落",
            status=ConceptDirectionStatus.SELECTED,
        )
    )
    db_session.commit()

    enriched = enrich_mission_generation_context(db_session, "资料摘要", mission)
    assert "研究补充" in enriched
    assert "【设计使命】" in enriched
    assert "【当前概念方向】" in enriched
    assert "台地聚落" in enriched
    assert "分散院落" in enriched

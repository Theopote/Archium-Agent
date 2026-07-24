"""Unit tests for concept direction (design iteration) service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from archium.application.concept_direction_service import ConceptDirectionService
from archium.domain.enums import (
    ConceptDirectionStatus,
    ProjectOriginMode,
    TaskNature,
)
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.project import Project
from archium.domain.project_mission import ProjectMission
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.concept_direction_schemas import (
    ConceptDirectionBatchDraft,
    ConceptDirectionDraft,
)


@pytest.fixture
def concept_mission(db_session):
    project = ProjectRepository(db_session).create(
        Project(
            name="黄土高原文化中心",
            origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
        )
    )
    mission = MissionRepository(db_session).save_mission(
        ProjectMission(
            project_id=project.id,
            title="文化中心概念探索",
            task_statement="探索嵌入地域文化的小型文化中心概念方向",
            task_natures=[TaskNature.PLANNING, TaskNature.RESEARCH],
            design_intent=DesignIntent(
                theme="地域文化再生",
                problem_statement="如何在缺少任务书时建立可讨论方向？",
                desired_experience="在地认同与开放交流",
            ),
            project_context="仅有一句话想法",
        )
    )
    db_session.commit()
    return mission


def test_generate_and_select_concept_directions(db_session, concept_mission) -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = ConceptDirectionBatchDraft(
        directions=[
            ConceptDirectionDraft(
                title="台地聚落",
                summary="沿台地展开的开放群落",
                theme="台地生活",
                spatial_idea="分散院落 + 共享庭院",
                experience_focus="村民日常与游客穿行并存",
                differentiator="以台地地貌组织公共空间",
                open_questions=["规模上限？"],
                risks=["运营负担"],
            ),
            ConceptDirectionDraft(
                title="窑洞再生",
                summary="以窑洞原型转译当代公共空间",
                theme="窑洞当代化",
                spatial_idea="半地下连续拱廊",
                experience_focus="庇护与仪式感",
                differentiator="窑洞构造作为主叙事",
                open_questions=["防水与采光？"],
                risks=["施工复杂度"],
            ),
            ConceptDirectionDraft(
                title="景观驿站",
                summary="轻量驿站串联周边景观",
                theme="轻介入",
                spatial_idea="线性廊道与眺望点",
                experience_focus="路过停留",
                differentiator="最小建筑量",
                open_questions=["是否需要常驻功能？"],
                risks=["辨识度不足"],
            ),
        ]
    )
    service = ConceptDirectionService(db_session, llm)

    generated = service.generate_directions(concept_mission.id, count=3)
    assert len(generated.directions) == 3
    assert all(item.status == ConceptDirectionStatus.DRAFT for item in generated.directions)

    selected = service.select_direction(generated.directions[1].id)
    assert selected.direction.status == ConceptDirectionStatus.SELECTED
    assert selected.mission.design_intent is not None
    assert selected.mission.design_intent.theme == "窑洞当代化"
    assert "窑洞原型" in selected.mission.design_intent.problem_statement

    listed = service.list_directions(concept_mission.id)
    selected_count = sum(
        1 for item in listed if item.status == ConceptDirectionStatus.SELECTED
    )
    assert selected_count == 1


def test_regenerate_archives_previous_drafts(db_session, concept_mission) -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = ConceptDirectionBatchDraft(
        directions=[
            ConceptDirectionDraft(title="方向A", summary="摘要A"),
            ConceptDirectionDraft(title="方向B", summary="摘要B"),
        ]
    )
    service = ConceptDirectionService(db_session, llm)
    first = service.generate_directions(concept_mission.id, count=2)
    assert len(first.directions) == 2

    llm.generate_structured.return_value = ConceptDirectionBatchDraft(
        directions=[
            ConceptDirectionDraft(title="方向C", summary="摘要C"),
            ConceptDirectionDraft(title="方向D", summary="摘要D"),
            ConceptDirectionDraft(title="方向E", summary="摘要E"),
        ]
    )
    second = service.generate_directions(concept_mission.id, count=3)
    assert len(second.directions) == 3

    active = service.list_directions(concept_mission.id)
    titles = {item.title for item in active}
    assert titles == {"方向C", "方向D", "方向E"}
    archived = service.list_directions(concept_mission.id, include_archived=True)
    assert any(item.status == ConceptDirectionStatus.ARCHIVED for item in archived)

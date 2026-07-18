"""Tests for ProjectMissionService."""

from __future__ import annotations

import pytest
from archium.application.project_mission_service import MissionPatch, ProjectMissionService
from archium.domain.enums import (
    ApprovalStatus,
    KnowledgeGapCategory,
    TaskNature,
)
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.exceptions import StructuredOutputError, WorkflowError
from archium.infrastructure.database.repositories import FactRepository, ProjectRepository
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mock_mission_responses import (
    FABRICATED_AREA_MISSION_JSON,
    FIRE_STATION_MISSION_JSON,
    TEMPLE_MISSION_JSON,
)


def mission_mock_selector(request: LLMRequest) -> str | None:
    prompt = request.user_prompt
    if "ProjectMission JSON" not in prompt:
        return None
    task_section = prompt.split("【已导入资料摘要】", maxsplit=1)[0]
    if "FABRICATED_TEST" in task_section:
        return FABRICATED_AREA_MISSION_JSON
    if "消防站" in task_section:
        return FIRE_STATION_MISSION_JSON
    return TEMPLE_MISSION_JSON


@pytest.fixture
def mission_service(db_session: Session) -> ProjectMissionService:
    llm = MockLLMProvider(selector=mission_mock_selector)
    return ProjectMissionService(db_session, llm)


@pytest.fixture
def temple_project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(
        Project(name="三原县清凉寺", description="历史寺庙重建")
    )


@pytest.fixture
def fire_station_project(db_session: Session) -> Project:
    project = ProjectRepository(db_session).create(Project(name="某区消防站新建"))
    facts = FactRepository(db_session)
    for key, label, value, unit in (
        ("site_area", "用地面积", 8000, "㎡"),
        ("building_area", "建筑面积", 4500, "㎡"),
        ("height", "建筑高度", 24, "m"),
    ):
        fact = ProjectFact(
            project_id=project.id,
            key=key,
            label=label,
            value=value,
            unit=unit,
            category="area" if "area" in key else "dimension",
        )
        fact.confirm()
        facts.create(fact)
    return project


TEMPLE_TASK = (
    "三原县清凉寺历史上多次被毁，现在希望重新建设。"
    "目前只有部分地方志和现场照片，甲方还没有明确建筑面积。"
    "希望先形成前期策划、案例研究和概念设计汇报。"
)


def test_generate_mission_from_free_description(
    mission_service: ProjectMissionService,
    temple_project: Project,
) -> None:
    result = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    assert TaskNature.RECONSTRUCTION in result.mission.task_natures
    assert TaskNature.RESEARCH in result.mission.task_natures
    assert "施工图" in " ".join(result.mission.out_of_scope)
    assert result.mission.confidence <= 0.5
    assert len(result.knowledge_gaps) >= 1
    assert any(gap.category == KnowledgeGapCategory.AREA for gap in result.knowledge_gaps)
    assert len(result.clarifying_questions) <= 5
    assert len(result.clarifying_questions) >= 1


def test_generate_mission_does_not_fabricate_area(
    mission_service: ProjectMissionService,
    temple_project: Project,
) -> None:
    result = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    constraint_text = " ".join(item.value for item in result.mission.known_constraints)
    assert "12000" not in constraint_text


def test_generate_mission_preserves_confirmed_facts(
    mission_service: ProjectMissionService,
    fire_station_project: Project,
) -> None:
    task = "消防站新建，已有明确用地8000㎡、建筑面积4500㎡、高度24m，需开展功能策划和规范研究。"
    result = mission_service.generate_mission(fire_station_project.id, task)
    constraints = " ".join(c.value for c in result.mission.known_constraints)
    assert "4500" in constraints or "8000" in constraints
    area_gaps = [g for g in result.knowledge_gaps if g.category == KnowledgeGapCategory.AREA]
    assert area_gaps == []


def test_rejects_fabricated_confirmed_metrics(
    mission_service: ProjectMissionService,
    temple_project: Project,
) -> None:
    with pytest.raises(WorkflowError, match="缺少事实账本依据"):
        mission_service.generate_mission(temple_project.id, "FABRICATED_TEST 编造面积测试")


def test_regenerate_mission_with_feedback(
    mission_service: ProjectMissionService,
    temple_project: Project,
) -> None:
    first = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    second = mission_service.regenerate_mission(
        first.mission.id,
        "请将 out_of_scope 增加'造价测算'",
    )
    assert second.mission.version == first.mission.version + 1
    assert second.mission.lineage_id == first.mission.lineage_id


def test_update_and_approve_mission(
    mission_service: ProjectMissionService,
    temple_project: Project,
) -> None:
    result = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    updated = mission_service.update_mission(
        result.mission.id,
        MissionPatch(title="修订后的任务标题", confidence=0.6),
    )
    assert updated.title == "修订后的任务标题"
    assert updated.confidence == 0.6

    approved = mission_service.approve_mission(result.mission.id)
    assert approved.approval_status == ApprovalStatus.APPROVED


def test_empty_task_description_rejected(
    mission_service: ProjectMissionService,
    temple_project: Project,
) -> None:
    with pytest.raises(WorkflowError, match="任务描述"):
        mission_service.generate_mission(temple_project.id, "   ")


def test_get_mission_bundle(
    mission_service: ProjectMissionService,
    temple_project: Project,
) -> None:
    generated = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    bundle = mission_service.get_mission_bundle(generated.mission.id)
    assert bundle.mission.id == generated.mission.id
    assert len(bundle.knowledge_gaps) == len(generated.knowledge_gaps)


def test_illegal_llm_json_raises_structured_output_error(
    db_session: Session,
    temple_project: Project,
) -> None:
    llm = MockLLMProvider(selector=lambda _request: "{not-json")
    service = ProjectMissionService(db_session, llm)
    with pytest.raises(StructuredOutputError):
        service.generate_mission(temple_project.id, TEMPLE_TASK)


def test_regenerate_does_not_duplicate_open_gaps(
    mission_service: ProjectMissionService,
    temple_project: Project,
) -> None:
    first = mission_service.generate_mission(temple_project.id, TEMPLE_TASK)
    second = mission_service.regenerate_mission(
        first.mission.id,
        "请更强调历史研究，面积仍未知",
    )
    first_bundle = mission_service.get_mission_bundle(first.mission.id)
    second_bundle = mission_service.get_mission_bundle(second.mission.id)
    assert second.mission.id != first.mission.id
    assert second.mission.lineage_id == first.mission.lineage_id
    assert second.mission.version == first.mission.version + 1
    # New version has its own gap set; regenerating must not pile onto the old mission
    assert len(first_bundle.knowledge_gaps) == len(first.knowledge_gaps)
    assert len(second_bundle.knowledge_gaps) == len(second.knowledge_gaps)
    assert {g.id for g in first_bundle.knowledge_gaps}.isdisjoint(
        {g.id for g in second_bundle.knowledge_gaps}
    )

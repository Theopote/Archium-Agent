"""Tests for MissionRepository."""

from __future__ import annotations

from uuid import UUID

import pytest
from archium.domain.architectural_narrative_mode import ArchitecturalNarrativeMode
from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import (
    ApprovalStatus,
    DeliverableType,
    InterventionScale,
    KnowledgeGapCategory,
    TaskNature,
    WorkstreamType,
)
from archium.domain.knowledge_gap import (
    Assumption,
    ClarifyingQuestion,
    DesignQuestion,
    KnowledgeGap,
)
from archium.domain.project import Project
from archium.domain.project_mission import MissionConstraint, ProjectMission, Stakeholder
from archium.domain.workstream import Workstream
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ProjectRepository
from sqlalchemy.orm import Session


@pytest.fixture
def project_id(db_session: Session) -> UUID:
    project = ProjectRepository(db_session).create(Project(name="清凉寺重建"))
    return project.id


@pytest.fixture
def mission_repo(db_session: Session) -> MissionRepository:
    return MissionRepository(db_session)


def _sample_mission(project_id: UUID) -> ProjectMission:
    return ProjectMission(
        project_id=project_id,
        title="清凉寺重建前期策划",
        task_statement="形成前期策划与概念汇报",
        task_natures=[TaskNature.RECONSTRUCTION, TaskNature.RESEARCH],
        intervention_scales=[InterventionScale.SITE],
        in_scope=["前期策划", "概念汇报"],
        out_of_scope=["施工图设计"],
        stakeholders=[Stakeholder(name="甲方", role="业主", concerns=["宗教功能"])],
        known_constraints=[
            MissionConstraint(name="资料", value="地方志与现场照片", importance="high"),
        ],
        design_questions=["重建策略应如何平衡历史与当代？"],
    )


def test_save_and_get_mission(mission_repo: MissionRepository, project_id: UUID) -> None:
    mission = _sample_mission(project_id)
    saved = mission_repo.save_mission(mission)
    fetched = mission_repo.get_mission(saved.id)
    assert fetched is not None
    assert fetched.title == mission.title
    assert fetched.task_natures == mission.task_natures
    assert fetched.stakeholders[0].name == "甲方"
    assert fetched.out_of_scope == ["施工图设计"]


def test_narrative_mode_survives_repository_round_trip(
    mission_repo: MissionRepository, project_id: UUID
) -> None:
    mission = _sample_mission(project_id)
    mission.narrative_mode = ArchitecturalNarrativeMode.DECISION_FIRST
    saved = mission_repo.save_mission(mission)
    fetched = mission_repo.get_mission(saved.id)
    assert fetched is not None
    assert fetched.narrative_mode == ArchitecturalNarrativeMode.DECISION_FIRST


def test_list_missions_by_project(mission_repo: MissionRepository, project_id: UUID) -> None:
    mission_repo.save_mission(_sample_mission(project_id))
    second = _sample_mission(project_id)
    second.version = 2
    mission_repo.save_mission(second)
    missions = mission_repo.list_missions_by_project(project_id)
    assert len(missions) == 2


def test_get_latest_mission_by_lineage(mission_repo: MissionRepository, project_id: UUID) -> None:
    mission = mission_repo.save_mission(_sample_mission(project_id))
    newer = mission.model_copy(update={"version": 2, "title": "更新版任务理解"})
    mission_repo.save_mission(newer)
    latest = mission_repo.get_latest_mission_by_lineage(mission.lineage_id)
    assert latest is not None
    assert latest.version == 2
    assert latest.title == "更新版任务理解"


def test_knowledge_gap_persistence(mission_repo: MissionRepository, project_id: UUID) -> None:
    mission = mission_repo.save_mission(_sample_mission(project_id))
    gap = KnowledgeGap(
        project_id=project_id,
        mission_id=mission.id,
        category=KnowledgeGapCategory.AREA,
        question="建设规模是多少？",
        why_it_matters="影响功能配置",
    )
    saved = mission_repo.save_knowledge_gap(gap)
    gaps = mission_repo.list_knowledge_gaps(mission.id)
    assert len(gaps) == 1
    assert gaps[0].id == saved.id
    assert gaps[0].category == KnowledgeGapCategory.AREA


def test_assumption_persistence(mission_repo: MissionRepository, project_id: UUID) -> None:
    mission = mission_repo.save_mission(_sample_mission(project_id))
    assumption = Assumption(
        project_id=project_id,
        mission_id=mission.id,
        statement="暂按中等规模估算",
        reason="甲方未提供面积",
    )
    assumption.accept()
    mission_repo.save_assumption(assumption)
    assumptions = mission_repo.list_assumptions(mission.id)
    assert len(assumptions) == 1
    assert assumptions[0].status.value == "accepted"


def test_clarifying_question_persistence(mission_repo: MissionRepository, project_id: UUID) -> None:
    mission = mission_repo.save_mission(_sample_mission(project_id))
    question = ClarifyingQuestion(
        project_id=project_id,
        mission_id=mission.id,
        question="更倾向历史复原还是当代表达？",
        why_asked="影响重建策略",
        suggested_assumption="传统语汇新建",
    )
    question.assume()
    mission_repo.save_clarifying_question(question)
    questions = mission_repo.list_clarifying_questions(mission.id)
    assert len(questions) == 1
    assert questions[0].answer == "传统语汇新建"


def test_design_question_persistence(mission_repo: MissionRepository, project_id: UUID) -> None:
    mission = mission_repo.save_mission(_sample_mission(project_id))
    dq = DesignQuestion(
        project_id=project_id,
        mission_id=mission.id,
        question="如何在用地紧张条件下组织礼佛流线？",
        related_problem="场地受限",
    )
    dq.approve()
    mission_repo.save_design_question(dq)
    questions = mission_repo.list_design_questions(mission.id)
    assert len(questions) == 1
    assert questions[0].status == ApprovalStatus.APPROVED


def test_workstream_persistence_and_delete(mission_repo: MissionRepository, project_id: UUID) -> None:
    mission = mission_repo.save_mission(_sample_mission(project_id))
    ws = Workstream(
        project_id=project_id,
        mission_id=mission.id,
        title="历史研究",
        workstream_type=WorkstreamType.HISTORICAL_RESEARCH,
        objective="梳理历史沿革",
        recommendation_reason="重建任务依赖历史依据",
    )
    ws.select()
    mission_repo.save_workstream(ws)
    workstreams = mission_repo.list_workstreams(mission.id)
    assert len(workstreams) == 1
    assert workstreams[0].selected is True
    assert workstreams[0].recommendation_reason == "重建任务依赖历史依据"
    deleted = mission_repo.delete_workstreams_for_mission(mission.id)
    assert deleted == 1
    assert mission_repo.list_workstreams(mission.id) == []


def test_deliverable_plan_persistence(mission_repo: MissionRepository, project_id: UUID) -> None:
    mission = mission_repo.save_mission(_sample_mission(project_id))
    plan = DeliverablePlan(
        project_id=project_id,
        mission_id=mission.id,
        deliverables=[
            PlannedDeliverable(
                id="del-ppt",
                title="概念汇报",
                deliverable_type=DeliverableType.PRESENTATION,
                purpose="汇报重建策略",
                selected=True,
            ),
        ],
    )
    plan.approve()
    mission_repo.save_deliverable_plan(plan)
    fetched = mission_repo.get_deliverable_plan(plan.id)
    assert fetched is not None
    assert len(fetched.deliverables) == 1
    approved = mission_repo.get_approved_deliverable_plan(mission.id)
    assert approved is not None
    assert approved.approval_status == ApprovalStatus.APPROVED


def test_cascade_delete_with_project(db_session: Session, mission_repo: MissionRepository) -> None:
    project = ProjectRepository(db_session).create(Project(name="待删除项目"))
    mission = mission_repo.save_mission(
        ProjectMission(
            project_id=project.id,
            title="测试",
            task_statement="测试任务",
        )
    )
    mission_repo.save_knowledge_gap(
        KnowledgeGap(
            project_id=project.id,
            mission_id=mission.id,
            question="问题",
            why_it_matters="原因",
        )
    )
    ProjectRepository(db_session).delete(project.id)
    db_session.expire_all()
    assert mission_repo.get_mission(mission.id) is None

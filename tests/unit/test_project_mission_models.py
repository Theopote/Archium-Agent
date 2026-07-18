"""Tests for project mission and adaptive planning domain models."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from archium.domain._base import model_to_dict
from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import (
    ApprovalStatus,
    AssumptionStatus,
    DeliverableType,
    InterventionScale,
    KnowledgeGapStatus,
    Priority,
    QuestionAnswerType,
    QuestionStatus,
    ServiceDepth,
    TaskNature,
    UncertaintyLevel,
    WorkstreamStatus,
    WorkstreamType,
)
from archium.domain.knowledge_gap import (
    Assumption,
    ClarifyingQuestion,
    DesignQuestion,
    KnowledgeGap,
)
from archium.domain.project_mission import (
    EvaluationCriterion,
    MissionConstraint,
    ProjectMission,
    Stakeholder,
)
from archium.domain.workstream import (
    Workstream,
    WorkstreamPlan,
    detect_workstream_dependency_cycles,
)
from pydantic import ValidationError

PROJECT_ID = uuid4()
MISSION_ID = uuid4()


def _mission(**overrides: object) -> ProjectMission:
    defaults: dict = {
        "project_id": PROJECT_ID,
        "title": "清凉寺重建前期策划",
        "task_statement": "在历史语境下形成宗教建筑重建的前期策划与概念汇报",
        "task_natures": [TaskNature.RECONSTRUCTION, TaskNature.RESEARCH],
        "intervention_scales": [InterventionScale.SITE, InterventionScale.BUILDING],
        "requested_service_depths": [ServiceDepth.CONCEPT_PLANNING, ServiceDepth.PRELIMINARY_RESEARCH],
        "in_scope": ["前期策划", "案例研究", "概念汇报"],
        "out_of_scope": ["施工图设计"],
        "primary_problems": ["历史形制不确定", "建设规模未知"],
        "uncertainty_level": UncertaintyLevel.HIGH,
        "confidence": 0.4,
    }
    defaults.update(overrides)
    return ProjectMission(**defaults)  # type: ignore[arg-type]


class TestProjectMission:
    def test_create_mission(self) -> None:
        mission = _mission()
        assert mission.version == 1
        assert mission.approval_status == ApprovalStatus.DRAFT
        assert mission.logical_key == "project-mission"
        assert TaskNature.RECONSTRUCTION in mission.task_natures

    def test_task_nature_deduplication(self) -> None:
        mission = _mission(
            task_natures=[
                TaskNature.RESEARCH,
                TaskNature.RESEARCH,
                TaskNature.PLANNING,
            ]
        )
        assert mission.task_natures == [TaskNature.RESEARCH, TaskNature.PLANNING]

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError, match="confidence"):
            _mission(confidence=1.5)

    def test_scope_lists(self) -> None:
        mission = _mission()
        assert "施工图设计" in mission.out_of_scope
        assert "前期策划" in mission.in_scope

    def test_approve_and_reject(self) -> None:
        mission = _mission()
        mission.approve()
        assert mission.approval_status == ApprovalStatus.APPROVED
        mission.reject()
        assert mission.approval_status == ApprovalStatus.REJECTED

    def test_stakeholder_and_constraint(self) -> None:
        mission = _mission(
            stakeholders=[
                Stakeholder(name="甲方", role="业主", concerns=["宗教功能", "建设规模"]),
            ],
            known_constraints=[
                MissionConstraint(name="资料条件", value="仅有地方志与现场照片", importance="high"),
            ],
            evaluation_criteria=[
                EvaluationCriterion(
                    name="历史可信度",
                    description="重建策略应基于可验证的历史依据",
                    weight=0.3,
                ),
            ],
        )
        assert mission.stakeholders[0].name == "甲方"
        assert mission.known_constraints[0].name == "资料条件"

    def test_serialization_roundtrip(self) -> None:
        mission = _mission()
        data = model_to_dict(mission)
        restored = ProjectMission.model_validate(data)
        assert restored.task_statement == mission.task_statement
        assert restored.id == mission.id


class TestKnowledgeGap:
    def test_create_gap(self) -> None:
        from archium.domain.enums import KnowledgeGapCategory

        gap = KnowledgeGap(
            project_id=PROJECT_ID,
            mission_id=MISSION_ID,
            category=KnowledgeGapCategory.AREA,
            question="建设规模是多少？",
            why_it_matters="影响功能配置与造价估算",
            blocking=False,
            priority=Priority.HIGH,
        )
        assert gap.status == KnowledgeGapStatus.OPEN

    def test_mark_assumed(self) -> None:
        gap = KnowledgeGap(
            project_id=PROJECT_ID,
            mission_id=MISSION_ID,
            question="用地范围？",
            why_it_matters="影响总图策略",
        )
        gap.mark_assumed("暂按现有寺庙旧址范围")
        assert gap.status == KnowledgeGapStatus.ASSUMED
        assert gap.resolution == "暂按现有寺庙旧址范围"

    def test_mark_answered(self) -> None:
        gap = KnowledgeGap(
            project_id=PROJECT_ID,
            mission_id=MISSION_ID,
            question="宗教功能？",
            why_it_matters="影响空间配置",
        )
        gap.mark_answered("礼佛与公共文化活动")
        assert gap.status == KnowledgeGapStatus.ANSWERED


class TestAssumption:
    def test_lifecycle(self) -> None:
        assumption = Assumption(
            project_id=PROJECT_ID,
            mission_id=MISSION_ID,
            statement="建设规模暂按同类寺庙中等规模估算",
            reason="甲方尚未提供面积指标",
            requires_confirmation=True,
        )
        assert assumption.status == AssumptionStatus.PROPOSED
        assumption.accept()
        assert assumption.status == AssumptionStatus.ACCEPTED
        assumption.confirm()
        assert assumption.status == AssumptionStatus.CONFIRMED

    def test_reject(self) -> None:
        assumption = Assumption(
            project_id=PROJECT_ID,
            mission_id=MISSION_ID,
            statement="测试假设",
            reason="测试",
        )
        assumption.reject()
        assert assumption.status == AssumptionStatus.REJECTED


class TestClarifyingQuestion:
    def test_answer_and_assume(self) -> None:
        question = ClarifyingQuestion(
            project_id=PROJECT_ID,
            mission_id=MISSION_ID,
            question="更倾向历史复原还是当代表达？",
            why_asked="影响重建策略方向",
            blocking=False,
            can_assume=True,
            suggested_assumption="传统语汇新建",
        )
        question.assume()
        assert question.status == QuestionStatus.ASSUMED
        assert question.answer == "传统语汇新建"

    def test_choice_requires_options(self) -> None:
        with pytest.raises(ValidationError, match="choice questions require"):
            ClarifyingQuestion(
                project_id=PROJECT_ID,
                mission_id=MISSION_ID,
                question="选择方向",
                why_asked="测试",
                answer_type=QuestionAnswerType.SINGLE_CHOICE,
                options=[],
            )

    def test_answer_with_text(self) -> None:
        question = ClarifyingQuestion(
            project_id=PROJECT_ID,
            mission_id=MISSION_ID,
            question="是否有明确用地边界？",
            why_asked="影响总图范围",
        )
        question.answer_with("已有红线范围")
        assert question.status == QuestionStatus.ANSWERED


class TestDesignQuestion:
    def test_create_design_question(self) -> None:
        dq = DesignQuestion(
            project_id=PROJECT_ID,
            mission_id=MISSION_ID,
            question="如何在不停诊和用地紧张条件下改善患者体验？",
            context="既有医院门诊楼",
            related_problem="就医焦虑与拥堵",
            constraints=["不停诊", "用地紧张"],
            desired_outcome="降低焦虑、迷失和拥堵",
        )
        dq.approve()
        assert dq.status == ApprovalStatus.APPROVED


class TestWorkstream:
    def _workstream(self, **overrides: object) -> Workstream:
        defaults: dict = {
            "project_id": PROJECT_ID,
            "mission_id": MISSION_ID,
            "title": "历史研究",
            "workstream_type": WorkstreamType.HISTORICAL_RESEARCH,
            "objective": "梳理清凉寺历史沿革与形制依据",
            "recommended": True,
        }
        defaults.update(overrides)
        return Workstream(**defaults)  # type: ignore[arg-type]

    def test_select_and_deselect(self) -> None:
        ws = self._workstream()
        ws.select()
        assert ws.selected
        assert ws.status == WorkstreamStatus.SELECTED
        ws.deselect()
        assert not ws.selected
        assert ws.status == WorkstreamStatus.PROPOSED

    def test_dependency_cycle_detection(self) -> None:
        ws_a = self._workstream(title="A")
        ws_b = self._workstream(title="B", dependencies=[ws_a.id])
        ws_a = ws_a.model_copy(update={"dependencies": [ws_b.id]})
        cycles = detect_workstream_dependency_cycles([ws_a, ws_b])
        assert ws_a.id in cycles or ws_b.id in cycles

    def test_workstream_plan_rejects_cycles(self) -> None:
        ws_a = self._workstream(title="A")
        ws_b = self._workstream(title="B", dependencies=[ws_a.id])
        ws_a = ws_a.model_copy(update={"dependencies": [ws_b.id]})
        with pytest.raises(ValidationError, match="cycle"):
            WorkstreamPlan(
                project_id=PROJECT_ID,
                mission_id=MISSION_ID,
                workstreams=[ws_a, ws_b],
            )

    def test_acyclic_plan_valid(self) -> None:
        ws_a = self._workstream(title="历史研究")
        ws_b = self._workstream(title="案例分析", dependencies=[ws_a.id])
        plan = WorkstreamPlan(
            project_id=PROJECT_ID,
            mission_id=MISSION_ID,
            workstreams=[ws_a, ws_b],
        )
        assert len(plan.workstreams) == 2


class TestDeliverablePlan:
    def test_create_and_select(self) -> None:
        plan = DeliverablePlan(
            project_id=PROJECT_ID,
            mission_id=MISSION_ID,
            deliverables=[
                PlannedDeliverable(
                    id="del-concept-ppt",
                    title="概念设计汇报",
                    deliverable_type=DeliverableType.PRESENTATION,
                    purpose="向甲方汇报重建策略",
                    audience="甲方",
                    required=True,
                    selected=True,
                ),
                PlannedDeliverable(
                    id="del-case-study",
                    title="案例研究",
                    deliverable_type=DeliverableType.CASE_STUDY,
                    purpose="提供重建策略参考",
                    required=False,
                ),
            ],
        )
        selected = plan.selected_deliverables()
        assert len(selected) == 1
        assert selected[0].title == "概念设计汇报"

    def test_approve(self) -> None:
        plan = DeliverablePlan(project_id=PROJECT_ID, mission_id=MISSION_ID)
        plan.approve()
        assert plan.approval_status == ApprovalStatus.APPROVED


class TestPlanningJsonSerialization:
    @pytest.mark.parametrize(
        "model",
        [
            _mission(),
            KnowledgeGap(
                project_id=PROJECT_ID,
                mission_id=MISSION_ID,
                question="测试",
                why_it_matters="原因",
            ),
            Workstream(
                project_id=PROJECT_ID,
                mission_id=MISSION_ID,
                title="测试",
                objective="目标",
            ),
            DeliverablePlan(project_id=PROJECT_ID, mission_id=MISSION_ID),
        ],
    )
    def test_json_roundtrip(self, model: object) -> None:
        from pydantic import BaseModel

        assert isinstance(model, BaseModel)
        json_str = json.dumps(model.model_dump(mode="json"))
        restored = type(model).model_validate(json.loads(json_str))
        assert restored.model_dump() == model.model_dump()

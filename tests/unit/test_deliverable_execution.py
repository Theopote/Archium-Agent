"""Tests for DeliverableExecutionRouter — no silent PPT fallback."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.deliverable_execution import (
    SUPPORTED_GENERATION_MESSAGE,
    UNSUPPORTED_GENERATION_MESSAGE,
    DeliverableExecutionRouter,
    supports_auto_generation,
)
from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import DeliverableType, TaskNature
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError


def _mission() -> ProjectMission:
    return ProjectMission(
        project_id=uuid4(),
        title="绿色低碳专项",
        task_statement="形成绿色低碳专项建议，不是完整建筑设计",
        task_natures=[TaskNature.RESEARCH],
        out_of_scope=["施工图", "设备选型"],
    )


def test_router_presentation_is_supported() -> None:
    mission = _mission()
    deliverable = PlannedDeliverable(
        id="del-ppt",
        title="概念汇报",
        deliverable_type=DeliverableType.PRESENTATION,
        purpose="汇报",
        selected=True,
    )
    plan = DeliverableExecutionRouter().route(mission, deliverable)
    assert plan.supported is True
    assert plan.request_kind == "presentation"
    assert plan.presentation_request is not None
    assert plan.presentation_request.title == "概念汇报"


def test_router_report_is_supported() -> None:
    mission = _mission()
    deliverable = PlannedDeliverable(
        id="del-report",
        title="绿色低碳专项建议报告",
        deliverable_type=DeliverableType.REPORT,
        purpose="专项建议",
        content_scope=["目标", "技术"],
        selected=True,
    )
    plan = DeliverableExecutionRouter().route(mission, deliverable)
    assert plan.supported is True
    assert plan.request_kind == "report"
    assert plan.presentation_request is None
    assert plan.report_request is not None
    assert plan.report_request.title == "绿色低碳专项建议报告"
    assert plan.message == SUPPORTED_GENERATION_MESSAGE


@pytest.mark.parametrize(
    ("dtype", "kind", "attr"),
    [
        (DeliverableType.MEMO, "memo", "memo_request"),
        (DeliverableType.CHECKLIST, "checklist", "checklist_request"),
        (DeliverableType.CASE_STUDY, "case_study", "case_study_request"),
    ],
)
def test_router_text_artifacts_are_supported(
    dtype: DeliverableType,
    kind: str,
    attr: str,
) -> None:
    mission = _mission()
    deliverable = PlannedDeliverable(
        id=f"del-{kind}",
        title=f"测试{kind}",
        deliverable_type=dtype,
        purpose="测试",
        selected=True,
    )
    plan = DeliverableExecutionRouter().route(mission, deliverable)
    assert plan.supported is True
    assert plan.request_kind == kind
    assert getattr(plan, attr) is not None
    assert plan.message == SUPPORTED_GENERATION_MESSAGE


def test_router_risk_register_remains_unsupported() -> None:
    mission = _mission()
    deliverable = PlannedDeliverable(
        id="del-risk",
        title="风险登记",
        deliverable_type=DeliverableType.RISK_REGISTER,
        purpose="风险",
        selected=True,
    )
    plan = DeliverableExecutionRouter().route(mission, deliverable)
    assert plan.supported is False
    assert plan.message == UNSUPPORTED_GENERATION_MESSAGE


def test_router_question_list_is_supported() -> None:
    mission = _mission()
    deliverable = PlannedDeliverable(
        id="del-ql",
        title="待澄清问题清单",
        deliverable_type=DeliverableType.QUESTION_LIST,
        purpose="汇总待问项",
        selected=True,
    )
    plan = DeliverableExecutionRouter().route(mission, deliverable)
    assert plan.supported is True
    assert plan.request_kind == "question_list"
    assert plan.question_list_request is not None
    assert plan.checklist_request is None


def test_router_work_plan_is_supported() -> None:
    mission = _mission()
    deliverable = PlannedDeliverable(
        id="del-wp",
        title="项目工作大纲",
        deliverable_type=DeliverableType.WORK_PLAN,
        purpose="工作路径",
        selected=True,
    )
    plan = DeliverableExecutionRouter().route(mission, deliverable)
    assert plan.supported is True
    assert plan.request_kind == "work_plan"
    assert plan.work_plan_request is not None


def test_require_presentation_rejects_report_only_plan() -> None:
    mission = _mission()
    plan = DeliverablePlan(
        project_id=mission.project_id,
        mission_id=mission.id,
        deliverables=[
            PlannedDeliverable(
                id="del-report",
                title="专项报告",
                deliverable_type=DeliverableType.REPORT,
                purpose="报告",
                selected=True,
            )
        ],
    )
    with pytest.raises(WorkflowError, match="不会自动转换成 PresentationRequest"):
        DeliverableExecutionRouter().require_presentation_plan(mission, plan)


def test_route_plan_mixed_selection() -> None:
    mission = _mission()
    plan = DeliverablePlan(
        project_id=mission.project_id,
        mission_id=mission.id,
        deliverables=[
            PlannedDeliverable(
                id="del-report",
                title="专项报告",
                deliverable_type=DeliverableType.REPORT,
                purpose="报告",
                selected=True,
            ),
            PlannedDeliverable(
                id="del-ppt",
                title="概念汇报",
                deliverable_type=DeliverableType.PRESENTATION,
                purpose="汇报",
                selected=True,
            ),
            PlannedDeliverable(
                id="del-memo",
                title="决策备忘",
                deliverable_type=DeliverableType.MEMO,
                purpose="备忘",
                selected=False,
            ),
        ],
    )
    routed = DeliverableExecutionRouter().route_plan(mission, plan)
    assert len(routed) == 2
    by_id = {item.deliverable_id: item for item in routed}
    assert by_id["del-report"].supported is True
    assert by_id["del-report"].report_request is not None
    assert by_id["del-ppt"].supported is True
    assert "del-memo" not in by_id


@pytest.mark.parametrize(
    ("dtype", "expected"),
    [
        (DeliverableType.PRESENTATION, True),
        (DeliverableType.QUESTION_LIST, True),
        (DeliverableType.WORK_PLAN, True),
        (DeliverableType.IMPLEMENTATION_ROADMAP, True),
        (DeliverableType.REPORT, True),
        (DeliverableType.TECHNICAL_PROPOSAL, True),
        (DeliverableType.MEMO, True),
        (DeliverableType.CHECKLIST, True),
        (DeliverableType.CASE_STUDY, True),
        (DeliverableType.RISK_REGISTER, False),
        (DeliverableType.OTHER, False),
    ],
)
def test_supports_auto_generation(dtype: DeliverableType, expected: bool) -> None:
    assert supports_auto_generation(dtype) is expected

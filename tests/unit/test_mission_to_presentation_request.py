"""Tests for mission → PresentationRequest adapter."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.mission_to_presentation_request import (
    PresentationOverrides,
    bridge_from_draft,
    build_presentation_bridge,
    build_presentation_request,
    infer_presentation_type,
    select_presentation_deliverable,
)
from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import (
    DeliverableType,
    PresentationType,
    ServiceDepth,
    TaskNature,
    WorkstreamType,
)
from archium.domain.project_mission import ProjectMission, Stakeholder
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError


def _temple_mission() -> ProjectMission:
    return ProjectMission(
        project_id=uuid4(),
        title="清凉寺重建前期策划",
        task_statement="形成宗教建筑重建的前期策划、案例研究与概念设计汇报",
        task_natures=[TaskNature.RECONSTRUCTION, TaskNature.RESEARCH],
        requested_service_depths=[
            ServiceDepth.PRELIMINARY_RESEARCH,
            ServiceDepth.CONCEPT_PLANNING,
            ServiceDepth.PRESENTATION_PRODUCTION,
        ],
        desired_changes=["形成前期策划", "完成案例研究"],
        in_scope=["前期策划", "案例研究", "概念设计汇报"],
        out_of_scope=["施工图设计", "施工招标"],
        stakeholders=[
            Stakeholder(name="甲方", role="业主", concerns=["宗教功能", "文化定位"]),
        ],
        decisions_required=["重建策略取向", "主要宗教与公共功能"],
        design_questions=["如何在历史资料有限条件下形成可接受的重建策略？"],
        research_questions=["历史形制有哪些可信依据？"],
        key_unknowns=["建设规模"],
        decision_context="需确定重建策略与概念方向",
    )


def _presentation_deliverable() -> PlannedDeliverable:
    return PlannedDeliverable(
        id="del-concept-ppt",
        title="概念设计汇报",
        deliverable_type=DeliverableType.PRESENTATION,
        purpose="向甲方汇报重建策略与概念方向",
        audience="甲方",
        content_scope=["现状", "策略", "概念"],
        required=True,
        selected=True,
        expected_length="12-16页",
    )


def _workstreams(mission_id, project_id) -> list[Workstream]:
    return [
        Workstream(
            project_id=project_id,
            mission_id=mission_id,
            title="历史与案例研究",
            workstream_type=WorkstreamType.HISTORICAL_RESEARCH,
            objective="梳理形制依据与同类策略",
            selected=True,
        ),
        Workstream(
            project_id=project_id,
            mission_id=mission_id,
            title="概念生成",
            workstream_type=WorkstreamType.DESIGN_STRATEGY,
            objective="形成概念方向比较",
            selected=True,
        ),
        Workstream(
            project_id=project_id,
            mission_id=mission_id,
            title="施工图准备",
            workstream_type=WorkstreamType.OTHER,
            objective="不在本轮",
            selected=False,
        ),
    ]


def test_build_presentation_request_includes_project_context_in_user_notes() -> None:
    mission = _temple_mission()
    mission.project_context = "【已确认公开研究】\n- 关中乡村公共文化空间"

    request = build_presentation_request(mission)

    assert "项目语境:" in request.user_notes
    assert "关中乡村" in request.user_notes


def test_build_presentation_request_includes_concept_direction() -> None:
    from archium.domain.concept_direction import ConceptDirection
    from archium.domain.enums import ConceptDirectionStatus

    mission = _temple_mission()
    direction = ConceptDirection(
        project_id=mission.project_id,
        mission_id=mission.id,
        title="窑洞再生",
        summary="以窑洞原型转译公共空间",
        theme="窑洞当代化",
        experience_focus="庇护与仪式感",
        spatial_idea="半地下拱廊",
        status=ConceptDirectionStatus.SELECTED,
    )

    request = build_presentation_request(mission, concept_direction=direction)

    assert request.core_message == "庇护与仪式感"
    assert request.purpose == "以窑洞原型转译公共空间"
    assert "当前概念方向:" in request.user_notes
    assert "窑洞再生" in request.user_notes
    assert "半地下拱廊" in request.user_notes


def test_build_presentation_request_includes_visual_concept_brief() -> None:
    from archium.domain.concept_direction import ConceptDirection
    from archium.domain.enums import ConceptDirectionStatus
    from archium.domain.visual.vision_generation import ArchitectureImageType
    from archium.domain.visual.visual_concept_brief import VisualConceptBrief

    mission = _temple_mission()
    direction = ConceptDirection(
        project_id=mission.project_id,
        mission_id=mission.id,
        title="窑洞再生",
        summary="以窑洞原型转译公共空间",
        status=ConceptDirectionStatus.SELECTED,
    )
    brief = VisualConceptBrief(
        project_id=mission.project_id,
        mission_id=mission.id,
        concept_direction_id=direction.id,
        title="窑洞氛围示意",
        composition_intent="侧光穿过拱廊",
        atmosphere="温润黄土",
        image_type=ArchitectureImageType.ATMOSPHERE_IMAGE,
        subject="拱廊氛围",
        status="ready",
    )

    request = build_presentation_request(
        mission,
        concept_direction=direction,
        visual_concept_brief=brief,
    )

    assert "当前概念方向:" in request.user_notes
    assert "视觉概念简报:" in request.user_notes
    assert "窑洞氛围示意" in request.user_notes
    assert "侧光穿过拱廊" in request.user_notes


def test_build_presentation_request_field_mapping() -> None:
    mission = _temple_mission()
    deliverable = _presentation_deliverable()
    workstreams = _workstreams(mission.id, mission.project_id)

    request = build_presentation_request(mission, deliverable, workstreams=workstreams)

    assert request.title == "概念设计汇报"
    assert request.audience == "甲方"
    assert request.purpose == mission.task_statement
    assert request.core_message == "形成前期策划"
    assert request.decisions_required == mission.decisions_required
    assert request.audience_concerns == ["宗教功能", "文化定位"]
    assert request.required_sections == ["现状", "策略", "概念"]
    assert request.excluded_topics == ["施工图设计", "施工招标"]
    assert request.target_slide_count == 14
    assert request.presentation_type == PresentationType.CONCEPT
    assert "设计命题" in request.user_notes
    assert "相关工作路径（生成上下文，非汇报章节大纲）" in request.user_notes
    assert "历史与案例研究" in request.user_notes
    assert "施工图准备" not in request.user_notes
    mission.project_context = "【已确认公开研究】\n- 关中乡村公共文化空间"
    request_with_context = build_presentation_request(mission, deliverable, workstreams=workstreams)
    assert "项目语境" in request_with_context.user_notes
    assert "关中乡村" in request_with_context.user_notes
    # Workstream titles must not become required_sections.
    assert "历史与案例研究" not in request.required_sections
    assert "概念生成" not in request.required_sections


def test_workstream_names_are_not_mechanical_sections() -> None:
    mission = _temple_mission()
    workstreams = _workstreams(mission.id, mission.project_id)
    request = build_presentation_request(mission, workstreams=workstreams)
    assert request.required_sections == mission.in_scope
    for ws in workstreams:
        assert ws.title not in request.required_sections


def test_user_overrides_win() -> None:
    mission = _temple_mission()
    request = build_presentation_request(
        mission,
        _presentation_deliverable(),
        user_overrides=PresentationOverrides(
            title="自定义标题",
            audience="专家评审",
            target_slide_count=10,
            presentation_type=PresentationType.COMPETITION,
        ),
    )
    assert request.title == "自定义标题"
    assert request.audience == "专家评审"
    assert request.target_slide_count == 10
    assert request.presentation_type == PresentationType.COMPETITION


def test_select_presentation_deliverable_prefers_presentation_type() -> None:
    mission = _temple_mission()
    plan = DeliverablePlan(
        project_id=mission.project_id,
        mission_id=mission.id,
        deliverables=[
            PlannedDeliverable(
                id="del-report",
                title="研究报告",
                deliverable_type=DeliverableType.REPORT,
                purpose="研究",
                selected=True,
            ),
            _presentation_deliverable(),
        ],
    )
    selected, warnings = select_presentation_deliverable(plan)
    assert selected is not None
    assert selected.id == "del-concept-ppt"
    assert warnings == []


def test_select_presentation_deliverable_does_not_fall_back_to_report() -> None:
    mission = _temple_mission()
    plan = DeliverablePlan(
        project_id=mission.project_id,
        mission_id=mission.id,
        deliverables=[
            PlannedDeliverable(
                id="del-report",
                title="绿色低碳专项建议报告",
                deliverable_type=DeliverableType.REPORT,
                purpose="专项建议",
                selected=True,
            ),
        ],
    )
    selected, warnings = select_presentation_deliverable(plan)
    assert selected is None
    assert warnings == []


def test_bridge_rejects_report_only_plan() -> None:
    mission = _temple_mission()
    plan = DeliverablePlan(
        project_id=mission.project_id,
        mission_id=mission.id,
        deliverables=[
            PlannedDeliverable(
                id="del-report",
                title="绿色低碳专项建议报告",
                deliverable_type=DeliverableType.REPORT,
                purpose="专项建议",
                selected=True,
            ),
        ],
    )
    with pytest.raises(WorkflowError, match="不会自动转换成 PresentationRequest"):
        build_presentation_bridge(mission, plan=plan)


def test_build_presentation_request_rejects_non_presentation_deliverable() -> None:
    mission = _temple_mission()
    report = PlannedDeliverable(
        id="del-report",
        title="专项报告",
        deliverable_type=DeliverableType.REPORT,
        purpose="报告",
        selected=True,
    )
    with pytest.raises(WorkflowError, match="不能构建 PresentationRequest"):
        build_presentation_request(mission, report)


def test_bridge_roundtrip_draft() -> None:
    mission = _temple_mission()
    plan = DeliverablePlan(
        project_id=mission.project_id,
        mission_id=mission.id,
        deliverables=[_presentation_deliverable()],
    )
    bridge = build_presentation_bridge(
        mission,
        plan=plan,
        workstreams=_workstreams(mission.id, mission.project_id),
    )
    restored = bridge_from_draft(bridge.to_draft())
    assert restored.mission_id == mission.id
    assert restored.deliverable_id == "del-concept-ppt"
    assert restored.request.title == bridge.request.title
    assert restored.request.purpose == bridge.request.purpose
    assert restored.request.required_sections == bridge.request.required_sections


def test_select_unselected_deliverable_raises() -> None:
    mission = _temple_mission()
    item = _presentation_deliverable()
    item.selected = False
    plan = DeliverablePlan(
        project_id=mission.project_id,
        mission_id=mission.id,
        deliverables=[item],
    )
    with pytest.raises(WorkflowError, match="未选中"):
        select_presentation_deliverable(plan, deliverable_id="del-concept-ppt")


def test_infer_presentation_type_defaults() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="日常汇报",
        task_statement="确认方向",
    )
    assert infer_presentation_type(mission) == PresentationType.CLIENT_REVIEW


def test_infer_presentation_type_concept_from_design_intent() -> None:
    from archium.domain.intent.design_intent import DesignIntent

    mission = ProjectMission(
        project_id=uuid4(),
        title="黄土高原文化中心",
        task_statement="探索地域文化再生",
        design_intent=DesignIntent(
            theme="地域文化再生",
            problem_statement="如何在缺乏任务书时建立设计方向？",
        ),
    )
    assert infer_presentation_type(mission) == PresentationType.CONCEPT

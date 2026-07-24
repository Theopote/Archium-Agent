"""Unit tests for QuestionListExecutor, WorkPlanExecutor, and text artifact executors."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.artifact_executors import (
    CaseStudyExecutor,
    ChecklistExecutor,
    MemoExecutor,
    QuestionListExecutor,
    ReportExecutor,
    WorkPlanExecutor,
)
from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import (
    AssumptionStatus,
    DeliverableType,
    KnowledgeGapCategory,
    KnowledgeGapStatus,
    Priority,
    QuestionAnswerType,
    QuestionStatus,
    TaskNature,
    VerificationStatus,
    WorkstreamType,
)
from archium.domain.fact import ProjectFact
from archium.domain.knowledge_gap import Assumption, ClarifyingQuestion, KnowledgeGap
from archium.domain.project_mission import ProjectMission
from archium.domain.workstream import Workstream


def _mission() -> ProjectMission:
    return ProjectMission(
        project_id=uuid4(),
        title="专项诊断",
        task_statement="形成医院环境专项诊断建议",
        task_natures=[TaskNature.CONSULTING],
        in_scope=["诊断"],
        out_of_scope=["施工图"],
        decisions_required=["是否分期改造"],
        key_unknowns=["改造预算上限"],
        research_questions=["同类医院环境提升案例"],
        primary_problems=["候诊空间拥挤"],
    )


def test_question_list_reads_bundle_not_content_scope(tmp_path: Path) -> None:
    mission = _mission()
    gap = KnowledgeGap(
        project_id=mission.project_id,
        mission_id=mission.id,
        category=KnowledgeGapCategory.BUDGET,
        question="改造预算上限是多少？",
        why_it_matters="影响分期",
        blocking=True,
        priority=Priority.HIGH,
        status=KnowledgeGapStatus.OPEN,
    )
    question = ClarifyingQuestion(
        project_id=mission.project_id,
        mission_id=mission.id,
        question="是否允许夜间施工？",
        why_asked="影响工期",
        answer_type=QuestionAnswerType.BOOLEAN,
        priority=Priority.MEDIUM,
        blocking=False,
        status=QuestionStatus.OPEN,
    )
    assumption = Assumption(
        project_id=mission.project_id,
        mission_id=mission.id,
        statement="按不停诊改造推进",
        reason="业主口头倾向",
        requires_confirmation=True,
        status=AssumptionStatus.PROPOSED,
    )
    fact = ProjectFact(
        project_id=mission.project_id,
        key="building_area",
        label="建筑面积",
        value="未知冲突值",
        verification_status=VerificationStatus.CONFLICTED,
        conflict_group="area",
    )
    deliverable = PlannedDeliverable(
        id="del-ql",
        title="提问清单",
        deliverable_type=DeliverableType.QUESTION_LIST,
        purpose="澄清",
        content_scope=["这不该成为唯一来源"],
        selected=True,
    )
    output = QuestionListExecutor().execute(
        mission,
        gaps=[gap],
        questions=[question],
        assumptions=[assumption],
        facts=[fact],
        deliverable=deliverable,
        output_dir=tmp_path,
    )
    texts = [item["text"] for item in output.payload["items"]]
    assert any("改造预算" in text for text in texts)
    assert any("夜间施工" in text for text in texts)
    assert any("不停诊" in text for text in texts)
    assert any("事实冲突" in text for text in texts)
    assert any("分期改造" in text for text in texts)
    assert "这不该成为唯一来源" not in texts
    assert "阻塞项" in output.markdown
    assert output.payload["formats"] == ["json", "markdown", "docx"]
    assert output.json_path is not None and output.json_path.exists()
    assert output.markdown_path is not None and output.markdown_path.exists()
    assert output.docx_path is not None and output.docx_path.exists()
    assert output.docx_path.suffix == ".docx"
    from docx import Document as DocumentFactory

    doc = DocumentFactory(str(output.docx_path))
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    assert "提问清单" in text or "改造预算" in text
    assert "阻塞项" in text
    assert "改造预算上限是多少？" in text


def test_work_plan_from_workstreams(tmp_path: Path) -> None:
    mission = _mission()
    ws = Workstream(
        project_id=mission.project_id,
        mission_id=mission.id,
        title="现状诊断",
        workstream_type=WorkstreamType.SITE_ANALYSIS,
        objective="摸清现状问题",
        inputs_required=["现场照片"],
        activities=["走访", "问题清单"],
        outputs=["诊断纪要"],
        selected=True,
        recommended=True,
    )
    plan = DeliverablePlan(
        project_id=mission.project_id,
        mission_id=mission.id,
        deliverables=[
            PlannedDeliverable(
                id="del-wp",
                title="工作大纲",
                deliverable_type=DeliverableType.WORK_PLAN,
                purpose="执行",
                selected=True,
            )
        ],
    )
    output = WorkPlanExecutor().execute(
        mission,
        workstreams=[ws],
        deliverable_plan=plan,
        deliverable=plan.deliverables[0],
        output_dir=tmp_path,
    )
    assert output.payload["workstreams"][0]["title"] == "现状诊断"
    assert "走访" in output.markdown
    assert "诊断纪要" in output.markdown
    assert output.json_path is not None and output.json_path.exists()


def test_report_executor_uses_content_scope(tmp_path: Path) -> None:
    mission = _mission()
    deliverable = PlannedDeliverable(
        id="del-report",
        title="专项诊断报告",
        deliverable_type=DeliverableType.REPORT,
        purpose="形成可讨论建议",
        audience="院方",
        content_scope=["问题诊断", "改造策略"],
        selected=True,
    )
    output = ReportExecutor().execute(mission, deliverable=deliverable, output_dir=tmp_path)
    assert output.payload["sections"] == ["问题诊断", "改造策略"]
    assert "问题诊断" in output.markdown
    assert "是否分期改造" in output.markdown
    assert output.markdown_path is not None and output.markdown_path.exists()


def test_memo_executor_highlights_mission_problems(tmp_path: Path) -> None:
    mission = _mission()
    output = MemoExecutor().execute(mission, output_dir=tmp_path)
    assert "候诊空间拥挤" in output.markdown
    assert "是否分期改造" in output.markdown
    assert output.payload["kind"] == "memo"
    assert output.json_path is not None and output.json_path.exists()


def test_checklist_executor_falls_back_to_decisions(tmp_path: Path) -> None:
    mission = _mission()
    output = ChecklistExecutor().execute(mission, output_dir=tmp_path)
    assert output.payload["item_count"] == 1
    assert "- [ ] 是否分期改造" in output.markdown


def test_case_study_executor_includes_research_questions(tmp_path: Path) -> None:
    mission = _mission()
    deliverable = PlannedDeliverable(
        id="del-cs",
        title="环境提升案例研究",
        deliverable_type=DeliverableType.CASE_STUDY,
        purpose="借鉴",
        content_scope=["空间组织"],
        selected=True,
    )
    output = CaseStudyExecutor().execute(mission, deliverable=deliverable, output_dir=tmp_path)
    assert "同类医院环境提升案例" in output.markdown
    assert "空间组织" in output.markdown
    assert output.payload["kind"] == "case_study"

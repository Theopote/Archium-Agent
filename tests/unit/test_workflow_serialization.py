"""Unit tests for workflow state serialization."""

from __future__ import annotations

from uuid import uuid4

from archium.application.presentation_models import PresentationRequest
from archium.domain.enums import (
    PresentationType,
    ReviewCategory,
    ReviewLayer,
    ReviewSeverity,
    WorkflowStep,
)
from archium.domain.presentation import Presentation
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.workflow.serialization import (
    request_from_dict,
    request_to_dict,
    restore_domain_artifacts,
    snapshot_state,
)
from archium.workflow.state import initial_workflow_state


def test_request_round_trip() -> None:
    request = PresentationRequest(
        title="概念汇报",
        audience="甲方",
        purpose="决策",
        core_message="核心信息",
        presentation_type=PresentationType.CLIENT_REVIEW,
        required_sections=["现状分析"],
    )
    restored = request_from_dict(request_to_dict(request))
    assert restored.title == request.title
    assert restored.presentation_type == request.presentation_type
    assert restored.required_sections == request.required_sections


def test_snapshot_state_is_json_safe() -> None:
    project_id = uuid4()
    presentation_id = uuid4()
    workflow_run_id = uuid4()
    request = PresentationRequest(
        title="概念汇报",
        audience="甲方",
        purpose="决策",
        core_message="核心信息",
    )
    presentation = Presentation(project_id=project_id, title=request.title)
    state = initial_workflow_state(
        project_id=str(project_id),
        presentation_id=str(presentation_id),
        workflow_run_id=str(workflow_run_id),
        request=request,
        presentation=presentation,
        export_json=True,
    )
    snapshot = snapshot_state(state)
    assert snapshot["current_step"] == WorkflowStep.INIT.value
    assert snapshot["request"]["title"] == "概念汇报"
    assert snapshot["presentation"]["title"] == "概念汇报"


def test_restore_domain_artifacts_from_snapshot() -> None:
    project_id = uuid4()
    presentation_id = uuid4()
    request = PresentationRequest(
        title="概念汇报",
        audience="甲方",
        purpose="决策",
        core_message="核心信息",
    )
    presentation = Presentation(
        id=presentation_id,
        project_id=project_id,
        title=request.title,
    )
    snapshot = {
        "request": request_to_dict(request),
        "presentation": presentation.model_dump(mode="json"),
    }
    restored = restore_domain_artifacts(snapshot)
    assert restored["request"].title == "概念汇报"
    assert restored["presentation"].id == presentation_id


def test_restore_domain_artifacts_infers_rule_code_for_legacy_review_issues() -> None:
    presentation_id = uuid4()
    legacy_issue = {
        "id": str(uuid4()),
        "presentation_id": str(presentation_id),
        "reviewer_layer": "evidence",
        "category": "citation",
        "severity": "medium",
        "title": "缺少引用来源",
        "description": "第 2 页未关联项目资料。",
        "status": "open",
        "auto_fixable": False,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    restored = restore_domain_artifacts({"review_issues": [legacy_issue]})
    issues = restored["review_issues"]
    assert len(issues) == 1
    assert isinstance(issues[0], ReviewIssue)
    assert issues[0].rule_code == ReviewRuleCode.EVIDENCE_MISSING_CITATION


def test_snapshot_state_round_trips_review_issue_rule_code() -> None:
    project_id = uuid4()
    presentation_id = uuid4()
    workflow_run_id = uuid4()
    request = PresentationRequest(
        title="概念汇报",
        audience="甲方",
        purpose="决策",
        core_message="核心信息",
    )
    presentation = Presentation(project_id=project_id, title=request.title)
    issue = ReviewIssue(
        presentation_id=presentation_id,
        reviewer_layer=ReviewLayer.EVIDENCE,
        category=ReviewCategory.CITATION,
        severity=ReviewSeverity.MEDIUM,
        rule_code=ReviewRuleCode.EVIDENCE_MISSING_CITATION,
        title="缺少引用来源",
        description="第 2 页未关联项目资料。",
    )
    state = initial_workflow_state(
        project_id=str(project_id),
        presentation_id=str(presentation_id),
        workflow_run_id=str(workflow_run_id),
        request=request,
        presentation=presentation,
        export_json=True,
    )
    state["review_issues"] = [issue]

    snapshot = snapshot_state(state)
    restored = restore_domain_artifacts(snapshot)
    restored_issues = restored["review_issues"]
    assert len(restored_issues) == 1
    assert restored_issues[0].rule_code == ReviewRuleCode.EVIDENCE_MISSING_CITATION

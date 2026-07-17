"""Unit tests for workflow state serialization."""

from __future__ import annotations

from uuid import uuid4

from archium.application.presentation_models import PresentationRequest
from archium.domain.enums import PresentationType, WorkflowStep
from archium.domain.presentation import Presentation
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

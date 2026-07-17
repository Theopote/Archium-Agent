"""Serialize workflow state for persistence."""

from __future__ import annotations

from typing import Any

from archium.application.presentation_models import PresentationRequest
from archium.domain.enums import WorkflowStep
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec
from archium.workflow.state import PresentationWorkflowState


def request_to_dict(request: PresentationRequest) -> dict[str, Any]:
    return {
        "title": request.title,
        "audience": request.audience,
        "purpose": request.purpose,
        "duration_minutes": request.duration_minutes,
        "target_slide_count": request.target_slide_count,
        "core_message": request.core_message,
        "presentation_type": request.presentation_type.value,
        "decisions_required": list(request.decisions_required),
        "audience_concerns": list(request.audience_concerns),
        "required_sections": list(request.required_sections),
        "excluded_topics": list(request.excluded_topics),
        "tone": request.tone,
        "language": request.language,
        "user_notes": request.user_notes,
    }


def request_from_dict(data: dict[str, Any]) -> PresentationRequest:
    from archium.domain.enums import PresentationType

    presentation_type = data.get("presentation_type", PresentationType.CLIENT_REVIEW)
    if isinstance(presentation_type, str):
        presentation_type = PresentationType(presentation_type)
    return PresentationRequest(
        title=str(data["title"]),
        audience=str(data["audience"]),
        purpose=str(data["purpose"]),
        duration_minutes=int(data.get("duration_minutes", 20)),
        target_slide_count=int(data.get("target_slide_count", 20)),
        core_message=str(data.get("core_message", "")),
        presentation_type=presentation_type,
        decisions_required=list(data.get("decisions_required", [])),
        audience_concerns=list(data.get("audience_concerns", [])),
        required_sections=list(data.get("required_sections", [])),
        excluded_topics=list(data.get("excluded_topics", [])),
        tone=str(data.get("tone", "professional")),
        language=str(data.get("language", "zh-CN")),
        user_notes=str(data.get("user_notes", "")),
    )


def snapshot_state(state: PresentationWorkflowState) -> dict[str, Any]:
    """Convert graph state to a JSON-safe checkpoint dict."""
    brief = state.get("brief")
    storyline = state.get("storyline")
    presentation = state.get("presentation")
    slides = state.get("slides", [])
    request = state.get("request")

    payload: dict[str, Any] = {
        "current_step": state.get("current_step", WorkflowStep.INIT.value),
        "project_id": state.get("project_id"),
        "presentation_id": state.get("presentation_id"),
        "workflow_run_id": state.get("workflow_run_id"),
        "export_json": state.get("export_json", True),
        "export_marp": state.get("export_marp", False),
        "export_pptx": state.get("export_pptx", False),
        "json_path": state.get("json_path"),
        "marp_md_path": state.get("marp_md_path"),
        "marp_pptx_path": state.get("marp_pptx_path"),
        "errors": list(state.get("errors", [])),
        "slide_count": len(slides),
    }
    if request is not None:
        payload["request"] = request_to_dict(request)
    if presentation is not None:
        payload["presentation"] = presentation.model_dump(mode="json")
    if brief is not None:
        payload["brief"] = brief.model_dump(mode="json")
    if storyline is not None:
        payload["storyline"] = storyline.model_dump(mode="json")
    if slides:
        payload["slides"] = [slide.model_dump(mode="json") for slide in slides]
    return payload


def restore_domain_artifacts(state_data: dict[str, Any]) -> dict[str, Any]:
    """Restore domain objects from a persisted checkpoint or graph state."""
    restored: dict[str, Any] = {}
    if "request" in state_data:
        request = state_data["request"]
        restored["request"] = request if isinstance(request, PresentationRequest) else request_from_dict(request)
    if "presentation" in state_data:
        presentation = state_data["presentation"]
        restored["presentation"] = (
            presentation
            if isinstance(presentation, Presentation)
            else Presentation.model_validate(presentation)
        )
    if "brief" in state_data:
        brief = state_data["brief"]
        restored["brief"] = (
            brief if isinstance(brief, PresentationBrief) else PresentationBrief.model_validate(brief)
        )
    if "storyline" in state_data:
        storyline = state_data["storyline"]
        restored["storyline"] = (
            storyline
            if isinstance(storyline, Storyline)
            else Storyline.model_validate(storyline)
        )
    if "slides" in state_data:
        slides = state_data["slides"]
        if not slides:
            restored["slides"] = []
        elif isinstance(slides[0], SlideSpec):
            restored["slides"] = list(slides)
        else:
            restored["slides"] = [SlideSpec.model_validate(item) for item in slides]
    return restored

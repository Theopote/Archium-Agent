"""Serialize workflow state for persistence."""

from __future__ import annotations

from typing import Any

from archium.application.presentation_models import PresentationRequest
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.enums import WorkflowStep
from archium.domain.fact import ProjectFact
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.reference_style import ReferenceStyleProfile
from archium.domain.renovation_issue import RenovationIssueMap
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec
from archium.workflow.state import PresentationWorkflowState


def _dump_artifact(value: Any) -> Any:
    """Serialize a domain artifact that may already be a plain dict."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


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
    cultural_narrative = state.get("cultural_narrative")
    renovation_issue_map = state.get("renovation_issue_map")
    reference_style_profile = state.get("reference_style_profile")
    storyline = state.get("storyline")
    outline = state.get("outline")
    presentation = state.get("presentation")
    slides = state.get("slides", [])
    request = state.get("request")

    payload: dict[str, Any] = {
        "current_step": state.get("current_step", WorkflowStep.INIT.value),
        "project_id": state.get("project_id"),
        "presentation_id": state.get("presentation_id"),
        "workflow_run_id": state.get("workflow_run_id"),
        "export_json": state.get("export_json", True),
        "export_presentation_spec": state.get("export_presentation_spec", False),
        "export_editable_pptx": state.get("export_editable_pptx", False),
        "export_marp": state.get("export_marp", False),
        "export_pptx": state.get("export_pptx", False),
        "export_pdf": state.get("export_pdf", False),
        "export_preview_images": state.get("export_preview_images", False),
        "require_brief_review": state.get("require_brief_review", False),
        "require_storyline_review": state.get("require_storyline_review", False),
        "require_outline_review": state.get("require_outline_review", True),
        "require_slides_review": state.get("require_slides_review", False),
        "review_gate": state.get("review_gate"),
        "source_document_count": state.get("source_document_count", 0),
        "source_chunk_count": state.get("source_chunk_count", 0),
        "source_validation_issues": list(state.get("source_validation_issues", [])),
        "extracted_fact_count": state.get("extracted_fact_count", 0),
        "fact_validation_issues": list(state.get("fact_validation_issues", [])),
        "fact_count": len(state.get("project_facts", [])),
        "json_path": state.get("json_path"),
        "spec_path": state.get("spec_path"),
        "editable_pptx_path": state.get("editable_pptx_path"),
        "marp_md_path": state.get("marp_md_path"),
        "marp_pptx_path": state.get("marp_pptx_path"),
        "pdf_path": state.get("pdf_path"),
        "preview_image_paths": list(state.get("preview_image_paths", [])),
        "render_warnings": list(state.get("render_warnings", [])),
        "errors": list(state.get("errors", [])),
        "slide_review_issues": list(state.get("slide_review_issues", [])),
        "matched_asset_count": state.get("matched_asset_count", 0),
        "repaired_slide_count": state.get("repaired_slide_count", 0),
        "repair_round": state.get("repair_round", 0),
        "review_issue_count": len(state.get("review_issues", [])),
        "slide_count": len(slides),
    }
    context_bundle = state.get("context_bundle")
    if context_bundle is not None:
        payload["context_chunk_count"] = len(context_bundle.chunks)
    if request is not None:
        payload["request"] = request_to_dict(request)
    if presentation is not None:
        payload["presentation"] = _dump_artifact(presentation)
    if brief is not None:
        payload["brief"] = _dump_artifact(brief)
    if cultural_narrative is not None:
        payload["cultural_narrative"] = _dump_artifact(cultural_narrative)
    if renovation_issue_map is not None:
        payload["renovation_issue_map"] = _dump_artifact(renovation_issue_map)
    if reference_style_profile is not None:
        payload["reference_style_profile"] = _dump_artifact(reference_style_profile)
    if storyline is not None:
        payload["storyline"] = _dump_artifact(storyline)
    if outline is not None:
        payload["outline"] = _dump_artifact(outline)
    if slides:
        payload["slides"] = [_dump_artifact(slide) for slide in slides]
    project_facts = state.get("project_facts", [])
    if project_facts:
        payload["project_facts"] = [
            fact.model_dump(mode="json") if isinstance(fact, ProjectFact) else fact
            for fact in project_facts
        ]
    review_issues = state.get("review_issues", [])
    if review_issues:
        payload["review_issues"] = [
            issue.model_dump(mode="json") if isinstance(issue, ReviewIssue) else issue
            for issue in review_issues
        ]
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
        if brief is not None:
            restored["brief"] = (
                brief if isinstance(brief, PresentationBrief) else PresentationBrief.model_validate(brief)
            )
    if "cultural_narrative" in state_data:
        narrative = state_data["cultural_narrative"]
        if narrative is not None:
            restored["cultural_narrative"] = (
                narrative
                if isinstance(narrative, CulturalNarrativePlan)
                else CulturalNarrativePlan.model_validate(narrative)
            )
    if "renovation_issue_map" in state_data:
        issue_map = state_data["renovation_issue_map"]
        if issue_map is not None:
            restored["renovation_issue_map"] = (
                issue_map
                if isinstance(issue_map, RenovationIssueMap)
                else RenovationIssueMap.model_validate(issue_map)
            )
    if "reference_style_profile" in state_data:
        profile = state_data["reference_style_profile"]
        if profile is not None:
            restored["reference_style_profile"] = (
                profile
                if isinstance(profile, ReferenceStyleProfile)
                else ReferenceStyleProfile.model_validate(profile)
            )
    if "storyline" in state_data:
        storyline = state_data["storyline"]
        if storyline is not None:
            restored["storyline"] = (
                storyline
                if isinstance(storyline, Storyline)
                else Storyline.model_validate(storyline)
            )
    if "outline" in state_data:
        outline = state_data["outline"]
        if outline is not None:
            restored["outline"] = (
                outline if isinstance(outline, OutlinePlan) else OutlinePlan.model_validate(outline)
            )
    if "slides" in state_data:
        slides = state_data["slides"]
        if not slides:
            restored["slides"] = []
        elif isinstance(slides[0], SlideSpec):
            restored["slides"] = list(slides)
        else:
            restored["slides"] = [SlideSpec.model_validate(item) for item in slides]
    if "review_issues" in state_data:
        issues = state_data["review_issues"]
        if not issues:
            restored["review_issues"] = []
        elif isinstance(issues[0], ReviewIssue):
            restored["review_issues"] = list(issues)
        else:
            restored["review_issues"] = [ReviewIssue.model_validate(item) for item in issues]
    if "project_facts" in state_data:
        facts = state_data["project_facts"]
        if not facts:
            restored["project_facts"] = []
        elif isinstance(facts[0], ProjectFact):
            restored["project_facts"] = list(facts)
        else:
            restored["project_facts"] = [ProjectFact.model_validate(item) for item in facts]
    return restored

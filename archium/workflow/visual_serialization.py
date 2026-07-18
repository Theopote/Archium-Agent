"""Serialize visual composition workflow state for WorkflowRun persistence."""

from __future__ import annotations

from typing import Any

from archium.domain.enums import WorkflowStep
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.preferences import VisualPreferences
from archium.workflow.visual_state import VisualWorkflowState

# Explicit denylist — never persist secrets into visual workflow state.
_FORBIDDEN_STATE_KEYS = frozenset(
    {
        "api_key",
        "llm_api_key",
        "pexels_api_key",
        "unsplash_api_key",
        "openai_api_key",
        "authorization",
        "password",
        "secret",
        "token",
    }
)


def snapshot_visual_state(state: VisualWorkflowState) -> dict[str, Any]:
    """Convert graph state to a JSON-safe checkpoint dict (no API keys)."""
    presentation = state.get("presentation")
    brief = state.get("brief")
    storyline = state.get("storyline")
    design_system = state.get("design_system")
    art_direction = state.get("art_direction")
    preferences = state.get("preferences")
    slides = state.get("slides", [])

    payload: dict[str, Any] = {
        "workflow_kind": "visual_composition",
        "current_step": state.get("current_step", WorkflowStep.INIT.value),
        "project_id": state.get("project_id"),
        "presentation_id": state.get("presentation_id"),
        "workflow_run_id": state.get("workflow_run_id"),
        "design_system_id": state.get("design_system_id"),
        "art_direction_id": state.get("art_direction_id"),
        "slide_ids": list(state.get("slide_ids", [])),
        "visual_intent_ids": list(state.get("visual_intent_ids", [])),
        "layout_plan_ids": list(state.get("layout_plan_ids", [])),
        "candidate_plan_ids_by_slide": dict(state.get("candidate_plan_ids_by_slide") or {}),
        "render_paths": list(state.get("render_paths", [])),
        "validation_reports": list(state.get("validation_reports", [])),
        "review_gate": state.get("review_gate"),
        "errors": list(state.get("errors", [])),
        "warnings": list(state.get("warnings", [])),
        "require_art_direction_review": bool(state.get("require_art_direction_review", True)),
        "use_llm": bool(state.get("use_llm", False)),
        "export_pptx": bool(state.get("export_pptx", False)),
        "export_layout_instructions": bool(state.get("export_layout_instructions", True)),
        "candidate_count": int(state.get("candidate_count", 3)),
        "repair_round": int(state.get("repair_round", 0)),
        "max_repair_rounds": int(state.get("max_repair_rounds", 1)),
        "fallback_applied": bool(state.get("fallback_applied", False)),
        "allow_invalid_layout_export": bool(state.get("allow_invalid_layout_export", False)),
        "repair_diffs": list(state.get("repair_diffs") or []),
        "visual_critic_reports": list(state.get("visual_critic_reports") or []),
        "deck_qa_report": state.get("deck_qa_report"),
        "output_dir": state.get("output_dir"),
        "presentation": presentation.model_dump(mode="json") if presentation else None,
        "brief": brief.model_dump(mode="json") if brief else None,
        "storyline": storyline.model_dump(mode="json") if storyline else None,
        "slides": [slide.model_dump(mode="json") for slide in slides],
        "design_system": design_system.model_dump(mode="json") if design_system else None,
        "art_direction": art_direction.model_dump(mode="json") if art_direction else None,
        "preferences": preferences.model_dump(mode="json") if preferences else None,
    }
    return _strip_forbidden(payload)


def restore_visual_artifacts(state_data: dict[str, Any]) -> dict[str, Any]:
    """Restore domain objects from a persisted visual workflow snapshot."""
    restored: dict[str, Any] = {
        "project_id": state_data.get("project_id"),
        "presentation_id": state_data.get("presentation_id"),
        "workflow_run_id": state_data.get("workflow_run_id"),
        "design_system_id": state_data.get("design_system_id"),
        "art_direction_id": state_data.get("art_direction_id"),
        "slide_ids": list(state_data.get("slide_ids") or []),
        "visual_intent_ids": list(state_data.get("visual_intent_ids") or []),
        "layout_plan_ids": list(state_data.get("layout_plan_ids") or []),
        "candidate_plan_ids_by_slide": dict(state_data.get("candidate_plan_ids_by_slide") or {}),
        "render_paths": list(state_data.get("render_paths") or []),
        "validation_reports": list(state_data.get("validation_reports") or []),
        "current_step": state_data.get("current_step"),
        "review_gate": state_data.get("review_gate"),
        "errors": list(state_data.get("errors") or []),
        "warnings": list(state_data.get("warnings") or []),
        "require_art_direction_review": bool(
            state_data.get("require_art_direction_review", True)
        ),
        "use_llm": bool(state_data.get("use_llm", False)),
        "export_pptx": bool(state_data.get("export_pptx", False)),
        "export_layout_instructions": bool(
            state_data.get("export_layout_instructions", True)
        ),
        "candidate_count": int(state_data.get("candidate_count", 3)),
        "repair_round": int(state_data.get("repair_round", 0)),
        "max_repair_rounds": int(state_data.get("max_repair_rounds", 1)),
        "fallback_applied": bool(state_data.get("fallback_applied", False)),
        "allow_invalid_layout_export": bool(
            state_data.get("allow_invalid_layout_export", False)
        ),
        "repair_diffs": list(state_data.get("repair_diffs") or []),
        "visual_critic_reports": list(state_data.get("visual_critic_reports") or []),
        "deck_qa_report": state_data.get("deck_qa_report"),
        "output_dir": state_data.get("output_dir"),
    }
    if state_data.get("presentation"):
        restored["presentation"] = Presentation.model_validate(state_data["presentation"])
    if state_data.get("brief"):
        restored["brief"] = PresentationBrief.model_validate(state_data["brief"])
    if state_data.get("storyline"):
        restored["storyline"] = Storyline.model_validate(state_data["storyline"])
    if state_data.get("slides"):
        restored["slides"] = [SlideSpec.model_validate(item) for item in state_data["slides"]]
    if state_data.get("design_system"):
        restored["design_system"] = DesignSystem.model_validate(state_data["design_system"])
    if state_data.get("art_direction"):
        restored["art_direction"] = ArtDirection.model_validate(state_data["art_direction"])
    if state_data.get("preferences"):
        restored["preferences"] = VisualPreferences.model_validate(state_data["preferences"])
    return restored


def _strip_forbidden(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in _FORBIDDEN_STATE_KEYS:
            continue
        cleaned[key] = value
    return cleaned

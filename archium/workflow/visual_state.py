"""LangGraph state for the visual composition workflow."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from archium.domain.enums import WorkflowStep
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.preferences import VisualPreferences


class VisualWorkflowState(TypedDict, total=False):
    """Mutable graph state for ArtDirection → Layout → Render."""

    project_id: str
    presentation_id: str
    workflow_run_id: str
    design_system_id: str
    art_direction_id: str
    slide_ids: list[str]
    visual_intent_ids: list[str]
    layout_plan_ids: list[str]
    # slide_id -> list of candidate layout_plan ids
    candidate_plan_ids_by_slide: dict[str, list[str]]
    render_paths: list[str]
    validation_reports: list[dict]
    current_step: str
    review_gate: str | None
    errors: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]

    # Runtime artifacts (also snapshotted for resume)
    presentation: Presentation | None
    brief: PresentationBrief | None
    storyline: Storyline | None
    slides: list[SlideSpec]
    design_system: DesignSystem | None
    art_direction: ArtDirection | None
    preferences: VisualPreferences | None

    require_art_direction_review: bool
    use_llm: bool
    export_pptx: bool
    export_layout_instructions: bool
    candidate_count: int
    repair_round: int
    max_repair_rounds: int
    fallback_applied: bool
    allow_invalid_layout_export: bool
    # Accumulated per-round repair before/after diffs (repair contract audit trail).
    repair_diffs: Annotated[list[dict], operator.add]
    output_dir: str | None


def initial_visual_workflow_state(
    *,
    project_id: str,
    presentation_id: str,
    workflow_run_id: str,
    require_art_direction_review: bool = True,
    use_llm: bool = False,
    export_pptx: bool = False,
    export_layout_instructions: bool = True,
    candidate_count: int = 3,
    max_repair_rounds: int = 1,
    preferences: VisualPreferences | None = None,
    design_system_id: str | None = None,
) -> VisualWorkflowState:
    """Build the initial graph state for a new visual composition run."""
    state: VisualWorkflowState = {
        "project_id": project_id,
        "presentation_id": presentation_id,
        "workflow_run_id": workflow_run_id,
        "slide_ids": [],
        "visual_intent_ids": [],
        "layout_plan_ids": [],
        "candidate_plan_ids_by_slide": {},
        "render_paths": [],
        "validation_reports": [],
        "current_step": WorkflowStep.INIT.value,
        "review_gate": None,
        "errors": [],
        "warnings": [],
        "presentation": None,
        "brief": None,
        "storyline": None,
        "slides": [],
        "design_system": None,
        "art_direction": None,
        "preferences": preferences,
        "require_art_direction_review": require_art_direction_review,
        "use_llm": use_llm,
        "export_pptx": export_pptx,
        "export_layout_instructions": export_layout_instructions,
        "candidate_count": candidate_count,
        "repair_round": 0,
        "max_repair_rounds": max_repair_rounds,
        "fallback_applied": False,
        "allow_invalid_layout_export": False,
        "repair_diffs": [],
        "output_dir": None,
    }
    if design_system_id is not None:
        state["design_system_id"] = design_system_id
    return state

"""LangGraph state definitions for the presentation workflow."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from archium.application.presentation_models import PresentationRequest
from archium.domain.enums import WorkflowStep
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec


class PresentationWorkflowState(TypedDict, total=False):
    """Mutable graph state passed between workflow nodes."""

    project_id: str
    presentation_id: str
    workflow_run_id: str
    request: PresentationRequest
    presentation: Presentation | None
    brief: PresentationBrief | None
    storyline: Storyline | None
    slides: list[SlideSpec]
    json_path: str | None
    marp_md_path: str | None
    marp_pptx_path: str | None
    export_json: bool
    export_marp: bool
    export_pptx: bool
    current_step: str
    errors: Annotated[list[str], operator.add]


def initial_workflow_state(
    *,
    project_id: str,
    presentation_id: str,
    workflow_run_id: str,
    request: PresentationRequest,
    presentation: Presentation,
    export_json: bool,
    export_marp: bool = False,
    export_pptx: bool = False,
) -> PresentationWorkflowState:
    """Build the initial graph state for a new workflow run."""
    return {
        "project_id": project_id,
        "presentation_id": presentation_id,
        "workflow_run_id": workflow_run_id,
        "request": request,
        "presentation": presentation,
        "brief": None,
        "storyline": None,
        "slides": [],
        "json_path": None,
        "marp_md_path": None,
        "marp_pptx_path": None,
        "export_json": export_json,
        "export_marp": export_marp,
        "export_pptx": export_pptx,
        "current_step": WorkflowStep.INIT.value,
        "errors": [],
    }

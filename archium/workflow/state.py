"""LangGraph state definitions for the presentation workflow."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from archium.application.chunk_models import ProjectContextBundle
from archium.application.presentation_models import PresentationRequest
from archium.domain.enums import WorkflowStep
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec


class PresentationWorkflowState(TypedDict, total=False):
    """Mutable graph state passed between workflow nodes."""

    project_id: str
    presentation_id: str
    workflow_run_id: str
    project_name: str | None
    source_document_count: int
    source_chunk_count: int
    source_validation_issues: list[str]
    request: PresentationRequest
    presentation: Presentation | None
    context_bundle: ProjectContextBundle | None
    brief: PresentationBrief | None
    storyline: Storyline | None
    slides: list[SlideSpec]
    json_path: str | None
    marp_md_path: str | None
    marp_pptx_path: str | None
    export_json: bool
    export_marp: bool
    export_pptx: bool
    require_brief_review: bool
    require_storyline_review: bool
    require_slides_review: bool
    review_gate: str | None
    slide_review_issues: list[str]
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
    require_brief_review: bool = False,
    require_storyline_review: bool = False,
    require_slides_review: bool = False,
) -> PresentationWorkflowState:
    """Build the initial graph state for a new workflow run."""
    return {
        "project_id": project_id,
        "presentation_id": presentation_id,
        "workflow_run_id": workflow_run_id,
        "project_name": None,
        "source_document_count": 0,
        "source_chunk_count": 0,
        "source_validation_issues": [],
        "request": request,
        "presentation": presentation,
        "context_bundle": None,
        "brief": None,
        "storyline": None,
        "slides": [],
        "json_path": None,
        "marp_md_path": None,
        "marp_pptx_path": None,
        "export_json": export_json,
        "export_marp": export_marp,
        "export_pptx": export_pptx,
        "require_brief_review": require_brief_review,
        "require_storyline_review": require_storyline_review,
        "require_slides_review": require_slides_review,
        "review_gate": None,
        "slide_review_issues": [],
        "current_step": WorkflowStep.INIT.value,
        "errors": [],
    }

"""LangGraph state definitions for the presentation workflow."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from archium.application.chunk_models import ProjectContextBundle
from archium.application.presentation_models import PresentationRequest
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.enums import WorkflowStep
from archium.domain.fact import ProjectFact
from archium.domain.outline import OutlinePlan
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.reference_style import ReferenceStyleProfile
from archium.domain.renovation_issue import RenovationIssueMap
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec


class PresentationWorkflowState(TypedDict, total=False):
    """Mutable graph state passed between workflow nodes."""

    project_id: str
    presentation_id: str
    workflow_run_id: str
    project_name: str | None
    source_document_count: int
    source_chunk_count: int
    source_validation_issues: Annotated[list[str], operator.add]
    request: PresentationRequest
    presentation: Presentation | None
    context_bundle: ProjectContextBundle | None
    project_facts: list[ProjectFact]
    extracted_fact_count: int
    fact_validation_issues: Annotated[list[str], operator.add]
    manuscript: PresentationManuscript | None
    brief: PresentationBrief | None
    cultural_narrative: CulturalNarrativePlan | None
    renovation_issue_map: RenovationIssueMap | None
    reference_style_profile: ReferenceStyleProfile | None
    storyline: Storyline | None
    outline: OutlinePlan | None
    slides: list[SlideSpec]
    review_issues: list[ReviewIssue]
    matched_asset_count: int
    repaired_slide_count: int
    repair_round: int
    slide_repair_records: list[object]
    json_path: str | None
    spec_path: str | None
    editable_pptx_path: str | None
    marp_md_path: str | None
    marp_pptx_path: str | None
    pdf_path: str | None
    preview_image_paths: list[str]
    export_json: bool
    export_presentation_spec: bool
    export_editable_pptx: bool
    export_marp: bool
    export_pptx: bool
    export_pdf: bool
    export_preview_images: bool
    render_warnings: Annotated[list[str], operator.add]
    require_brief_review: bool
    require_manuscript_review: bool
    require_storyline_review: bool
    require_outline_review: bool
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
    export_presentation_spec: bool = False,
    export_editable_pptx: bool = False,
    export_marp: bool = False,
    export_pptx: bool = False,
    export_pdf: bool = False,
    export_preview_images: bool = True,
    require_brief_review: bool = False,
    require_manuscript_review: bool = False,
    require_storyline_review: bool = False,
    require_outline_review: bool = True,
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
        "project_facts": [],
        "extracted_fact_count": 0,
        "fact_validation_issues": [],
        "manuscript": None,
        "brief": None,
        "cultural_narrative": None,
        "renovation_issue_map": None,
        "reference_style_profile": None,
        "storyline": None,
        "outline": None,
        "slides": [],
        "review_issues": [],
        "matched_asset_count": 0,
        "repaired_slide_count": 0,
        "repair_round": 0,
        "slide_repair_records": [],
        "json_path": None,
        "spec_path": None,
        "editable_pptx_path": None,
        "marp_md_path": None,
        "marp_pptx_path": None,
        "pdf_path": None,
        "preview_image_paths": [],
        "export_json": export_json,
        "export_presentation_spec": export_presentation_spec or export_editable_pptx,
        "export_editable_pptx": export_editable_pptx,
        "export_marp": export_marp,
        "export_pptx": export_pptx,
        "export_pdf": export_pdf,
        "export_preview_images": export_preview_images,
        "render_warnings": [],
        "require_brief_review": require_brief_review,
        "require_manuscript_review": require_manuscript_review,
        "require_storyline_review": require_storyline_review,
        "require_outline_review": require_outline_review,
        "require_slides_review": require_slides_review,
        "review_gate": None,
        "slide_review_issues": [],
        "current_step": WorkflowStep.INIT.value,
        "errors": [],
    }

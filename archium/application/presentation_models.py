"""Presentation request and pipeline result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from archium.domain.enums import PresentationType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.render import RenderResult
from archium.domain.slide import SlideSpec
from archium.domain.workflow_route import PresentationWorkflowRoute


@dataclass(frozen=True)
class PresentationRequest:
    """User input for creating and generating a presentation."""

    title: str
    audience: str
    purpose: str
    duration_minutes: int = 20
    target_slide_count: int = 20
    core_message: str = ""
    presentation_type: PresentationType = PresentationType.CLIENT_REVIEW
    decisions_required: list[str] = field(default_factory=list)
    audience_concerns: list[str] = field(default_factory=list)
    required_sections: list[str] = field(default_factory=list)
    excluded_topics: list[str] = field(default_factory=list)
    tone: str = "professional"
    language: str = "zh-CN"
    user_notes: str = ""
    use_manuscript_pipeline: bool = False
    # Per-page free-text instructions (index = page order). Seeded onto OutlinePlan.page_intents.
    page_instructions: list[str] = field(default_factory=list)
    # Explicit page materials: {page_index: [{asset_id, type/description/...}, ...]}
    # or flat list with page_index/page_order. Seeded onto OutlinePlan.page_asset_bindings.
    page_materials: dict[int, list[dict[str, object]]] | list[dict[str, object]] = field(
        default_factory=dict
    )
    # Explicit route keeps preservation-incompatible jobs out of this generation pipeline.
    workflow_route: PresentationWorkflowRoute = PresentationWorkflowRoute.GENERATE_FROM_PROJECT


@dataclass
class PipelineResult:
    """Legacy pipeline result shape. Prefer :class:`WorkflowRunResult` for new code."""

    presentation: Presentation
    brief: PresentationBrief | None = None
    storyline: Storyline | None = None
    slides: list[SlideSpec] = field(default_factory=list)
    render: RenderResult = field(default_factory=RenderResult)
    errors: list[str] = field(default_factory=list)

    @property
    def json_path(self) -> Path | None:
        return self.render.json_path

    @property
    def marp_md_path(self) -> Path | None:
        return self.render.markdown_path

    @property
    def marp_pptx_path(self) -> Path | None:
        return self.render.pptx_path

    @property
    def pdf_path(self) -> Path | None:
        return self.render.pdf_path

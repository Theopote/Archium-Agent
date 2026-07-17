"""Workflow execution result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.render import RenderResult
from archium.domain.slide import SlideSpec
from archium.domain.workflow import WorkflowRun


@dataclass
class WorkflowRunResult:
    """Outcome of a LangGraph presentation workflow execution."""

    workflow_run: WorkflowRun
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

    @property
    def render_warnings(self) -> list[str]:
        return self.render.warnings

    @property
    def succeeded(self) -> bool:
        return not self.errors

    @property
    def awaiting_review(self) -> bool:
        from archium.domain.enums import WorkflowStatus

        return self.workflow_run.status == WorkflowStatus.AWAITING_REVIEW

"""Workflow execution result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from archium.domain.presentation import Presentation, PresentationBrief, Storyline
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
    json_path: Path | None = None
    marp_md_path: Path | None = None
    marp_pptx_path: Path | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return not self.errors

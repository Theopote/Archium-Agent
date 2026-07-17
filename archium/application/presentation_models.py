"""Presentation request and pipeline result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from archium.domain.enums import PresentationType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.render import RenderResult
from archium.domain.slide import SlideSpec


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


@dataclass
class PipelineResult:
    """Result of running the presentation generation pipeline."""

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

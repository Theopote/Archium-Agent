"""Renderer protocol for presentation exports."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.slide import SlideSpec


class PresentationRenderer(Protocol):
    """Export a presentation artifact bundle to disk."""

    def render(
        self,
        *,
        presentation_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        slides: list[SlideSpec],
        version: int = 1,
    ) -> Path:
        """Write the presentation package and return the output path."""
        ...

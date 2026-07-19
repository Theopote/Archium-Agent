"""Slide-related domain models for visual editing."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.visual_intent import VisualIntent


@dataclass(frozen=True)
class SlideSnapshot:
    """
    Immutable snapshot of a slide's visual state.

    Used for operation decomposition and transaction execution.
    Contains all visual-related state needed to execute operations.
    """

    slide_id: UUID
    presentation_id: UUID
    visual_intent: VisualIntent | None
    layout_plan: LayoutPlan | None

    @property
    def has_layout_plan(self) -> bool:
        """Check if this snapshot has a layout plan."""
        return self.layout_plan is not None

    @property
    def has_visual_intent(self) -> bool:
        """Check if this snapshot has a visual intent."""
        return self.visual_intent is not None

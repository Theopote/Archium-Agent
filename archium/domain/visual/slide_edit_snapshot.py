"""Immutable visual-edit state snapshot (distinct from ``archium.domain.slide.SlideSpec``)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.visual_intent import VisualIntent


@dataclass(frozen=True)
class SlideEditSnapshot:
    """
    Immutable snapshot of a slide's visual state for composite edit transactions.

    Used for operation decomposition and :class:`TransactionExecutor` checkpoints.
    """

    slide_id: UUID
    presentation_id: UUID
    visual_intent: VisualIntent | None
    layout_plan: LayoutPlan | None

    @property
    def has_layout_plan(self) -> bool:
        return self.layout_plan is not None

    @property
    def has_visual_intent(self) -> bool:
        return self.visual_intent is not None

"""Helpers for immutable layout / intent updates inside transactions."""

from __future__ import annotations

from typing import Any, TypeVar

from archium.domain._base import utc_now
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.visual_intent import VisualIntent

VersionedVisualModel = TypeVar("VersionedVisualModel", LayoutPlan, VisualIntent)


def bumped_layout_plan(
    plan: LayoutPlan,
    *,
    elements: list[LayoutElement] | None = None,
    extra_updates: dict[str, Any] | None = None,
) -> LayoutPlan:
    """Return a new layout plan with incremented version and fresh ``updated_at``."""
    updates: dict[str, Any] = {
        "version": plan.version + 1,
        "updated_at": utc_now(),
    }
    if elements is not None:
        updates["elements"] = elements
    if extra_updates:
        updates.update(extra_updates)
    return plan.model_copy(update=updates)


def restored_from_snapshot(model: VersionedVisualModel) -> VersionedVisualModel:
    """Return a persisted-ready copy without mutating the validated instance in place."""
    return model.model_copy(update={"updated_at": utc_now()})

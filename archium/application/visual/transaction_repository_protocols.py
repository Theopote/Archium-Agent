"""Typed repository contracts for visual transaction execution."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from archium.domain.slide import SlideSpec
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.visual_intent import VisualIntent


@runtime_checkable
class VisualIntentRepositoryProtocol(Protocol):
    def get(self, intent_id: UUID) -> VisualIntent | None: ...

    def save(self, intent: VisualIntent) -> VisualIntent: ...


@runtime_checkable
class LayoutPlanRepositoryProtocol(Protocol):
    def get(self, plan_id: UUID) -> LayoutPlan | None: ...

    def save(self, plan: LayoutPlan) -> LayoutPlan: ...


@runtime_checkable
class PresentationRepositoryProtocol(Protocol):
    def get_slide(self, slide_id: UUID) -> SlideSpec | None: ...

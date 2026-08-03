"""/visual — art direction, layout plans, intents, and presentation visual load."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)


@dataclass(frozen=True)
class LoadedSlideVisual:
    slide: SlideSpec
    visual_intent: VisualIntent | None
    layout_plan: LayoutPlan | None
    candidates: list[LayoutPlan] = field(default_factory=list)


@dataclass(frozen=True)
class LoadedPresentationVisual:
    presentation_id: UUID
    design_system: DesignSystem | None
    art_direction: ArtDirection | None
    slides: tuple[LoadedSlideVisual, ...]


class VisualApi:
    """Stable visual read/write helpers for Studio (no UI types)."""

    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._session = session
        self._presentations = PresentationRepository(session)
        self._intents = VisualIntentRepository(session)
        self._plans = LayoutPlanRepository(session)
        self._art = ArtDirectionRepository(session)
        self._design = DesignSystemRepository(session)

    def get_layout_plan(self, layout_plan_id: UUID) -> LayoutPlan | None:
        return self._plans.get(layout_plan_id)

    def list_layout_plans_for_slide(self, slide_id: UUID) -> list[LayoutPlan]:
        return self._plans.list_by_slide(slide_id)

    def save_layout_plan(self, plan: LayoutPlan) -> LayoutPlan:
        return self._plans.save(plan)

    def get_visual_intent(self, intent_id: UUID) -> VisualIntent | None:
        return self._intents.get(intent_id)

    def get_visual_intent_for_slide(self, slide_id: UUID) -> VisualIntent | None:
        return self._intents.get_by_slide(slide_id)

    def save_visual_intent(self, intent: VisualIntent) -> VisualIntent:
        return self._intents.save(intent)

    def save_design_system(self, design_system: DesignSystem) -> DesignSystem:
        return self._design.save(design_system)

    def resolve_visual_intent_for_slide(self, slide: SlideSpec) -> VisualIntent | None:
        if slide.visual_intent_id is not None:
            intent = self._intents.get(slide.visual_intent_id)
            if intent is not None:
                return intent
        return self._intents.get_by_slide(slide.id)

    def resolve_layout_plan_for_slide(self, slide: SlideSpec) -> LayoutPlan | None:
        if slide.layout_plan_id is not None:
            plan = self._plans.get(slide.layout_plan_id)
            if plan is not None:
                return plan
        listed = self._plans.list_by_slide(slide.id)
        return listed[0] if listed else None

    def get_art_direction(self, art_direction_id: UUID) -> ArtDirection | None:
        return self._art.get(art_direction_id)

    def list_art_directions_for_project(self, project_id: UUID) -> list[ArtDirection]:
        return self._art.list_by_project(project_id)

    def resolve_art_direction_for_presentation(
        self,
        *,
        project_id: UUID,
        presentation_id: UUID,
    ) -> ArtDirection | None:
        for art in self._art.list_by_project(project_id):
            if art.presentation_id == presentation_id:
                return art
        arts = self._art.list_by_project(project_id)
        return arts[0] if arts else None

    def get_design_system(self, design_system_id: UUID) -> DesignSystem | None:
        return self._design.get(design_system_id)

    def load_presentation_visual(self, presentation_id: UUID) -> LoadedPresentationVisual:
        presentation = self._presentations.get_presentation(presentation_id)
        slides = self._presentations.list_slides(presentation_id)
        art_direction = None
        design_system = None
        if presentation is not None:
            art_direction = self.resolve_art_direction_for_presentation(
                project_id=presentation.project_id,
                presentation_id=presentation_id,
            )
        if art_direction is not None and art_direction.design_system_id is not None:
            design_system = self._design.get(art_direction.design_system_id)

        loaded: list[LoadedSlideVisual] = []
        for slide in slides:
            intent = self.resolve_visual_intent_for_slide(slide)
            plan = self.resolve_layout_plan_for_slide(slide)
            candidates = self._plans.list_by_slide(slide.id)
            loaded.append(
                LoadedSlideVisual(
                    slide=slide,
                    visual_intent=intent,
                    layout_plan=plan,
                    candidates=candidates,
                )
            )
        return LoadedPresentationVisual(
            presentation_id=presentation_id,
            design_system=design_system,
            art_direction=art_direction,
            slides=tuple(loaded),
        )

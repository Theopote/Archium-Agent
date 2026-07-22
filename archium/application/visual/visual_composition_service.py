"""Thin orchestration for ArtDirection → VisualIntent → LayoutPlan."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.art_direction_service import ArtDirectionService
from archium.application.visual.layout_planning_service import LayoutPlanningService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.preferences import VisualPreferences
from archium.domain.visual.validation import LayoutValidationReport
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    DesignSystemRepository,
    LayoutPlanRepository,
)
from archium.infrastructure.llm.base import LLMProvider


@dataclass
class SlideCompositionResult:
    visual_intent: VisualIntent
    layout_plan: LayoutPlan
    validation: LayoutValidationReport
    candidates: list[tuple[LayoutPlan, LayoutValidationReport]]


@dataclass
class PresentationCompositionResult:
    design_system: DesignSystem
    art_direction: ArtDirection
    slides: list[SlideCompositionResult]


class VisualCompositionService:
    """Facade that wires visual services without becoming a god-object."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._design = DesignSystemRepository(session)
        self._plans = LayoutPlanRepository(session)
        self._art = ArtDirectionService(session, llm=llm)
        self._intent = VisualIntentService(session, llm=llm)
        self._layout = LayoutPlanningService(session, llm=llm)
        self._validator = LayoutValidationService()
        self._presentations = PresentationRepository(session)

    def ensure_design_system(self, design_system_id: UUID | None = None) -> DesignSystem:
        if design_system_id is not None:
            existing = self._design.get(design_system_id)
            if existing is not None:
                return existing
        return self._design.save(default_presentation_design_system())

    def compose_presentation(
        self,
        *,
        project_id: UUID,
        presentation_id: UUID,
        slides: list[SlideSpec] | None = None,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
        preferences: VisualPreferences | None = None,
        design_system_id: UUID | None = None,
        approve_art_direction: bool = False,
        use_llm: bool = False,
        candidate_count: int = 3,
    ) -> PresentationCompositionResult:
        design = self.ensure_design_system(design_system_id)
        art = self._art.generate(
            project_id=project_id,
            presentation_id=presentation_id,
            design_system_id=design.id,
            user_preferences=preferences,
            brief=brief,
            storyline=storyline,
            use_llm=use_llm,
        )
        if approve_art_direction:
            art = self._art.approve(art.id)

        resolved_slides = slides or self._presentations.list_slides(presentation_id)
        results: list[SlideCompositionResult] = []
        for index, slide in enumerate(resolved_slides):
            previous = resolved_slides[index - 1] if index > 0 else None
            nxt = resolved_slides[index + 1] if index + 1 < len(resolved_slides) else None
            results.append(
                self.compose_slide(
                    slide,
                    art_direction=art,
                    design_system=design,
                    previous_slide=previous,
                    next_slide=nxt,
                    use_llm=use_llm,
                    candidate_count=candidate_count,
                )
            )
        return PresentationCompositionResult(
            design_system=design,
            art_direction=art,
            slides=results,
        )

    def compose_slide(
        self,
        slide: SlideSpec,
        *,
        art_direction: ArtDirection,
        design_system: DesignSystem,
        previous_slide: SlideSpec | None = None,
        next_slide: SlideSpec | None = None,
        use_llm: bool = False,
        candidate_count: int = 3,
    ) -> SlideCompositionResult:
        intent = self._intent.generate_for_slide(
            slide,
            art_direction=art_direction,
            previous_slide=previous_slide,
            next_slide=next_slide,
            use_llm=use_llm,
        )
        presentation = self._presentations.get_presentation(slide.presentation_id)
        project_id = presentation.project_id if presentation is not None else None
        candidates = self._layout.generate_candidates(
            slide=slide,
            visual_intent_id=intent.id,
            art_direction_id=art_direction.id,
            design_system_id=design_system.id,
            candidate_count=candidate_count,
            project_id=project_id,
        )
        best = self._layout.select_best(
            candidates,
            style_preference=self._layout.last_style_preference,
        )
        saved = self._plans.save(best)
        report = next(
            (report for plan, report in candidates if plan.id == best.id),
            self._validator.validate(saved, design_system),
        )

        slide.visual_intent_id = intent.id
        slide.layout_plan_id = saved.id
        self._presentations.save_slide(slide)

        return SlideCompositionResult(
            visual_intent=intent,
            layout_plan=saved,
            validation=report,
            candidates=candidates,
        )

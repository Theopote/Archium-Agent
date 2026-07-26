"""Atomic presentation generation capabilities used by the LangGraph workflow."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.narrative.brief_service import BriefService
from archium.application.narrative.outline_plan_service import OutlinePlanService
from archium.application.narrative.slide_plan_service import SlidePlanService
from archium.application.narrative.specialty_plan_services import (
    CulturalNarrativeService,
    ReferenceStyleProfileService,
    RenovationIssueMapService,
)
from archium.application.narrative.storyline_service import StorylineService
from archium.application.presentation_models import PresentationRequest
from archium.config.settings import Settings, get_settings
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.reference_style import ReferenceStyleProfile
from archium.domain.renovation_issue import RenovationIssueMap
from archium.domain.slide import SlideSpec
from archium.domain.slide_asset_binding import SlideAssetBinding
from archium.domain.slide_intent import SlideIntent
from archium.exceptions import ProjectNotFoundError
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.renderers.json_renderer import JsonPresentationRenderer
from archium.infrastructure.renderers.marp_renderer import MarpPresentationRenderer
from archium.logging import get_logger

logger = get_logger(__name__, operation="presentation")


class PresentationService:
    """Atomic presentation generation capabilities used by the LangGraph workflow.

    Orchestrates Narrative **Services** (persist) and LLM **planners** (propose).
    """

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        renderer: JsonPresentationRenderer | None = None,
        marp_renderer: MarpPresentationRenderer | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._projects = ProjectRepository(session)
        self._brief = BriefService(session, llm, settings=self._settings)
        self._cultural_narrative = CulturalNarrativeService(
            session, llm, settings=self._settings
        )
        self._renovation_issue_map = RenovationIssueMapService(
            session, llm, settings=self._settings
        )
        self._reference_style = ReferenceStyleProfileService(
            session, llm, settings=self._settings
        )
        self._storyline = StorylineService(session, llm, settings=self._settings)
        self._outline = OutlinePlanService(session, llm, settings=self._settings)
        self._slide_planner = SlidePlanService(session, llm, settings=self._settings)
        self._renderer = renderer or JsonPresentationRenderer(self._settings)
        self._marp_renderer = marp_renderer or MarpPresentationRenderer(self._settings)

    def create_presentation(
        self,
        project_id: UUID,
        request: PresentationRequest,
    ) -> Presentation:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return self._presentations.create_presentation(
            Presentation(
                project_id=project_id,
                title=request.title,
                mission_id=request.mission_id,
            )
        )

    def generate_brief(
        self,
        project_id: UUID,
        presentation_id: UUID,
        request: PresentationRequest,
        *,
        manuscript: PresentationManuscript | None = None,
    ) -> PresentationBrief:
        return self._brief.generate(
            project_id,
            presentation_id,
            request,
            manuscript=manuscript,
        )

    def generate_cultural_narrative(
        self,
        project_id: UUID,
        brief: PresentationBrief,
    ) -> CulturalNarrativePlan | None:
        return self._cultural_narrative.generate(project_id, brief)

    def generate_renovation_issue_map(
        self,
        project_id: UUID,
        brief: PresentationBrief,
    ) -> RenovationIssueMap | None:
        return self._renovation_issue_map.generate(project_id, brief)

    def generate_reference_style_profile(
        self,
        project_id: UUID,
        brief: PresentationBrief,
    ) -> ReferenceStyleProfile | None:
        return self._reference_style.generate(project_id, brief)

    def generate_storyline(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        *,
        cultural_narrative: CulturalNarrativePlan | None = None,
        renovation_issue_map: RenovationIssueMap | None = None,
        manuscript: PresentationManuscript | None = None,
        use_manuscript_pipeline: bool = False,
    ) -> Storyline:
        return self._storyline.generate(
            project_id,
            brief,
            cultural_narrative=cultural_narrative,
            renovation_issue_map=renovation_issue_map,
            manuscript=manuscript,
            use_manuscript_pipeline=use_manuscript_pipeline,
        )

    def generate_outline_plan(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        *,
        cultural_narrative: CulturalNarrativePlan | None = None,
        renovation_issue_map: RenovationIssueMap | None = None,
        manuscript: PresentationManuscript | None = None,
        use_manuscript_pipeline: bool = False,
        page_intents: list[SlideIntent] | None = None,
        page_asset_bindings: list[SlideAssetBinding] | None = None,
    ) -> OutlinePlan:
        return self._outline.generate(
            project_id,
            brief,
            storyline,
            cultural_narrative=cultural_narrative,
            renovation_issue_map=renovation_issue_map,
            manuscript=manuscript,
            use_manuscript_pipeline=use_manuscript_pipeline,
            page_intents=page_intents,
            page_asset_bindings=page_asset_bindings,
        )

    def generate_slide_plan(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        outline: OutlinePlan | None = None,
        *,
        manuscript: PresentationManuscript | None = None,
        use_manuscript_pipeline: bool = False,
    ) -> list[SlideSpec]:
        return self._slide_planner.generate(
            project_id,
            brief,
            storyline,
            outline=outline,
            manuscript=manuscript,
            use_manuscript_pipeline=use_manuscript_pipeline,
        )

    def retry_slide(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        *,
        order: int,
        outline: OutlinePlan | None = None,
        sibling_slides: list[SlideSpec] | None = None,
        version: int = 1,
        manuscript: PresentationManuscript | None = None,
        use_manuscript_pipeline: bool = False,
    ) -> SlideSpec:
        return self._slide_planner.generate_one(
            project_id,
            brief,
            storyline,
            order=order,
            outline=outline,
            manuscript=manuscript,
            use_manuscript_pipeline=use_manuscript_pipeline,
            version=version,
            sibling_slides=sibling_slides,
        )

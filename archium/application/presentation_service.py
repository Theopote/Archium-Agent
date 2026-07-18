"""Atomic presentation generation capabilities used by the LangGraph workflow."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents.brief_builder import BriefBuilder
from archium.agents.narrative_architect import NarrativeArchitect
from archium.agents.slide_planner import SlidePlanner
from archium.application.presentation_models import PresentationRequest
from archium.config.settings import Settings, get_settings
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec
from archium.exceptions import ProjectNotFoundError
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.renderers.json_renderer import JsonPresentationRenderer
from archium.infrastructure.renderers.marp_renderer import MarpPresentationRenderer
from archium.logging import get_logger

logger = get_logger(__name__, operation="presentation")


class PresentationService:
    """Atomic presentation generation capabilities used by the LangGraph workflow."""

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
        self._brief_builder = BriefBuilder(session, llm, settings=self._settings)
        self._narrative = NarrativeArchitect(session, llm, settings=self._settings)
        self._slide_planner = SlidePlanner(session, llm, settings=self._settings)
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
            Presentation(project_id=project_id, title=request.title)
        )

    def generate_brief(
        self,
        project_id: UUID,
        presentation_id: UUID,
        request: PresentationRequest,
    ) -> PresentationBrief:
        return self._brief_builder.generate(project_id, presentation_id, request)

    def generate_storyline(
        self,
        project_id: UUID,
        brief: PresentationBrief,
    ) -> Storyline:
        return self._narrative.generate(project_id, brief)

    def generate_slide_plan(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
    ) -> list[SlideSpec]:
        return self._slide_planner.generate(project_id, brief, storyline)

"""Presentation generation pipeline service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents.brief_builder import BriefBuilder
from archium.agents.narrative_architect import NarrativeArchitect
from archium.agents.slide_planner import SlidePlanner
from archium.application.presentation_models import PipelineResult, PresentationRequest
from archium.config.settings import Settings, get_settings
from archium.domain.enums import PresentationStatus
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.renderers.json_renderer import JsonPresentationRenderer
from archium.infrastructure.renderers.marp_renderer import MarpPresentationRenderer
from archium.logging import get_logger

logger = get_logger(__name__, operation="presentation")


class PresentationService:
    """Orchestrate brief → storyline → slide plan → JSON export."""

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
            raise ValueError(f"Project {project_id} not found")
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

    def run_pipeline(
        self,
        project_id: UUID,
        request: PresentationRequest,
        *,
        presentation_id: UUID | None = None,
        export_json: bool = True,
        export_marp: bool = False,
        export_pptx: bool = False,
    ) -> PipelineResult:
        result = PipelineResult(
            presentation=Presentation(project_id=project_id, title=request.title),
        )
        try:
            if presentation_id is None:
                result.presentation = self.create_presentation(project_id, request)
            else:
                existing = self._presentations.get_presentation(presentation_id)
                if existing is None:
                    raise ValueError(f"Presentation {presentation_id} not found")
                result.presentation = existing

            pres_id = result.presentation.id
            result.brief = self.generate_brief(project_id, pres_id, request)
            result.storyline = self.generate_storyline(project_id, result.brief)
            result.slides = self.generate_slide_plan(project_id, result.brief, result.storyline)

            if export_json and result.brief and result.storyline:
                version = result.brief.version
                result.json_path = self._renderer.render(
                    presentation_id=pres_id,
                    brief=result.brief,
                    storyline=result.storyline,
                    slides=result.slides,
                    version=version,
                )

            if export_marp and result.brief and result.storyline:
                version = result.brief.version
                result.marp_md_path = self._marp_renderer.render(
                    presentation_id=pres_id,
                    brief=result.brief,
                    storyline=result.storyline,
                    slides=result.slides,
                    version=version,
                )
                if export_pptx and result.marp_md_path is not None:
                    result.marp_pptx_path = self._marp_renderer.export_pptx(result.marp_md_path)

            result.presentation.status = PresentationStatus.REVIEW
            result.presentation.current_brief_id = result.brief.id if result.brief else None
            result.presentation.current_storyline_id = (
                result.storyline.id if result.storyline else None
            )
            result.presentation = self._presentations.update_presentation(result.presentation)

            logger.info(
                "Pipeline completed for presentation %s with %d slides",
                pres_id,
                len(result.slides),
            )
        except Exception as exc:
            logger.exception("Pipeline failed")
            raise WorkflowError("Presentation pipeline failed") from exc
        return result

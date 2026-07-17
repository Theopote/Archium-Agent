"""Presentation generation pipeline service."""

from __future__ import annotations

import warnings
from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents.brief_builder import BriefBuilder
from archium.agents.narrative_architect import NarrativeArchitect
from archium.agents.slide_planner import SlidePlanner
from archium.application.presentation_models import PipelineResult, PresentationRequest
from archium.application.workflow_models import WorkflowRunResult
from archium.config.settings import Settings, get_settings
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec
from archium.exceptions import (
    PresentationNotFoundError,
    ProjectNotFoundError,
    WorkflowError,
)
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

    def run_pipeline(
        self,
        project_id: UUID,
        request: PresentationRequest,
        *,
        presentation_id: UUID | None = None,
        export_json: bool = True,
        export_marp: bool = False,
        export_pptx: bool = False,
        export_pdf: bool = False,
    ) -> PipelineResult:
        """Deprecated: delegate to :class:`PresentationWorkflowService`."""
        warnings.warn(
            "PresentationService.run_pipeline() is deprecated; "
            "use PresentationWorkflowService.run() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from archium.application.presentation_workflow_service import PresentationWorkflowService

        if presentation_id is not None:
            existing = self._presentations.get_presentation(presentation_id)
            if existing is None:
                raise PresentationNotFoundError(presentation_id)
            logger.warning(
                "run_pipeline(presentation_id=...) is ignored; "
                "workflow runs always create a new presentation record."
            )

        workflow = PresentationWorkflowService(
            self._session,
            self._llm,
            settings=self._settings,
            renderer=self._renderer,
        )
        try:
            workflow_result = workflow.run(
                project_id,
                request,
                export_json=export_json,
                export_marp=export_marp,
                export_pptx=export_pptx,
                export_pdf=export_pdf,
            )
        except WorkflowError:
            raise WorkflowError("Presentation pipeline failed") from None
        return _workflow_result_to_pipeline(workflow_result)


def _workflow_result_to_pipeline(result: WorkflowRunResult) -> PipelineResult:
    return PipelineResult(
        presentation=result.presentation,
        brief=result.brief,
        storyline=result.storyline,
        slides=list(result.slides),
        render=result.render,
        errors=list(result.errors),
    )

"""Runtime dependencies shared by workflow graph nodes."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from archium.application.pptxgen_renderer_factory import create_pptxgen_renderer
from archium.application.presentation_service import PresentationService
from archium.config.settings import Settings, get_settings
from archium.infrastructure.database.repositories import WorkflowRunRepository
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.renderers.json_renderer import JsonPresentationRenderer
from archium.infrastructure.renderers.marp_renderer import MarpPresentationRenderer
from archium.infrastructure.renderers.pptxgen_renderer import PptxGenPresentationRenderer


@dataclass
class PresentationWorkflowRuntime:
    """Dependencies injected into LangGraph workflow nodes."""

    session: Session
    llm: LLMProvider
    settings: Settings
    presentation_service: PresentationService
    workflow_runs: WorkflowRunRepository
    json_renderer: JsonPresentationRenderer
    marp_renderer: MarpPresentationRenderer
    pptxgen_renderer: PptxGenPresentationRenderer

    @classmethod
    def create(
        cls,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        renderer: JsonPresentationRenderer | None = None,
        marp_renderer: MarpPresentationRenderer | None = None,
        pptxgen_renderer: PptxGenPresentationRenderer | None = None,
    ) -> PresentationWorkflowRuntime:
        resolved_settings = settings or get_settings()
        presentation_service = PresentationService(
            session,
            llm,
            settings=resolved_settings,
            renderer=renderer,
            marp_renderer=marp_renderer,
        )
        return cls(
            session=session,
            llm=llm,
            settings=resolved_settings,
            presentation_service=presentation_service,
            workflow_runs=WorkflowRunRepository(session),
            json_renderer=renderer or JsonPresentationRenderer(resolved_settings),
            marp_renderer=marp_renderer or MarpPresentationRenderer(resolved_settings),
            pptxgen_renderer=pptxgen_renderer
            or create_pptxgen_renderer(resolved_settings, session=session),
        )

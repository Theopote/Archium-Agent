"""Runtime dependencies shared by workflow graph nodes."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from archium.application.presentation_service import PresentationService
from archium.config.settings import Settings, get_settings
from archium.infrastructure.database.repositories import WorkflowRunRepository
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.renderers.json_renderer import JsonPresentationRenderer


@dataclass
class PresentationWorkflowRuntime:
    """Dependencies injected into LangGraph workflow nodes."""

    session: Session
    llm: LLMProvider
    settings: Settings
    presentation_service: PresentationService
    workflow_runs: WorkflowRunRepository
    renderer: JsonPresentationRenderer

    @classmethod
    def create(
        cls,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        renderer: JsonPresentationRenderer | None = None,
    ) -> PresentationWorkflowRuntime:
        resolved_settings = settings or get_settings()
        presentation_service = PresentationService(session, llm, settings=resolved_settings)
        return cls(
            session=session,
            llm=llm,
            settings=resolved_settings,
            presentation_service=presentation_service,
            workflow_runs=WorkflowRunRepository(session),
            renderer=renderer or JsonPresentationRenderer(resolved_settings),
        )

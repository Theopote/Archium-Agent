"""/context — project cognition snapshot facade."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.project_context_builder import build_project_context
from archium.domain.context.project_context import ProjectContext


class ContextApi:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, project_id: UUID) -> ProjectContext | None:
        return build_project_context(self._session, project_id)

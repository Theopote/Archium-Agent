"""/context — project cognition snapshot facade."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.project_context_builder import build_project_context
from archium.domain.context.project_context import ProjectContext
from archium.domain.fact import ProjectFact
from archium.infrastructure.database.repositories import FactRepository


class ContextApi:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._facts = FactRepository(session)

    def get(self, project_id: UUID) -> ProjectContext | None:
        return build_project_context(self._session, project_id)

    def list_facts(self, project_id: UUID) -> list[ProjectFact]:
        return self._facts.list_by_project(project_id)

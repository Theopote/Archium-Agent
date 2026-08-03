"""/revisions — entity revision facade."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.application.revision_service import RevisionService
from archium.domain.enums import RevisionEntityType
from archium.domain.revision import EntityRevision


class RevisionsApi:
    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._service = RevisionService(session)

    def list_by_lineage(self, lineage_id: UUID) -> list[EntityRevision]:
        return self._service.list_by_lineage(lineage_id)

    def list_by_presentation(
        self,
        presentation_id: UUID,
        *,
        entity_type: RevisionEntityType | None = None,
    ) -> list[EntityRevision]:
        return self._service.list_by_presentation(
            presentation_id,
            entity_type=entity_type,
        )

    def get(self, revision_id: UUID) -> EntityRevision | None:
        return self._service.get_revision(revision_id)

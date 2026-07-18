"""Unified revision history service for domain entities."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.enums import RevisionEntityType, RevisionSource
from archium.domain.revision import EntityRevision
from archium.infrastructure.database.repositories import EntityRevisionRepository


class RevisionService:
    """Record and query entity revisions by stable lineage ID."""

    def __init__(self, session: Session) -> None:
        self._revisions = EntityRevisionRepository(session)

    def record(
        self,
        *,
        entity_type: RevisionEntityType,
        entity_id: UUID | None,
        lineage_id: UUID,
        presentation_id: UUID | None,
        change_source: RevisionSource,
        snapshot: dict[str, object],
        note: str | None = None,
        actor: str | None = None,
    ) -> EntityRevision:
        revision_number = self._revisions.next_revision_number(lineage_id)
        revision = EntityRevision(
            entity_type=entity_type,
            entity_id=entity_id,
            lineage_id=lineage_id,
            presentation_id=presentation_id,
            revision_number=revision_number,
            change_source=change_source,
            snapshot=snapshot,
            note=note,
            actor=actor,
        )
        return self._revisions.create(revision)

    def list_by_lineage(self, lineage_id: UUID) -> list[EntityRevision]:
        return self._revisions.list_by_lineage(lineage_id)

    def list_by_presentation(
        self,
        presentation_id: UUID,
        *,
        entity_type: RevisionEntityType | None = None,
    ) -> list[EntityRevision]:
        return self._revisions.list_by_presentation(presentation_id, entity_type=entity_type)

    def get_revision(self, revision_id: UUID) -> EntityRevision | None:
        return self._revisions.get_by_id(revision_id)

    def get_previous_revision(
        self,
        lineage_id: UUID,
        revision_number: int,
    ) -> EntityRevision | None:
        return self._revisions.get_previous_revision(lineage_id, revision_number)

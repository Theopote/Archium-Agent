"""Resolve whether a project has bound materials (fail-closed when unknown)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.enums import EvidenceAvailability


@dataclass(frozen=True)
class ProjectEvidenceStatus:
    availability: EvidenceAvailability
    document_count: int = 0

    @property
    def allows_formal_export(self) -> bool:
        return (
            self.availability == EvidenceAvailability.AVAILABLE
            and self.document_count > 0
        )

    @property
    def is_concept_draft(self) -> bool:
        return self.availability == EvidenceAvailability.MISSING

    @property
    def is_unknown(self) -> bool:
        return self.availability == EvidenceAvailability.UNKNOWN


def resolve_project_evidence(session: Session, project_id: UUID) -> ProjectEvidenceStatus:
    from archium.infrastructure.database.repositories import DocumentRepository

    documents = DocumentRepository(session).list_by_project(project_id)
    count = len(documents)
    if count > 0:
        return ProjectEvidenceStatus(
            availability=EvidenceAvailability.AVAILABLE,
            document_count=count,
        )
    return ProjectEvidenceStatus(
        availability=EvidenceAvailability.MISSING,
        document_count=0,
    )


def resolve_project_evidence_safe(project_id: UUID) -> ProjectEvidenceStatus:
    """Open a session and resolve evidence; query failures become UNKNOWN."""
    from archium.infrastructure.database.session import get_session

    try:
        with get_session() as session:
            return resolve_project_evidence(session, project_id)
    except Exception:
        return ProjectEvidenceStatus(
            availability=EvidenceAvailability.UNKNOWN,
            document_count=0,
        )

"""Persist and list delivery export records."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.delivery_record import DeliveryRecord
from archium.infrastructure.database.repositories import DeliveryRecordRepository


def _file_hash(path: str) -> str:
    file_path = Path(path)
    if not file_path.is_file():
        return ""
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


@dataclass(frozen=True)
class DeliveryRecordResult:
    """Distinguishes file export success from audit-row persistence."""

    file_exported: bool
    record_persisted: bool
    record: DeliveryRecord | None = None
    error_message: str | None = None


class DeliveryRecordService:
    def __init__(self, session: Session) -> None:
        self._records = DeliveryRecordRepository(session)

    def record_export(
        self,
        *,
        project_id: UUID,
        presentation_id: UUID,
        format: str,
        file_uri: str,
        qa_status: str = "unknown",
        revision_id: UUID | None = None,
    ) -> DeliveryRecord:
        record = DeliveryRecord(
            project_id=project_id,
            presentation_id=presentation_id,
            revision_id=revision_id,
            format=format,
            file_uri=file_uri,
            file_hash=_file_hash(file_uri),
            qa_status=qa_status,
            exported_at=datetime.now(UTC),
        )
        return self._records.create(record)

    def list_for_project(self, project_id: UUID, *, limit: int = 12) -> list[DeliveryRecord]:
        return self._records.list_by_project(project_id, limit=limit)

    def list_for_presentation(
        self,
        presentation_id: UUID,
        *,
        limit: int = 12,
    ) -> list[DeliveryRecord]:
        return self._records.list_by_presentation(presentation_id, limit=limit)

"""Persist and list delivery export records."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.artifact_policy_service import (
    ArtifactMutationGuard,
    ArtifactMutationOperation,
)
from archium.domain.artifact_ownership import ArtifactKind, ArtifactRecord
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
        self._artifact_guard = ArtifactMutationGuard()

    def record_export(
        self,
        *,
        project_id: UUID,
        presentation_id: UUID,
        format: str,
        file_uri: str,
        qa_status: str = "unknown",
        revision_id: UUID | None = None,
        round_trip_report: dict[str, object] | None = None,
        derived_from_artifact_ids: list[UUID] | None = None,
        generator_version: str = "archium-unknown",
        font_manifest_hash: str | None = None,
        theme_version: str | None = None,
        export_policy: str | None = None,
    ) -> DeliveryRecord:
        artifact_kind = ArtifactKind.PPTX if format.lower() == "pptx" else None
        if artifact_kind is not None:
            self._artifact_guard.require_entry(
                artifact_kind,
                ArtifactMutationOperation.DERIVE,
                entrypoint="delivery.record_pptx_export",
            )
            self._artifact_guard.validate_derivation(
                ArtifactKind.RENDER_SCENE, artifact_kind
            )
        record = DeliveryRecord(
            project_id=project_id,
            presentation_id=presentation_id,
            revision_id=revision_id,
            artifact_kind=artifact_kind.value if artifact_kind else format.lower(),
            derived_from_artifact_ids=derived_from_artifact_ids or [],
            generator_version=generator_version,
            font_manifest_hash=font_manifest_hash,
            theme_version=theme_version,
            export_policy=export_policy,
            format=format,
            file_uri=file_uri,
            file_hash=_file_hash(file_uri),
            qa_status=qa_status,
            round_trip_report_json=round_trip_report,
            exported_at=datetime.now(UTC),
        )
        return self._records.create(record)

    @staticmethod
    def artifact_record(record: DeliveryRecord) -> ArtifactRecord:
        """Expose the generic lineage contract for a persisted PPTX delivery."""
        if record.artifact_kind != ArtifactKind.PPTX.value or not record.file_hash:
            raise ValueError("Only hashed PPTX delivery records map to ArtifactRecord")
        return ArtifactRecord(
            id=record.id,
            kind=ArtifactKind.PPTX,
            project_id=record.project_id,
            presentation_id=record.presentation_id,
            revision_id=record.revision_id,
            content_hash=record.file_hash,
            derived_from_artifact_ids=tuple(record.derived_from_artifact_ids),
            generator_version=record.generator_version,
            font_manifest_hash=record.font_manifest_hash,
            theme_version=record.theme_version,
            export_policy=record.export_policy,
            created_at=record.exported_at,
        )

    def list_for_project(self, project_id: UUID, *, limit: int = 12) -> list[DeliveryRecord]:
        return self._records.list_by_project(project_id, limit=limit)

    def list_for_presentation(
        self,
        presentation_id: UUID,
        *,
        limit: int = 12,
    ) -> list[DeliveryRecord]:
        return self._records.list_by_presentation(presentation_id, limit=limit)

"""/delivery — export records and delivery audit facade."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.api.jobs import JobsApi
from archium.application.delivery_record_service import DeliveryRecordService
from archium.domain.background_job import BackgroundJob, BackgroundJobKind
from archium.domain.delivery_record import DeliveryRecord


class DeliveryApi:
    def __init__(self, session: Session) -> None:
        self._records = DeliveryRecordService(session)
        self._jobs = JobsApi(session)

    def list_for_project(self, project_id: UUID, *, limit: int = 20) -> list[DeliveryRecord]:
        return self._records.list_for_project(project_id, limit=limit)

    def list_for_presentation(
        self,
        presentation_id: UUID,
        *,
        limit: int = 12,
    ) -> list[DeliveryRecord]:
        return self._records.list_for_presentation(presentation_id, limit=limit)

    def record_export(
        self,
        *,
        project_id: UUID,
        presentation_id: UUID,
        format: str,
        file_uri: str,
        qa_status: str = "unknown",
        revision_id: UUID | None = None,
        round_trip_report: dict[str, Any] | None = None,
        derived_from_artifact_ids: list[UUID] | None = None,
        generator_version: str = "archium-unknown",
        font_manifest_hash: str | None = None,
        theme_version: str | None = None,
        export_policy: str | None = None,
    ) -> DeliveryRecord:
        return self._records.record_export(
            project_id=project_id,
            presentation_id=presentation_id,
            format=format,
            file_uri=file_uri,
            qa_status=qa_status,
            revision_id=revision_id,
            round_trip_report=round_trip_report,
            derived_from_artifact_ids=derived_from_artifact_ids,
            generator_version=generator_version,
            font_manifest_hash=font_manifest_hash,
            theme_version=theme_version,
            export_policy=export_policy,
        )

    def enqueue_formal_export(
        self,
        project_id: UUID,
        presentation_id: UUID,
        *,
        format: str = "pptx",
        idempotency_key: str | None = None,
    ) -> BackgroundJob:
        key = idempotency_key or f"delivery_export:{presentation_id}:{format}"
        return self._jobs.create(
            project_id,
            BackgroundJobKind.ARTIFACT,
            label=f"正式导出 · {format.upper()}",
            payload={
                "presentation_id": str(presentation_id),
                "format": format,
            },
            message="queued for formal delivery export",
            idempotency_key=key,
        )

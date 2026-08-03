"""/delivery — export records and delivery audit facade."""

from __future__ import annotations

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

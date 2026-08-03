"""/render — long-running render/export work goes through Jobs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.api.jobs import JobsApi
from archium.domain.background_job import BackgroundJob, BackgroundJobKind


class RenderApi:
    """Enqueue render-related work; progress via JobsApi."""

    def __init__(self, session: Session) -> None:
        self._jobs = JobsApi(session)

    def enqueue_pptx_export(
        self,
        project_id: UUID,
        presentation_id: UUID,
        *,
        idempotency_key: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> BackgroundJob:
        payload = {"presentation_id": str(presentation_id), **dict(extra or {})}
        key = idempotency_key or f"render_pptx:{presentation_id}"
        return self._jobs.create(
            project_id,
            BackgroundJobKind.ARTIFACT,
            label="导出 PPTX",
            payload=payload,
            message="queued for pptx export",
            idempotency_key=key,
        )

    def enqueue_preview(
        self,
        project_id: UUID,
        presentation_id: UUID,
        *,
        slide_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> BackgroundJob:
        payload: dict[str, Any] = {"presentation_id": str(presentation_id)}
        if slide_id is not None:
            payload["slide_id"] = str(slide_id)
        key = idempotency_key or (
            f"render_preview:{slide_id}" if slide_id else f"render_preview:{presentation_id}"
        )
        return self._jobs.create(
            project_id,
            BackgroundJobKind.GENERIC,
            label="生成预览",
            payload=payload,
            message="queued for preview",
            idempotency_key=key,
        )

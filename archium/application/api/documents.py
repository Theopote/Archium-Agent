"""/documents — ingest + list + enqueue analyze jobs."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.api.jobs import JobsApi
from archium.application.ingestion_service import ImportItemResult, IngestionService
from archium.config.settings import Settings
from archium.domain.background_job import BackgroundJob, BackgroundJobKind
from archium.domain.document import SourceDocument


class DocumentsApi:
    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._ingestion = IngestionService(session, settings=settings)
        self._jobs = JobsApi(session)

    def list(self, project_id: UUID) -> list[SourceDocument]:
        return self._ingestion.list_documents(project_id)

    def get(self, document_id: UUID) -> SourceDocument | None:
        return self._ingestion.get_document(document_id)

    def upload_file(
        self,
        project_id: UUID,
        source_path: Path,
        *,
        actor_id: str | None = None,
    ) -> ImportItemResult:
        return self._ingestion.import_file(project_id, source_path, actor_id=actor_id)

    def enqueue_analyze(
        self,
        project_id: UUID,
        *,
        path: str,
        document_id: UUID | None = None,
        filename: str = "",
        idempotency_key: str | None = None,
    ) -> BackgroundJob:
        payload: dict[str, object] = {"path": path}
        if document_id is not None:
            payload["document_id"] = str(document_id)
        if filename:
            payload["filename"] = filename
        key = idempotency_key or (
            f"document_analyze:{document_id}" if document_id is not None else None
        )
        return self._jobs.create(
            project_id,
            BackgroundJobKind.DOCUMENT_ANALYZE,
            label=f"分析 · {filename or Path(path).name}",
            payload=payload,
            message="queued for analysis",
            idempotency_key=key,
        )

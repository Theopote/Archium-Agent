"""Background job worker — claim + dispatch one unit of work."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.application.background_job_service import BackgroundJobService
from archium.application.cad_bim_analysis import analyze_cad_bim_file, is_cad_bim_path
from archium.application.cad_spatial_fact_materializer import (
    materialize_cad_spatial_facts,
    merge_cad_analysis_into_document,
)
from archium.domain.background_job import BackgroundJob, BackgroundJobKind, BackgroundJobStatus
from archium.infrastructure.database.repositories import DocumentRepository


class BackgroundJobWorker:
    """Inline / process worker. Call ``process_once`` from a loop or test."""

    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._session = session
        self._jobs = BackgroundJobService(session)

    def process_once(self) -> BackgroundJob | None:
        job = self._jobs.claim_next()
        if job is None:
            return None
        if job.status == BackgroundJobStatus.CANCELLED or job.cancel_requested:
            if job.status != BackgroundJobStatus.CANCELLED:
                return self._jobs.cancel(job.id, message="cancelled before run")
            return job
        try:
            if self._jobs.is_cancel_requested(job.id):
                return self._jobs.cancel(job.id, message="cancelled")
            self._jobs.set_progress(job.id, 20, message="dispatching")
            if self._jobs.is_cancel_requested(job.id):
                return self._jobs.cancel(job.id, message="cancelled")
            result = self._dispatch(job)
            if self._jobs.is_cancel_requested(job.id):
                return self._jobs.cancel(job.id, message="cancelled")
            return self._jobs.complete(job.id, result=result, message="completed")
        except Exception as exc:
            return self._jobs.fail(job.id, str(exc))

    def _dispatch(self, job: BackgroundJob) -> dict[str, object]:
        if job.kind == BackgroundJobKind.DOCUMENT_ANALYZE:
            return self._handle_document_analyze(job)
        if job.kind in {
            BackgroundJobKind.WORKFLOW,
            BackgroundJobKind.ARTIFACT,
            BackgroundJobKind.GENERIC,
        }:
            # Placeholder ack — real workflow/artifact runners remain separate adapters.
            return {
                "acknowledged": True,
                "kind": job.kind.value,
                "payload_keys": sorted(str(k) for k in job.payload),
            }
        return {"acknowledged": True, "kind": job.kind.value}

    def _handle_document_analyze(self, job: BackgroundJob) -> dict[str, object]:
        raw_path = str(job.payload.get("path") or job.payload.get("file_path") or "").strip()
        if not raw_path:
            raise ValueError("document_analyze requires payload.path")
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(f"file not found: {path}")
        self._jobs.set_progress(job.id, 50, message=f"analyzing {path.name}")
        if is_cad_bim_path(path):
            analysis = analyze_cad_bim_file(path)
            payload: dict[str, object] = {
                "document_type": analysis.document_type.value,
                "format": analysis.format,
                "metadata": analysis.as_metadata(),
                "summary": analysis.summary_text(),
            }
            raw_doc_id = str(job.payload.get("document_id") or "").strip()
            if raw_doc_id:
                docs = DocumentRepository(self._session)
                document = docs.get_document(UUID(raw_doc_id))
                if document is not None:
                    document = merge_cad_analysis_into_document(document, analysis)
                    docs.update_document(document)
                    created = materialize_cad_spatial_facts(
                        self._session,
                        job.project_id,
                        document,
                        analysis=analysis,
                    )
                    payload["document_id"] = str(document.id)
                    payload["facts_created"] = created
                    payload["facts_materialized"] = True
            return payload
        return {
            "document_type": path.suffix.lower().lstrip(".") or "other",
            "file_name": path.name,
            "size_bytes": path.stat().st_size,
            "parse_depth": "metadata_only",
            "summary": f"已登记文件 {path.name}（非 CAD/BIM 深度解析路径）",
        }

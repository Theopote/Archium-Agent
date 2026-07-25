"""Background job worker — claim + dispatch one unit of work."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from archium.application.background_job_service import BackgroundJobService
from archium.application.cad_bim_analysis import analyze_cad_bim_file, is_cad_bim_path
from archium.domain.background_job import BackgroundJob, BackgroundJobKind


class BackgroundJobWorker:
    """Inline / process worker. Call ``process_once`` from a loop or test."""

    def __init__(self, session: Session) -> None:
        self._jobs = BackgroundJobService(session)

    def process_once(self) -> BackgroundJob | None:
        job = self._jobs.claim_next()
        if job is None:
            return None
        try:
            self._jobs.set_progress(job.id, 20, message="dispatching")
            result = self._dispatch(job)
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
                "payload_keys": sorted(str(k) for k in job.payload.keys()),
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
            return {
                "document_type": analysis.document_type.value,
                "format": analysis.format,
                "metadata": analysis.as_metadata(),
                "summary": analysis.summary_text(),
            }
        return {
            "document_type": path.suffix.lower().lstrip(".") or "other",
            "file_name": path.name,
            "size_bytes": path.stat().st_size,
            "parse_depth": "metadata_only",
            "summary": f"已登记文件 {path.name}（非 CAD/BIM 深度解析路径）",
        }

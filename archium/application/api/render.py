"""/render — sync render + async enqueue for PPTX/PDF/preview."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from archium.application.api.jobs import JobsApi
from archium.application.formal_pptx_export_service import (
    FormalPptxExportResult,
    FormalPptxExportService,
)
from archium.application.unit_of_work import SessionLike, session_of
from archium.config.settings import Settings, get_settings
from archium.domain.background_job import BackgroundJob, BackgroundJobKind
from archium.domain.export_fidelity import ChartExportMode
from archium.domain.render import RenderResult
from archium.exceptions import WorkflowError
from archium.infrastructure.renderers.pptx_pdf import convert_pptx_to_pdf


class RenderApi:
    """Render execution boundary: sync formal PPTX/PDF + async job enqueue."""

    def __init__(self, session: SessionLike, *, settings: Settings | None = None) -> None:
        session = session_of(session)
        self._session = session
        self._settings = settings
        self._jobs = JobsApi(session)

    def _resolved_settings(self, settings: Settings | None = None) -> Settings:
        return settings or self._settings or get_settings()

    def export_editable_pptx(
        self,
        presentation_id: UUID,
        *,
        chart_export_mode: ChartExportMode | None = None,
        allow_legacy_spec_fallback: bool | None = None,
        settings: Settings | None = None,
        actor_id: str | None = None,
    ) -> FormalPptxExportResult:
        """Formal editable PPTX from RenderScene (DOM-003)."""
        return FormalPptxExportService(
            self._session,
            settings=self._resolved_settings(settings),
        ).export_editable_pptx(
            presentation_id,
            chart_export_mode=chart_export_mode,
            allow_legacy_spec_fallback=allow_legacy_spec_fallback,
            actor_id=actor_id,
        )

    def export_editable_pptx_result(
        self,
        presentation_id: UUID,
        *,
        chart_export_mode: ChartExportMode | None = None,
        allow_legacy_spec_fallback: bool | None = False,
        settings: Settings | None = None,
        actor_id: str | None = None,
    ) -> RenderResult:
        """UI-friendly wrapper returning ``RenderResult``."""
        formal = self.export_editable_pptx(
            presentation_id,
            chart_export_mode=chart_export_mode,
            allow_legacy_spec_fallback=allow_legacy_spec_fallback,
            settings=settings,
            actor_id=actor_id,
        )
        return RenderResult(
            editable_pptx_path=formal.path,
            warnings=list(formal.warnings),
        )

    def export_pdf(
        self,
        presentation_id: UUID,
        *,
        chart_export_mode: ChartExportMode | None = None,
        settings: Settings | None = None,
        actor_id: str | None = None,
    ) -> RenderResult:
        """Export formal PPTX then convert to PDF (LibreOffice)."""
        pptx_result = self.export_editable_pptx_result(
            presentation_id,
            chart_export_mode=chart_export_mode,
            allow_legacy_spec_fallback=False,
            settings=settings,
            actor_id=actor_id,
        )
        pptx_path = pptx_result.editable_pptx_path
        if pptx_path is None:
            raise WorkflowError("PPTX 导出失败，无法继续生成 PDF。")
        pdf_path = convert_pptx_to_pdf(pptx_path, pptx_path.parent)
        if pdf_path is None:
            pptx_result.warnings.append(
                "未检测到 LibreOffice，无法将 PPTX 转为 PDF。请安装 LibreOffice 后重试。"
            )
            return pptx_result
        return RenderResult(
            editable_pptx_path=pptx_path,
            pdf_path=pdf_path,
            warnings=list(pptx_result.warnings),
        )

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

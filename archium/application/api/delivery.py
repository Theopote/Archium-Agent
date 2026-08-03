"""/delivery — sync re-export, export records, and delivery audit facade."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.api.jobs import JobsApi
from archium.application.api.render import RenderApi
from archium.application.delivery_record_service import DeliveryRecordService
from archium.application.export_service import PresentationExportService
from archium.config.settings import Settings, get_settings
from archium.domain.background_job import BackgroundJob, BackgroundJobKind
from archium.domain.delivery_record import DeliveryRecord
from archium.domain.export_fidelity import ChartExportMode
from archium.domain.render import RenderResult
from archium.application.formal_pptx_export_service import FormalPptxExportResult


class DeliveryApi:
    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings
        self._records = DeliveryRecordService(session)
        self._jobs = JobsApi(session)
        self._render = RenderApi(session, settings=settings)

    def _resolved_settings(self, settings: Settings | None = None) -> Settings:
        return settings or self._settings or get_settings()

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

    def export_formal_pptx(
        self,
        presentation_id: UUID,
        *,
        chart_export_mode: ChartExportMode | None = None,
        allow_legacy_spec_fallback: bool | None = False,
        settings: Settings | None = None,
        actor_id: str | None = None,
    ) -> FormalPptxExportResult:
        """Delivery-facing formal PPTX (delegates to RenderApi)."""
        return self._render.export_editable_pptx(
            presentation_id,
            chart_export_mode=chart_export_mode,
            allow_legacy_spec_fallback=allow_legacy_spec_fallback,
            settings=settings,
            actor_id=actor_id,
        )

    def export_formal_pptx_result(
        self,
        presentation_id: UUID,
        *,
        chart_export_mode: ChartExportMode | None = None,
        allow_legacy_spec_fallback: bool | None = False,
        settings: Settings | None = None,
        actor_id: str | None = None,
    ) -> RenderResult:
        return self._render.export_editable_pptx_result(
            presentation_id,
            chart_export_mode=chart_export_mode,
            allow_legacy_spec_fallback=allow_legacy_spec_fallback,
            settings=settings,
            actor_id=actor_id,
        )

    def export_pdf(
        self,
        presentation_id: UUID,
        *,
        chart_export_mode: ChartExportMode | None = None,
        settings: Settings | None = None,
        actor_id: str | None = None,
    ) -> RenderResult:
        return self._render.export_pdf(
            presentation_id,
            chart_export_mode=chart_export_mode,
            settings=settings,
            actor_id=actor_id,
        )

    def reexport(
        self,
        presentation_id: UUID,
        *,
        export_json: bool = True,
        export_marp: bool = True,
        export_presentation_spec: bool = False,
        export_editable_pptx: bool = False,
        export_pptx: bool = False,
        export_pdf: bool = False,
        settings: Settings | None = None,
    ) -> RenderResult:
        """Multi-artifact re-export (JSON / Marp / formal PPTX / Marp PPTX+PDF)."""
        return PresentationExportService(
            self._session,
            settings=self._resolved_settings(settings),
        ).reexport(
            presentation_id,
            export_json=export_json,
            export_marp=export_marp,
            export_presentation_spec=export_presentation_spec,
            export_editable_pptx=export_editable_pptx,
            export_pptx=export_pptx,
            export_pdf=export_pdf,
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

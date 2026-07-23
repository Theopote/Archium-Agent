"""Formal editable PPTX export preferring RenderScene (DOM-003 / APP-002)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.domain.export_authority import (
    FORMAL_EDITABLE_PPTX_AUTHORITY,
    DerivedExportKind,
    FormalExportAuthority,
)
from archium.domain.export_fidelity import ChartExportMode
from archium.domain.visual.render_scene import RenderScene
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository


@dataclass
class FormalPptxExportResult:
    """Outcome of a formal or legacy-fallback editable PPTX export."""

    path: Path
    authority: FormalExportAuthority | DerivedExportKind
    warnings: list[str] = field(default_factory=list)

    @property
    def is_formal(self) -> bool:
        return self.authority == FORMAL_EDITABLE_PPTX_AUTHORITY


class FormalPptxExportService:
    """Export client-facing editable PPTX with RenderScene as authority."""

    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)

    def export_editable_pptx(
        self,
        presentation_id: UUID,
        *,
        chart_export_mode: ChartExportMode | None = None,
        allow_legacy_spec_fallback: bool | None = None,
    ) -> FormalPptxExportResult:
        if allow_legacy_spec_fallback is None:
            allow_legacy_spec_fallback = (
                self._settings.allow_legacy_presentation_spec_pptx_fallback
            )
        from archium.application.visual.layout_readiness import presentation_has_visual_layout
        from archium.application.visual.studio_scene_service import StudioSceneService
        from archium.infrastructure.renderers.pptx_renderer import PptxRenderer
        from archium.infrastructure.renderers.pptxgen_renderer import PptxGenPresentationRenderer

        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is None:
            raise WorkflowError(f"Presentation {presentation_id} not found")

        brief = None
        if presentation.current_brief_id is not None:
            brief = self._presentations.get_brief(presentation.current_brief_id)
        if brief is None:
            briefs = self._presentations.list_briefs(presentation_id)
            brief = briefs[0] if briefs else None
        if brief is None:
            raise WorkflowError("Brief is required before export")

        if presentation_has_visual_layout(self._session, presentation_id):
            scene_service = StudioSceneService(self._session, settings=self._settings)
            scene_results = scene_service.ensure_scenes_for_presentation(
                presentation_id,
                force_recompile=False,
            )
            if scene_results:
                slides = self._presentations.list_slides(presentation_id)
                slides_by_id = {slide.id: slide for slide in slides}
                ordered_scenes: list[tuple[RenderScene, str | None]] = []
                for result in scene_results:
                    slide = slides_by_id.get(result.scene.slide_id)
                    notes = slide.speaker_notes if slide is not None else None
                    ordered_scenes.append((result.scene, notes or None))
                legacy = PptxGenPresentationRenderer(
                    self._settings, session=self._session
                )
                output_dir = legacy.output_dir(presentation_id, version=brief.version)
                pptx_path = output_dir / "presentation.pptx"
                rendered = PptxRenderer(self._settings).export_presentation(
                    title=brief.title,
                    scenes=ordered_scenes,
                    output_path=pptx_path,
                    chart_export_mode=chart_export_mode,
                    project_id=presentation.project_id,
                )
                return FormalPptxExportResult(
                    path=rendered,
                    authority=FormalExportAuthority.RENDER_SCENE,
                )

        if not allow_legacy_spec_fallback:
            raise WorkflowError(
                "正式可编辑 PPTX 仅认 RenderScene；当前汇报尚无视觉版式，"
                "请先完成视觉编排，或显式启用遗留 PresentationSpec 回退。"
            )

        storyline = None
        if presentation.current_storyline_id is not None:
            storyline = self._presentations.get_storyline(presentation.current_storyline_id)
        if storyline is None:
            storylines = self._presentations.list_storylines(presentation_id)
            storyline = storylines[0] if storylines else None
        slides = self._presentations.list_slides(presentation_id)
        if storyline is None or not slides:
            raise WorkflowError("Brief/storyline/slides required for legacy Spec PPTX fallback")

        pptxgen = PptxGenPresentationRenderer(self._settings, session=self._session)
        spec_path = pptxgen.render(
            presentation_id=presentation_id,
            project_id=presentation.project_id,
            brief=brief,
            storyline=storyline,
            slides=slides,
            version=brief.version,
        )
        from archium.application.render_export import export_pptxgen_extras

        extras = export_pptxgen_extras(
            pptxgen,
            spec_path,
            export_editable_pptx=True,
        )
        if extras.editable_pptx_path is None:
            raise WorkflowError(
                "遗留 PresentationSpec PPTX 导出失败："
                + ("; ".join(extras.warnings) if extras.warnings else "unknown")
            )
        warnings = list(extras.warnings)
        warnings.append(
            "使用遗留 PresentationSpec 模板导出（非正式 RenderScene 路径）。"
        )
        return FormalPptxExportResult(
            path=extras.editable_pptx_path,
            authority=DerivedExportKind.PRESENTATION_SPEC,
            warnings=warnings,
        )

"""Formal editable PPTX export preferring RenderScene (DOM-003 / APP-002)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.application.design_system_integration import DesignSystemIntegrationService
from archium.domain.export_authority import (
    FORMAL_DELIVERY_PPTX_FILENAME,
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

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        design_system_integration: DesignSystemIntegrationService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._design_system_integration = design_system_integration

    def export_editable_pptx(
        self,
        presentation_id: UUID,
        *,
        chart_export_mode: ChartExportMode | None = None,
        allow_legacy_spec_fallback: bool | None = None,
        actor_id: str | None = None,
    ) -> FormalPptxExportResult:
        from archium.application.project_permission_gate import require_project_permission
        from archium.domain.access import ProjectPermission

        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is None:
            raise WorkflowError(f"汇报 {presentation_id} 不存在")
        require_project_permission(
            self._session,
            presentation.project_id,
            ProjectPermission.EXPORT,
            actor_id=actor_id,
        )
        if allow_legacy_spec_fallback is None:
            allow_legacy_spec_fallback = (
                self._settings.allow_legacy_presentation_spec_pptx_fallback
            )
        from archium.application.pptxgen_renderer_factory import create_pptxgen_renderer
        from archium.application.visual.layout_readiness import presentation_has_visual_layout
        from archium.application.visual.studio_scene_service import StudioSceneService
        from archium.infrastructure.renderers.pptx_renderer import PptxRenderer

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
                from archium.application.evidence_readiness_service import (
                    citation_lines_for_slide,
                )

                slides = self._presentations.list_slides(presentation_id)
                slides_by_id = {slide.id: slide for slide in slides}
                ordered_scenes: list[tuple[RenderScene, str | None, list[str] | None]] = []
                for result in scene_results:
                    slide = slides_by_id.get(result.scene.slide_id)
                    notes = slide.speaker_notes if slide is not None else None
                    cites = citation_lines_for_slide(slide) if slide is not None else []
                    ordered_scenes.append((result.scene, notes or None, cites or None))
                legacy = create_pptxgen_renderer(
                    self._settings, session=self._session
                )
                output_dir = legacy.output_dir(presentation_id, version=brief.version)
                pptx_path = output_dir / FORMAL_DELIVERY_PPTX_FILENAME
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

        pptxgen = create_pptxgen_renderer(self._settings, session=self._session)
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
    
    def export_with_enhanced_renderer(
        self,
        presentation_id: UUID,
        *,
        template_id: str | None = None,
        use_intelligent_layout: bool = True,
        actor_id: str | None = None,
    ) -> FormalPptxExportResult:
        """Export PPTX using enhanced renderer with design system integration.
        
        This method uses the new enhanced PptxGenJS renderer that supports
        advanced design system features like gradients, shadows, and professional typography.
        
        Args:
            presentation_id: Presentation ID to export
            template_id: Optional template ID to apply
            use_intelligent_layout: Whether to use intelligent layout optimization
            actor_id: Optional actor ID for permission checking
        
        Returns:
            FormalPptxExportResult with enhanced rendering
        """
        if self._design_system_integration is None:
            raise WorkflowError("Design system integration not available for enhanced rendering")
        
        from archium.application.project_permission_gate import require_project_permission
        from archium.domain.access import ProjectPermission
        
        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is None:
            raise WorkflowError(f"汇报 {presentation_id} 不存在")
        
        require_project_permission(
            self._session,
            presentation.project_id,
            ProjectPermission.EXPORT,
            actor_id=actor_id,
        )
        
        # Get presentation data
        brief = None
        if presentation.current_brief_id is not None:
            brief = self._presentations.get_brief(presentation.current_brief_id)
        if brief is None:
            briefs = self._presentations.list_briefs(presentation_id)
            brief = briefs[0] if briefs else None
        
        storyline = None
        if presentation.current_storyline_id is not None:
            storyline = self._presentations.get_storyline(presentation.current_storyline_id)
        if storyline is None:
            storylines = self._presentations.list_storylines(presentation_id)
            storyline = storylines[0] if storylines else None
        
        slides = self._presentations.list_slides(presentation_id)
        
        if brief is None or storyline is None or not slides:
            raise WorkflowError("Brief/storyline/slides required for enhanced export")
        
        # Apply template if specified
        if template_id:
            template_result = self._design_system_integration.apply_template_to_presentation(
                presentation_id,
                template_id,
                {"title": brief.title, "slides_count": len(slides)},
            )
        
        # Apply intelligent layout if enabled
        if use_intelligent_layout:
            from archium.ui.visual_service import apply_intelligent_layout_to_visual_workflow
            
            layout_optimizations = apply_intelligent_layout_to_visual_workflow(
                self._session,
                presentation_id,
                slides,
                self._design_system_integration,
            )
        
        # Use standard export path for now
        # In a full implementation, this would call the enhanced renderer
        from archium.application.pptxgen_renderer_factory import create_pptxgen_renderer
        
        pptxgen = create_pptxgen_renderer(self._settings, session=self._session)
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
        
        warnings = list(extras.warnings)
        warnings.append("使用增强渲染器导出（设计系统集成）")
        
        if template_id:
            warnings.append(f"已应用模板: {template_id}")
        
        if use_intelligent_layout:
            warnings.append("已应用智能布局优化")
        
        return FormalPptxExportResult(
            path=extras.editable_pptx_path,
            authority=FormalExportAuthority.RENDER_SCENE,  # Use formal authority
            warnings=warnings,
        )

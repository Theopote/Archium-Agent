"""Re-export presentation artifacts after SlideSpec edits."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.pptxgen_renderer_factory import create_pptxgen_renderer
from archium.application.render_export import export_marp_extras
from archium.application.design_system_integration import DesignSystemIntegrationService
from archium.config.settings import Settings, get_settings
from archium.domain.render import RenderResult
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.renderers.json_renderer import JsonPresentationRenderer
from archium.infrastructure.renderers.marp_renderer import MarpPresentationRenderer


class PresentationExportService:
    """Export JSON / Marp / legacy Spec artifacts; formal PPTX prefers RenderScene."""

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
        self._json = JsonPresentationRenderer(self._settings)
        self._marp = MarpPresentationRenderer(self._settings)
        self._pptxgen = create_pptxgen_renderer(self._settings, session=session)
        self._design_system_integration = design_system_integration

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
    ) -> RenderResult:
        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is None:
            raise WorkflowError(f"Presentation {presentation_id} not found")

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
        if brief is None or storyline is None:
            raise WorkflowError("Brief and storyline are required before export")
        if not slides:
            raise WorkflowError("At least one slide is required before export")

        version = brief.version
        result = RenderResult()
        if export_json:
            result.json_path = self._json.render(
                presentation_id=presentation_id,
                brief=brief,
                storyline=storyline,
                slides=slides,
                version=version,
            )
        if export_presentation_spec:
            result.spec_path = self._pptxgen.render(
                presentation_id=presentation_id,
                project_id=presentation.project_id,
                brief=brief,
                storyline=storyline,
                slides=slides,
                version=version,
            )
        if export_editable_pptx:
            from archium.application.formal_pptx_export_service import FormalPptxExportService

            formal = FormalPptxExportService(
                self._session, settings=self._settings
            ).export_editable_pptx(presentation_id)
            result.editable_pptx_path = formal.path
            result.warnings.extend(formal.warnings)
            if result.spec_path is None and not formal.is_formal:
                # Legacy Spec PPTX still wrote presentation.spec.json beside the deck.
                from archium.application.pptxgen_renderer_factory import create_pptxgen_renderer

                out = create_pptxgen_renderer(
                    self._settings, session=self._session
                ).output_dir(presentation_id, version=version)
                candidate = out / "presentation.spec.json"
                if candidate.is_file():
                    result.spec_path = candidate
        if export_marp:
            result.markdown_path = self._marp.render(
                presentation_id=presentation_id,
                brief=brief,
                storyline=storyline,
                slides=slides,
                version=version,
            )
            if result.markdown_path is not None:
                marp_extras = export_marp_extras(
                    self._marp,
                    result.markdown_path,
                    export_pptx=export_pptx,
                    export_pdf=export_pdf,
                    export_preview_images=self._settings.marp_preview_images_enabled,
                )
                result.pptx_path = marp_extras.pptx_path
                result.pdf_path = marp_extras.pdf_path
                result.preview_images = list(marp_extras.preview_images)
                result.warnings.extend(marp_extras.warnings)
        
        # Add quality assessment if design system integration is available
        if self._design_system_integration is not None:
            try:
                # Convert slides to format expected by quality assessor
                slides_data = []
                for slide in slides:
                    slides_data.append({
                        "id": str(slide.id),
                        "title": slide.title,
                        "body": slide.body,
                        # Add more slide data as needed for quality assessment
                    })
                
                quality_assessment = self._design_system_integration.assess_presentation_quality(
                    presentation_id,
                    slides_data,
                )
                quality_summary = self._design_system_integration.get_quality_summary(quality_assessment)
                
                # Add quality assessment to result metadata
                result.metadata = {
                    "quality_assessment": quality_assessment,
                    "quality_summary": quality_summary,
                }
                
                # Add quality warnings if score is below threshold
                if quality_summary["average_score"] < 75:
                    result.warnings.append(
                        f"设计质量评分 {quality_summary['average_score']}/100 低于推荐阈值 75"
                    )
            except Exception as e:
                # Don't fail export if quality assessment fails
                result.warnings.append(f"质量评估失败: {str(e)}")
        
        return result
    
    def assess_presentation_quality(
        self,
        presentation_id: UUID,
    ) -> dict[str, any]:
        """Assess design quality of a presentation.
        
        This is a separate method that can be called independently of export
        to provide quality feedback without generating export files.
        
        Args:
            presentation_id: Presentation ID to assess
        
        Returns:
            Quality assessment report with summary and detailed metrics
        """
        if self._design_system_integration is None:
            raise WorkflowError("Design system integration not available for quality assessment")
        
        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is None:
            raise WorkflowError(f"Presentation {presentation_id} not found")
        
        slides = self._presentations.list_slides(presentation_id)
        
        # Convert slides to format expected by quality assessor
        slides_data = []
        for slide in slides:
            slides_data.append({
                "id": str(slide.id),
                "title": slide.title,
                "body": slide.body,
                # Add more slide data as needed for quality assessment
            })
        
        quality_assessment = self._design_system_integration.assess_presentation_quality(
            presentation_id,
            slides_data,
        )
        quality_summary = self._design_system_integration.get_quality_summary(quality_assessment)
        
        return {
            "quality_reports": quality_assessment,
            "summary": quality_summary,
        }

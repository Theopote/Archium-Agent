"""Re-export presentation artifacts after SlideSpec edits."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.render_export import export_marp_extras, export_pptxgen_extras
from archium.config.settings import Settings, get_settings
from archium.domain.render import RenderResult
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.renderers.json_renderer import JsonPresentationRenderer
from archium.infrastructure.renderers.marp_renderer import MarpPresentationRenderer
from archium.infrastructure.renderers.pptxgen_renderer import PptxGenPresentationRenderer


class PresentationExportService:
    """Export JSON / Marp / PresentationSpec artifacts from persisted presentation data."""

    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._json = JsonPresentationRenderer(self._settings)
        self._marp = MarpPresentationRenderer(self._settings)
        self._pptxgen = PptxGenPresentationRenderer(self._settings, session=session)

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
        if export_presentation_spec or export_editable_pptx:
            result.spec_path = self._pptxgen.render(
                presentation_id=presentation_id,
                project_id=presentation.project_id,
                brief=brief,
                storyline=storyline,
                slides=slides,
                version=version,
            )
            if export_editable_pptx and result.spec_path is not None:
                extras = export_pptxgen_extras(
                    self._pptxgen,
                    result.spec_path,
                    export_editable_pptx=True,
                )
                result.editable_pptx_path = extras.editable_pptx_path
                result.warnings.extend(extras.warnings)
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
        return result

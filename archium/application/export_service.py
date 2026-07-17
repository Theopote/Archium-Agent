"""Re-export presentation artifacts after SlideSpec edits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.renderers.json_renderer import JsonPresentationRenderer
from archium.infrastructure.renderers.marp_renderer import MarpPresentationRenderer


@dataclass
class ExportPaths:
    json_path: Path | None = None
    marp_md_path: Path | None = None
    marp_pptx_path: Path | None = None


class PresentationExportService:
    """Export JSON / Marp artifacts from persisted presentation data."""

    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._json = JsonPresentationRenderer(self._settings)
        self._marp = MarpPresentationRenderer(self._settings)

    def reexport(
        self,
        presentation_id: UUID,
        *,
        export_json: bool = True,
        export_marp: bool = True,
        export_pptx: bool = False,
    ) -> ExportPaths:
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
        paths = ExportPaths()
        if export_json:
            paths.json_path = self._json.render(
                presentation_id=presentation_id,
                brief=brief,
                storyline=storyline,
                slides=slides,
                version=version,
            )
        if export_marp:
            paths.marp_md_path = self._marp.render(
                presentation_id=presentation_id,
                brief=brief,
                storyline=storyline,
                slides=slides,
                version=version,
            )
            if export_pptx and paths.marp_md_path is not None:
                paths.marp_pptx_path = self._marp.export_pptx(paths.marp_md_path)
        return paths

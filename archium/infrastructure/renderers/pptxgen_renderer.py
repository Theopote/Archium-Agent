"""PptxGenJS renderer for editable PPTX export from PresentationSpec."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.presentation_spec import PresentationSpec
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import AssetRepository
from archium.infrastructure.renderers.pptxgen_cli import PptxGenCliRunner
from archium.infrastructure.renderers.presentation_spec_builder import build_presentation_spec


class PptxGenPresentationRenderer:
    """Export brief/storyline/slides as PresentationSpec JSON and editable PPTX."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        session: Session | None = None,
        theme: str = "architecture-board",
    ) -> None:
        self._settings = settings or get_settings()
        self._session = session
        self._theme = theme
        self._cli = PptxGenCliRunner(self._settings)

    def output_dir(self, presentation_id: UUID, version: int = 1) -> Path:
        return (
            self._settings.output_path
            / "presentations"
            / str(presentation_id)
            / f"v{version}"
        )

    def build_spec(
        self,
        *,
        presentation_id: UUID,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        slides: list[SlideSpec],
        version: int = 1,
    ) -> PresentationSpec:
        return build_presentation_spec(
            presentation_id=presentation_id,
            brief=brief,
            storyline=storyline,
            slides=slides,
            version=version,
            theme=self._theme,
            asset_paths=self._resolve_asset_paths(project_id, slides),
        )

    def render(
        self,
        *,
        presentation_id: UUID,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        slides: list[SlideSpec],
        version: int = 1,
    ) -> Path:
        """Write presentation.spec.json and return its path."""
        spec = self.build_spec(
            presentation_id=presentation_id,
            project_id=project_id,
            brief=brief,
            storyline=storyline,
            slides=slides,
            version=version,
        )
        output_dir = self.output_dir(presentation_id, version)
        output_dir.mkdir(parents=True, exist_ok=True)
        spec_path = output_dir / "presentation.spec.json"
        spec_path.write_text(
            spec.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return spec_path

    def export_pptx(
        self,
        spec_path: Path,
        *,
        output_path: Path | None = None,
    ) -> Path:
        target = output_path or spec_path.with_name("presentation.editable.pptx")
        return self._cli.render(spec_path, target)

    def render_and_export_pptx(
        self,
        *,
        presentation_id: UUID,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        slides: list[SlideSpec],
        version: int = 1,
    ) -> tuple[Path, Path]:
        spec_path = self.render(
            presentation_id=presentation_id,
            project_id=project_id,
            brief=brief,
            storyline=storyline,
            slides=slides,
            version=version,
        )
        pptx_path = self.export_pptx(spec_path)
        return spec_path, pptx_path

    def _resolve_asset_paths(
        self,
        project_id: UUID,
        slides: list[SlideSpec],
    ) -> dict[UUID, Path]:
        if self._session is None:
            return {}

        asset_ids: set[UUID] = set()
        for slide in slides:
            for requirement in slide.visual_requirements:
                asset_id = requirement.primary_asset_id
                if asset_id is not None:
                    asset_ids.add(asset_id)
        if not asset_ids:
            return {}

        repo = AssetRepository(self._session)
        resolved: dict[UUID, Path] = {}
        for asset_id in asset_ids:
            asset = repo.get_by_id(asset_id)
            if asset is None or asset.project_id != project_id:
                continue
            path = Path(asset.path)
            if not path.is_absolute():
                path = self._settings.project_storage_path / str(project_id) / path
            resolved[asset_id] = path
        return resolved

"""PptxGenJS renderer for editable PPTX export from PresentationSpec."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.image_search_settings_service import ImageSearchSettingsService
from archium.application.visual_fallback_service import VisualFallbackService
from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.fact import ProjectFact
from archium.domain.fallback_image import FallbackImage
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.presentation_spec import PresentationSpec
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import AssetRepository, FactRepository
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
        output_dir = self.output_dir(presentation_id, version)
        asset_paths = self._resolve_asset_paths(project_id, slides)
        facts = self._resolve_project_facts(project_id)
        fallback_images: dict[tuple[UUID, int], FallbackImage] = {}
        if self._session is not None:
            image_search_preferences = ImageSearchSettingsService(self._session).get_preferences(
                base_settings=self._settings,
            )
            fallback_images = VisualFallbackService(
                self._session,
                settings=self._settings,
                pexels_session_api_key=_resolve_pexels_session_api_key(),
                unsplash_session_api_key=_resolve_unsplash_session_api_key(),
                image_search_preferences=image_search_preferences,
            ).resolve_export_images(
                project_id,
                slides,
                output_dir=output_dir,
                base_paths=asset_paths,
                facts=facts,
            )
            if self._session.new:
                self._session.commit()
        return build_presentation_spec(
            presentation_id=presentation_id,
            brief=brief,
            storyline=storyline,
            slides=slides,
            version=version,
            theme=self._theme,
            asset_paths=asset_paths,
            assets=self._resolve_assets(project_id, slides),
            facts=facts,
            fallback_images=fallback_images,
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

    def _resolve_assets(
        self,
        project_id: UUID,
        slides: list[SlideSpec],
    ) -> dict[UUID, Asset]:
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
        resolved: dict[UUID, Asset] = {}
        for asset_id in asset_ids:
            asset = repo.get_by_id(asset_id)
            if asset is not None and asset.project_id == project_id:
                resolved[asset_id] = asset
        return resolved

    def _resolve_project_facts(self, project_id: UUID) -> list[ProjectFact]:
        if self._session is None:
            return []
        return FactRepository(self._session).list_by_project(project_id)


def _resolve_pexels_session_api_key() -> str | None:
    try:
        import streamlit as st
    except ImportError:
        return None
    value = st.session_state.get("pexels_session_api_key")
    return value if isinstance(value, str) and value else None


def _resolve_unsplash_session_api_key() -> str | None:
    try:
        import streamlit as st
    except ImportError:
        return None
    value = st.session_state.get("unsplash_session_api_key")
    return value if isinstance(value, str) and value else None

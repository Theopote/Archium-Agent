"""Resolve missing slide visuals via relaxed matching, web search, or programmatic diagrams."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.asset_matching_service import rank_assets_for_requirement
from archium.application.image_search_settings_service import ImageSearchPreferences
from archium.application.web_image_asset_service import WebImageAssetService
from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.enums import VisualType
from archium.domain.fact import ProjectFact
from archium.domain.fallback_image import FallbackImage
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import AssetRepository, VisualQAReportRepository
from archium.infrastructure.images.web_search import WebImageSearchService
from archium.infrastructure.renderers.diagram_generator import (
    can_generate_diagram,
    generate_fallback_diagram,
)

FallbackKey = tuple[UUID, int]
_SKIP_TYPES = {VisualType.TEXT_ONLY, VisualType.CHART, VisualType.TABLE}


class VisualFallbackService:
    """Find alternate assets, licensed stock photos, or schematic PNGs for unmatched visuals."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        pexels_session_api_key: str | None = None,
        unsplash_session_api_key: str | None = None,
        image_search_preferences: ImageSearchPreferences | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._image_search_preferences = image_search_preferences
        self._assets = AssetRepository(session)
        self._qa_reports = VisualQAReportRepository(session)
        effective = self._effective_settings
        self._web_assets = WebImageAssetService(session, settings=effective)
        self._web_search = WebImageSearchService(
            effective,
            session_pexels_api_key=pexels_session_api_key,
            session_unsplash_api_key=unsplash_session_api_key,
        )

    @property
    def _effective_settings(self) -> Settings:
        if self._image_search_preferences is None:
            return self._settings
        return self._settings.model_copy(
            update={
                "web_image_search_enabled": self._image_search_preferences.enabled,
                "web_image_search_persist_to_library": (
                    self._image_search_preferences.persist_to_library
                ),
            }
        )

    def resolve_export_images(
        self,
        project_id: UUID,
        slides: list[SlideSpec],
        *,
        output_dir: Path,
        base_paths: dict[UUID, Path],
        facts: list[ProjectFact] | None = None,
    ) -> dict[FallbackKey, FallbackImage]:
        """Return supplemental images keyed by (slide_id, requirement_index)."""
        if not self._settings.visual_fallback_enabled:
            return {}

        assets = self._assets.list_by_project(project_id)
        if not assets and not any(slide.visual_requirements for slide in slides):
            return {}

        qa_reports = self._qa_reports.get_latest_by_asset_ids({asset.id for asset in assets})
        resolved: dict[FallbackKey, FallbackImage] = {}

        for slide in slides:
            for index, requirement in enumerate(slide.visual_requirements):
                if requirement.type in _SKIP_TYPES:
                    continue
                if self._requirement_has_path(requirement, base_paths, resolved, slide.id, index):
                    continue

                matched_path = self._try_relaxed_asset_match(
                    project_id,
                    requirement,
                    assets,
                    qa_reports,
                )
                if matched_path is not None:
                    resolved[(slide.id, index)] = FallbackImage(path=matched_path, generated=False)
                    continue

                web_image = self._try_web_image_search(
                    project_id,
                    slide,
                    requirement,
                    index,
                    output_dir=output_dir,
                    facts=facts,
                )
                if web_image is not None:
                    resolved[(slide.id, index)] = web_image
                    continue

                generated = self._try_generate_diagram(
                    slide,
                    requirement,
                    index,
                    output_dir=output_dir,
                )
                if generated is not None:
                    resolved[(slide.id, index)] = generated

        return resolved

    def _requirement_has_path(
        self,
        requirement: VisualRequirement,
        base_paths: dict[UUID, Path],
        resolved: dict[FallbackKey, FallbackImage],
        slide_id: UUID,
        requirement_index: int,
    ) -> bool:
        if (slide_id, requirement_index) in resolved:
            return True
        asset_id = requirement.primary_asset_id
        if asset_id is None:
            return False
        path = base_paths.get(asset_id)
        return path is not None and path.exists()

    def _try_relaxed_asset_match(
        self,
        project_id: UUID,
        requirement: VisualRequirement,
        assets: list[Asset],
        qa_reports: dict[UUID, object],
    ) -> Path | None:
        if not self._settings.visual_fallback_relaxed_matching:
            return None

        ranked = rank_assets_for_requirement(
            requirement,
            assets,
            min_score=self._settings.visual_fallback_relaxed_min_score,
            top_k=1,
            qa_reports=qa_reports,  # type: ignore[arg-type]
        )
        if not ranked:
            return None

        asset, score = ranked[0]
        path = self._resolve_asset_path(project_id, asset)
        if path.exists() and score >= self._settings.visual_fallback_relaxed_min_score:
            return path
        return None

    def _try_web_image_search(
        self,
        project_id: UUID,
        slide: SlideSpec,
        requirement: VisualRequirement,
        requirement_index: int,
        *,
        output_dir: Path,
        facts: list[ProjectFact] | None,
    ) -> FallbackImage | None:
        web_image = self._web_search.resolve_requirement(
            slide,
            requirement,
            requirement_index,
            output_dir=output_dir,
            facts=facts,
        )
        if web_image is None:
            return None
        return self._web_assets.persist_if_enabled(
            project_id,
            web_image,
            slide=slide,
            requirement=requirement,
            search_query=web_image.search_query or "",
        )

    def _try_generate_diagram(
        self,
        slide: SlideSpec,
        requirement: VisualRequirement,
        requirement_index: int,
        *,
        output_dir: Path,
    ) -> FallbackImage | None:
        if not self._settings.visual_fallback_generate_diagrams:
            return None
        if not can_generate_diagram(requirement.type):
            return None

        filename = f"fallback_{slide.id}_{requirement_index}.png"
        output_path = output_dir / "generated" / filename
        try:
            path = generate_fallback_diagram(
                output_path,
                title=slide.title,
                visual_type=requirement.type,
                description=requirement.description,
                key_points=list(slide.key_points),
                message=slide.message.strip() or None,
            )
        except RuntimeError:
            return None
        return FallbackImage(path=path, generated=True, web_sourced=False)

    def _resolve_asset_path(self, project_id: UUID, asset: Asset) -> Path:
        path = Path(asset.path)
        if path.is_absolute():
            return path
        return self._settings.project_storage_path / str(project_id) / path

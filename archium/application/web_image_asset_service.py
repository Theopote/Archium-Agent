"""Persist web-sourced fallback images into the project asset library."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.fallback_image import FallbackImage
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import AssetRepository

_WEB_IMPORT_DIR = "web_imports"
_METADATA_SOURCE_URL = "web_source_url"


class WebImageAssetService:
    """Copy downloaded web images into project storage and register Asset records."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._assets = AssetRepository(session)

    def persist_if_enabled(
        self,
        project_id: UUID,
        image: FallbackImage,
        *,
        slide: SlideSpec,
        requirement: VisualRequirement,
        search_query: str,
    ) -> FallbackImage:
        if not self._settings.web_image_search_persist_to_library:
            return image
        if not image.web_sourced or not image.path.exists():
            return image

        if image.source_url:
            existing = self._find_by_source_url(project_id, image.source_url)
            if existing is not None:
                return self._to_fallback(existing, image)

        relative_path, absolute_path = self._copy_into_project(project_id, image.path)
        asset = self._assets.create(
            Asset(
                project_id=project_id,
                filename=absolute_path.name,
                path=relative_path,
                asset_type=self._asset_type_for(requirement),
                description=(requirement.description or slide.title).strip() or None,
                tags=["web_import", image.provider or "web", requirement.type.value],
                metadata={
                    _METADATA_SOURCE_URL: image.source_url,
                    "attribution": image.attribution,
                    "visual_type_hint": requirement.type.value,
                    "search_query": search_query,
                    "provider": image.provider,
                },
            )
        )
        return self._to_fallback(asset, image, absolute_path=absolute_path)

    def _find_by_source_url(self, project_id: UUID, source_url: str) -> Asset | None:
        for asset in self._assets.list_by_project(project_id):
            metadata = asset.metadata or {}
            if metadata.get(_METADATA_SOURCE_URL) == source_url:
                return asset
        return None

    def _copy_into_project(self, project_id: UUID, source_path: Path) -> tuple[str, Path]:
        project_dir = self._settings.project_storage_path / str(project_id) / _WEB_IMPORT_DIR
        project_dir.mkdir(parents=True, exist_ok=True)
        dest_path = project_dir / source_path.name
        if not dest_path.exists():
            shutil.copy2(source_path, dest_path)
        relative = f"{_WEB_IMPORT_DIR}/{dest_path.name}".replace("\\", "/")
        return relative, dest_path

    def _to_fallback(
        self,
        asset: Asset,
        image: FallbackImage,
        *,
        absolute_path: Path | None = None,
    ) -> FallbackImage:
        path = absolute_path or self._resolve_asset_path(asset.project_id, asset)
        return FallbackImage(
            path=path,
            generated=image.generated,
            web_sourced=image.web_sourced,
            attribution=image.attribution,
            source_url=image.source_url,
        )

    def _resolve_asset_path(self, project_id: UUID, asset: Asset) -> Path:
        path = Path(asset.path)
        if path.is_absolute():
            return path
        return self._settings.project_storage_path / str(project_id) / path

    @staticmethod
    def _asset_type_for(requirement: VisualRequirement) -> AssetType:
        if requirement.type.value in {"rendering", "reference_case"}:
            return AssetType.IMAGE
        if requirement.type.value == "site_photo":
            return AssetType.PHOTO
        return AssetType.OTHER

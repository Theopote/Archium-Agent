"""Validate RenderScene asset bindings for Studio command execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.asset_path_resolver import (
    PROJECT_SCHEME,
    AssetPathResolveContext,
    AssetPathResolver,
    is_portable_storage_uri,
    project_asset_uri,
)
from archium.application.visual.asset_reference import (
    SUPPORTED_LAYOUT_IMAGE_EXTENSIONS,
    _asset_is_ready,
    is_supported_layout_image_path,
    is_technical_drawing_asset_type,
    resolve_asset_storage_path,
)
from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.studio_errors import (
    STUDIO_ASSET_FILE_MISSING,
    STUDIO_ASSET_NOT_FOUND,
    STUDIO_ASSET_PROJECT_MISMATCH,
    STUDIO_ASSET_TYPE_INCOMPATIBLE,
    STUDIO_ASSET_UNRESOLVABLE,
    STUDIO_ASSET_URI_MISMATCH,
    STUDIO_ASSET_URI_UNSUPPORTED,
    STUDIO_DRAWING_ORIGIN_REQUIRED,
    STUDIO_DRAWING_REPLACED_BY_PHOTO,
    StudioAssetReferenceError,
)
from archium.infrastructure.database.repositories import AssetRepository

AssetExpectedKind = Literal["image", "drawing"]

_IMAGE_ASSET_TYPES = frozenset(
    {
        AssetType.IMAGE,
        AssetType.PHOTO,
        AssetType.DRAWING,
        AssetType.DIAGRAM,
        AssetType.OTHER,
    }
)
_DRAWING_ASSET_TYPES = frozenset({AssetType.DRAWING, AssetType.DIAGRAM})


@dataclass(frozen=True)
class AssetBindingValidation:
    """Successful asset binding validation result."""

    asset_id: UUID
    storage_uri: str
    resolved_path: Path | None = None


class AssetBindingValidator:
    """Validate asset_id + storage_uri bindings before Studio mutations."""

    def __init__(
        self,
        session: Session | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._resolver = AssetPathResolver()
        self._assets = AssetRepository(session) if session is not None else None

    def validate(
        self,
        *,
        asset_id: UUID,
        storage_uri: str,
        asset_origin: str,
        expected_kind: AssetExpectedKind,
        project_id: UUID | None = None,
        require_resolvable: bool = True,
        resolve_context: AssetPathResolveContext | None = None,
    ) -> AssetBindingValidation:
        uri = storage_uri.strip()
        if not uri:
            raise StudioAssetReferenceError(
                STUDIO_ASSET_NOT_FOUND,
                "storage_uri 不能为空。",
            )

        if expected_kind == "drawing" and asset_origin != "project_upload":
            raise StudioAssetReferenceError(
                STUDIO_DRAWING_ORIGIN_REQUIRED,
                "图纸替换必须使用 project_upload 来源。",
            )

        self._validate_uri_scheme(uri)
        self._validate_project_uri_asset_id(uri, asset_id)
        self._validate_supported_format(uri)

        asset: Asset | None = None
        resolved_path: Path | None = None
        if self._assets is not None and project_id is not None:
            asset = self._load_project_asset(asset_id, project_id)
            self._validate_asset_kind(asset, expected_kind=expected_kind)
            resolved_path = resolve_asset_storage_path(
                asset,
                project_id=project_id,
                settings=self._settings,
            )
            if not resolved_path.is_file():
                raise StudioAssetReferenceError(
                    STUDIO_ASSET_FILE_MISSING,
                    f"素材 `{asset.filename}` 的文件缺失或路径无效。",
                )
            if not is_supported_layout_image_path(resolved_path):
                suffix = resolved_path.suffix.lower() or "(none)"
                raise StudioAssetReferenceError(
                    STUDIO_ASSET_TYPE_INCOMPATIBLE,
                    f"素材 `{asset.filename}` 的格式 {suffix} 不受支持。",
                )
        elif require_resolvable:
            ctx = resolve_context or AssetPathResolveContext(
                project_id=project_id,
                project_storage_root=self._settings.project_storage_path,
            )
            resolved_path = self._resolver.resolve(uri, ctx)
            if resolved_path is None or not resolved_path.is_file():
                raise StudioAssetReferenceError(
                    STUDIO_ASSET_UNRESOLVABLE,
                    f"素材 URI `{uri}` 无法解析为可读文件。",
                )
            if not is_supported_layout_image_path(resolved_path):
                suffix = resolved_path.suffix.lower() or "(none)"
                raise StudioAssetReferenceError(
                    STUDIO_ASSET_TYPE_INCOMPATIBLE,
                    f"素材文件格式 {suffix} 不受支持。",
                )

        if require_resolvable and resolved_path is not None:
            self._assert_readable_image(resolved_path)

        return AssetBindingValidation(
            asset_id=asset_id,
            storage_uri=uri,
            resolved_path=resolved_path,
        )

    def _load_project_asset(self, asset_id: UUID, project_id: UUID) -> Asset:
        assert self._assets is not None
        asset = self._assets.get_by_id(asset_id)
        if asset is None:
            raise StudioAssetReferenceError(
                STUDIO_ASSET_NOT_FOUND,
                f"素材 `{asset_id}` 不存在。",
            )
        if asset.project_id != project_id:
            raise StudioAssetReferenceError(
                STUDIO_ASSET_PROJECT_MISMATCH,
                f"素材 `{asset.filename}` 不属于当前项目，无法绑定。",
            )
        assert self._session is not None
        if not _asset_is_ready(self._session, asset):
            raise StudioAssetReferenceError(
                STUDIO_ASSET_FILE_MISSING,
                f"素材 `{asset.filename}` 尚未处理完成，请稍后再试。",
            )
        return asset

    @staticmethod
    def _validate_uri_scheme(uri: str) -> None:
        if is_portable_storage_uri(uri):
            return
        path = Path(uri)
        if path.is_file():
            return
        raise StudioAssetReferenceError(
            STUDIO_ASSET_URI_UNSUPPORTED,
            f"不支持的素材 URI scheme：`{uri}`。",
        )

    @staticmethod
    def _validate_supported_format(uri: str) -> None:
        if uri.startswith(PROJECT_SCHEME) and _asset_id_from_project_uri(uri) is not None:
            return
        if not is_supported_layout_image_path(uri):
            suffix = Path(uri.split("?", 1)[0]).suffix.lower() or "(none)"
            if suffix not in SUPPORTED_LAYOUT_IMAGE_EXTENSIONS:
                raise StudioAssetReferenceError(
                    STUDIO_ASSET_TYPE_INCOMPATIBLE,
                    f"素材 URI 格式 {suffix} 不受支持，请使用 png/jpg/jpeg/webp/gif。",
                )

    @staticmethod
    def _validate_project_uri_asset_id(uri: str, asset_id: UUID) -> None:
        if not uri.startswith(PROJECT_SCHEME):
            return
        parsed = _asset_id_from_project_uri(uri)
        if parsed is None:
            raise StudioAssetReferenceError(
                STUDIO_ASSET_URI_UNSUPPORTED,
                f"project:// URI 必须使用 `project://assets/<asset_id>` 形式：`{uri}`。",
            )
        if parsed != asset_id:
            raise StudioAssetReferenceError(
                STUDIO_ASSET_URI_MISMATCH,
                f"URI 中的 asset_id `{parsed}` 与命令 asset_id `{asset_id}` 不一致。",
            )

    @staticmethod
    def _validate_asset_kind(asset: Asset, *, expected_kind: AssetExpectedKind) -> None:
        asset_type = asset.asset_type
        if expected_kind == "drawing":
            if asset_type in {AssetType.PHOTO, AssetType.IMAGE}:
                raise StudioAssetReferenceError(
                    STUDIO_DRAWING_REPLACED_BY_PHOTO,
                    f"图纸节点不能用照片 `{asset.filename}` 替换。",
                )
            if asset_type not in _DRAWING_ASSET_TYPES and not is_technical_drawing_asset_type(
                asset_type.value
            ):
                raise StudioAssetReferenceError(
                    STUDIO_ASSET_TYPE_INCOMPATIBLE,
                    f"素材 `{asset.filename}`（{asset_type.value}）不是技术图纸。",
                )
            return
        if asset_type not in _IMAGE_ASSET_TYPES:
            raise StudioAssetReferenceError(
                STUDIO_ASSET_TYPE_INCOMPATIBLE,
                f"素材 `{asset.filename}`（{asset_type.value}）不能作为图片绑定。",
            )

    @staticmethod
    def _assert_readable_image(path: Path) -> None:
        try:
            from PIL import Image

            with Image.open(path) as image:
                image.verify()
        except Exception as exc:
            raise StudioAssetReferenceError(
                STUDIO_ASSET_UNRESOLVABLE,
                f"素材文件无法作为图片读取：`{path.name}`（{exc}）。",
            ) from exc


def _asset_id_from_project_uri(uri: str) -> UUID | None:
    if not uri.startswith(PROJECT_SCHEME):
        return None
    remainder = uri[len(PROJECT_SCHEME) :].replace("\\", "/").strip("/")
    parts = remainder.split("/")
    if len(parts) < 2 or parts[0] != "assets" or not parts[1]:
        return None
    try:
        return UUID(parts[1])
    except ValueError:
        return None


def canonical_project_asset_uri(asset_id: UUID) -> str:
    """Return the canonical portable URI for a project asset binding."""
    return project_asset_uri(asset_id)

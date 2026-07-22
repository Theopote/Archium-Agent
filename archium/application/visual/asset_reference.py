"""Resolve LayoutPlan content_ref values against project assets and storage paths."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, ProcessingStatus
from archium.domain.studio_errors import (
    STUDIO_ASSET_FILE_MISSING,
    STUDIO_ASSET_NOT_FOUND,
    STUDIO_ASSET_PROJECT_MISMATCH,
    STUDIO_ASSET_TYPE_INCOMPATIBLE,
    STUDIO_DRAWING_REPLACED_BY_PHOTO,
    StudioAssetReferenceError,
)
from archium.domain.visual.enums import LayoutContentType
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.infrastructure.database.repositories import AssetRepository, DocumentRepository

# Formats pptxgen / LayoutPlan render path can place reliably.
SUPPORTED_LAYOUT_IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
)
# Asset catalog types accepted as technical drawings for DRAWING slots.
TECHNICAL_DRAWING_ASSET_TYPES = frozenset(
    {AssetType.DRAWING.value, AssetType.DIAGRAM.value}
)
_COMPATIBLE_ASSET_TYPES: dict[LayoutContentType, frozenset[AssetType]] = {
    LayoutContentType.IMAGE: frozenset(
        {
            AssetType.IMAGE,
            AssetType.PHOTO,
            AssetType.DRAWING,
            AssetType.DIAGRAM,
            AssetType.OTHER,
        }
    ),
    LayoutContentType.DRAWING: frozenset({AssetType.DRAWING, AssetType.DIAGRAM}),
    LayoutContentType.CHART: frozenset({AssetType.CHART, AssetType.IMAGE}),
}


@dataclass(frozen=True)
class ResolvedAssetReference:
    """A project-scoped asset reference ready for LayoutPlan binding."""

    asset: Asset
    ref: str
    resolved_path: Path


class AssetReferenceResolver:
    """Resolve and validate project asset references for Studio edits."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._assets = AssetRepository(session)
        self._documents = DocumentRepository(session)

    def resolve(
        self,
        *,
        project_id: UUID,
        content_ref: str,
        element: LayoutElement | None = None,
    ) -> ResolvedAssetReference:
        return assert_studio_asset_reference(
            self._session,
            project_id=project_id,
            content_ref=content_ref,
            element=element,
            settings=self._settings,
        )

    def resolve_storage_path(self, asset: Asset, *, project_id: UUID) -> Path:
        return resolve_asset_storage_path(asset, project_id=project_id, settings=self._settings)


def resolve_asset_storage_path(
    asset: Asset,
    *,
    project_id: UUID,
    settings: Settings,
) -> Path:
    path = Path(asset.path)
    if not path.is_absolute():
        path = settings.project_storage_path / str(project_id) / path
    return path


def assert_studio_asset_reference(
    session: Session,
    *,
    project_id: UUID,
    content_ref: str,
    element: LayoutElement | None = None,
    settings: Settings | None = None,
) -> ResolvedAssetReference:
    """Validate asset integrity before binding to a layout element."""
    resolved_settings = settings or get_settings()
    ref = str(content_ref).strip()
    if not ref:
        raise StudioAssetReferenceError(
            STUDIO_ASSET_NOT_FOUND,
            "请指定有效的项目素材。",
        )

    try:
        asset_id = UUID(ref)
    except ValueError as exc:
        raise StudioAssetReferenceError(
            STUDIO_ASSET_NOT_FOUND,
            f"素材引用 `{ref}` 不是有效的项目素材 ID。",
        ) from exc

    normalized_ref = str(asset_id)
    repo = AssetRepository(session)
    asset = repo.get_by_id(asset_id)
    if asset is None:
        raise StudioAssetReferenceError(
            STUDIO_ASSET_NOT_FOUND,
            f"素材 `{normalized_ref[:8]}…` 不存在。",
        )

    if asset.project_id != project_id:
        raise StudioAssetReferenceError(
            STUDIO_ASSET_PROJECT_MISMATCH,
            f"素材 `{asset.filename}` 不属于当前项目，无法绑定。",
        )

    if not _asset_is_ready(session, asset):
        raise StudioAssetReferenceError(
            STUDIO_ASSET_FILE_MISSING,
            f"素材 `{asset.filename}` 尚未处理完成，请稍后再试。",
        )

    storage_path = resolve_asset_storage_path(
        asset,
        project_id=project_id,
        settings=resolved_settings,
    )
    if not storage_path.is_file():
        raise StudioAssetReferenceError(
            STUDIO_ASSET_FILE_MISSING,
            f"素材 `{asset.filename}` 的文件缺失或路径无效。",
        )

    if not is_supported_layout_image_path(storage_path):
        suffix = storage_path.suffix.lower() or "(none)"
        raise StudioAssetReferenceError(
            STUDIO_ASSET_TYPE_INCOMPATIBLE,
            f"素材 `{asset.filename}` 的格式 {suffix} 不受支持，请使用 png/jpg/jpeg/webp/gif。",
        )

    if element is not None and element.content_type in _COMPATIBLE_ASSET_TYPES:
        _assert_asset_compatible_with_element(asset, element)

    return ResolvedAssetReference(
        asset=asset,
        ref=normalized_ref,
        resolved_path=storage_path.resolve(),
    )


def _asset_is_ready(session: Session, asset: Asset) -> bool:
    if asset.document_id is None:
        return True
    document = DocumentRepository(session).get_document(asset.document_id)
    if document is None:
        return True
    return document.processing_status == ProcessingStatus.COMPLETED


def _assert_asset_compatible_with_element(asset: Asset, element: LayoutElement) -> None:
    allowed = _COMPATIBLE_ASSET_TYPES.get(element.content_type)
    if allowed is None:
        return

    asset_type = asset.asset_type
    if element.content_type == LayoutContentType.DRAWING and asset_type in {
        AssetType.PHOTO,
        AssetType.IMAGE,
    }:
        raise StudioAssetReferenceError(
            STUDIO_DRAWING_REPLACED_BY_PHOTO,
            f"元素 `{element.id}` 需要技术图纸，不能用照片 `{asset.filename}` 替换。",
        )

    if asset_type not in allowed:
        raise StudioAssetReferenceError(
            STUDIO_ASSET_TYPE_INCOMPATIBLE,
            (
                f"素材 `{asset.filename}`（{asset_type.value}）"
                f"不适合元素 `{element.id}`（{element.content_type.value}）。"
            ),
        )


@dataclass(frozen=True)
class AssetReferenceContext:
    """Inputs for LAYOUT.* asset integrity checks.

    ``known_asset_ids`` — asset IDs that exist in the project catalog.
    ``resolved_paths`` — refs → portable storage URIs (persistable).
    ``absolute_paths`` — refs → host filesystem paths (runtime only).
    ``asset_types`` — ref → ``AssetType`` value for catalogued assets.
    ``asset_origins`` — ref → RenderScene asset_origin value.
    """

    known_asset_ids: frozenset[str]
    resolved_paths: dict[str, str]
    asset_types: dict[str, str] = field(default_factory=dict)
    asset_origins: dict[str, str] = field(default_factory=dict)
    absolute_paths: dict[str, str] = field(default_factory=dict)


_VALID_ASSET_ORIGINS = frozenset(
    {
        "project_upload",
        "public_research",
        "reference_case",
        "ai_generated",
        "stock_image",
    }
)


def infer_asset_origin(asset: Asset) -> str:
    """Map asset metadata/tags to RenderScene ``asset_origin`` values."""
    metadata = asset.metadata or {}
    raw = metadata.get("origin") or metadata.get("asset_origin")
    if isinstance(raw, str) and raw.strip().lower() in _VALID_ASSET_ORIGINS:
        return raw.strip().lower()

    tags = {tag.strip().lower() for tag in (asset.tags or []) if tag.strip()}
    if tags & {"ai_generated", "ai", "generated"}:
        return "ai_generated"
    if tags & {"stock", "stock_image", "stock-photo"}:
        return "stock_image"
    if tags & {"reference", "reference_case", "reference_style"}:
        return "reference_case"
    if tags & {"public_research", "research"}:
        return "public_research"

    purpose = metadata.get("purpose") or metadata.get("document_purpose")
    if isinstance(purpose, str):
        purpose_l = purpose.strip().lower()
        if purpose_l in {"reference_case", "reference_style"}:
            return "reference_case"
        if purpose_l in {"public_research", "research"}:
            return "public_research"
        if purpose_l in {"ai_generated", "generated"}:
            return "ai_generated"
        if purpose_l in {"stock", "stock_image"}:
            return "stock_image"

    if metadata.get("is_ai") is True or metadata.get("ai_generated") is True:
        return "ai_generated"
    if metadata.get("is_stock") is True:
        return "stock_image"
    if metadata.get("is_reference") is True:
        return "reference_case"
    return "project_upload"


def is_supported_layout_image_path(path: str | Path) -> bool:
    """Return True when the file extension is accepted by the layout PPTX renderer."""
    from archium.application.visual.asset_path_resolver import (
        asset_uri_suffix,
        is_portable_storage_uri,
    )

    text = str(path)
    if is_portable_storage_uri(text):
        return asset_uri_suffix(text) in SUPPORTED_LAYOUT_IMAGE_EXTENSIONS
    return Path(path).suffix.lower() in SUPPORTED_LAYOUT_IMAGE_EXTENSIONS


def is_technical_drawing_asset_type(asset_type: str | None) -> bool:
    """Return True when catalog type is drawing/diagram (not photo/other)."""
    if not asset_type:
        return False
    return asset_type.lower() in TECHNICAL_DRAWING_ASSET_TYPES


def build_asset_reference_context(
    session: Session,
    *,
    project_id: UUID,
    content_refs: Iterable[str | None],
    settings: Settings,
) -> AssetReferenceContext:
    """Look up referenced assets and build portable storage URIs.

    Absolute filesystem paths are kept in ``absolute_paths`` for runtime
    resolution only — they must not be persisted into RenderScene JSON.
    """
    from archium.application.visual.asset_path_resolver import (
        project_asset_uri,
        storage_asset_uri,
    )

    refs: list[str] = []
    for raw in content_refs:
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            refs.append(text)

    if not refs:
        return AssetReferenceContext(
            known_asset_ids=frozenset(),
            resolved_paths={},
            asset_types={},
            asset_origins={},
            absolute_paths={},
        )

    repo = AssetRepository(session)
    known: set[str] = set()
    resolved: dict[str, str] = {}
    absolute: dict[str, str] = {}
    asset_types: dict[str, str] = {}
    asset_origins: dict[str, str] = {}
    project_root = settings.project_storage_path / str(project_id)
    icon_registry = None
    for ref in dict.fromkeys(refs):
        if ref.startswith("icon:"):
            # Curated architectural icon SVGs bundled inside Archium.
            if icon_registry is None:
                from archium.application.visual.architectural_icon_registry import (
                    load_default_architectural_icon_registry,
                )

                icon_registry = load_default_architectural_icon_registry()
            icon_key = ref.split(":", 1)[1].strip()
            if icon_key:
                icon = icon_registry.get_by_name(icon_key)
                if icon is not None:
                    svg_path = icon_registry.resolve_svg_path(icon)
                    if svg_path.is_file():
                        known.add(ref)
                        # Use absolute path for layout validation + renderers.
                        resolved[ref] = str(svg_path.resolve())
                        absolute[ref] = str(svg_path.resolve())
                        asset_types[ref] = "other"
                        asset_origins[ref] = "stock_image"
            continue
        try:
            asset_id = UUID(ref)
        except ValueError:
            continue
        asset = repo.get_by_id(asset_id)
        if asset is None or asset.project_id != project_id:
            continue
        known.add(ref)
        asset_types[ref] = (
            asset.asset_type.value
            if hasattr(asset.asset_type, "value")
            else str(asset.asset_type)
        )
        asset_origins[ref] = infer_asset_origin(asset)
        path = Path(asset.path)
        if not path.is_absolute():
            path = project_root / path
        if path.is_file():
            absolute[ref] = str(path.resolve())
            try:
                relative = path.resolve().relative_to(project_root.resolve())
                resolved[ref] = storage_asset_uri(project_id, relative.as_posix())
            except (OSError, ValueError):
                resolved[ref] = project_asset_uri(ref)
        else:
            resolved[ref] = project_asset_uri(ref)
    return AssetReferenceContext(
        known_asset_ids=frozenset(known),
        resolved_paths=resolved,
        asset_types=asset_types,
        asset_origins=asset_origins,
        absolute_paths=absolute,
    )


def content_refs_from_plan(plan: LayoutPlan) -> list[str]:
    return [el.content_ref for el in plan.elements if el.content_ref]

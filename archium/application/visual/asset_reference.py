"""Resolve LayoutPlan content_ref values against project assets and storage paths."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings
from archium.domain.enums import AssetType
from archium.infrastructure.database.repositories import AssetRepository

# Formats pptxgen / LayoutPlan render path can place reliably.
SUPPORTED_LAYOUT_IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif"}
)
# Asset catalog types accepted as technical drawings for DRAWING slots.
TECHNICAL_DRAWING_ASSET_TYPES = frozenset(
    {AssetType.DRAWING.value, AssetType.DIAGRAM.value}
)


@dataclass(frozen=True)
class AssetReferenceContext:
    """Inputs for LAYOUT.* asset integrity checks.

    ``known_asset_ids`` — asset IDs that exist in the project catalog.
    ``resolved_paths`` — refs that resolve to an existing file on disk.
    ``asset_types`` — ref → ``AssetType`` value for catalogued assets.
    """

    known_asset_ids: frozenset[str]
    resolved_paths: dict[str, str]
    asset_types: dict[str, str] = field(default_factory=dict)


def is_supported_layout_image_path(path: str | Path) -> bool:
    """Return True when the file extension is accepted by the layout PPTX renderer."""
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
    """Look up referenced assets and resolve storage paths that exist on disk."""
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
        )

    repo = AssetRepository(session)
    known: set[str] = set()
    resolved: dict[str, str] = {}
    asset_types: dict[str, str] = {}
    for ref in dict.fromkeys(refs):
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
        path = Path(asset.path)
        if not path.is_absolute():
            path = settings.project_storage_path / str(project_id) / path
        if path.is_file():
            resolved[ref] = str(path.resolve())
    return AssetReferenceContext(
        known_asset_ids=frozenset(known),
        resolved_paths=resolved,
        asset_types=asset_types,
    )


def content_refs_from_plan(plan) -> list[str]:  # noqa: ANN001
    return [el.content_ref for el in plan.elements if el.content_ref]

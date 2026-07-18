"""Resolve LayoutPlan content_ref values against project assets and storage paths."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings
from archium.infrastructure.database.repositories import AssetRepository


@dataclass(frozen=True)
class AssetReferenceContext:
    """Inputs for LAYOUT.* asset integrity checks.

    ``known_asset_ids`` — asset IDs that exist in the project catalog.
    ``resolved_paths`` — refs that resolve to an existing file on disk.
    """

    known_asset_ids: frozenset[str]
    resolved_paths: dict[str, str]


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
        return AssetReferenceContext(known_asset_ids=frozenset(), resolved_paths={})

    repo = AssetRepository(session)
    known: set[str] = set()
    resolved: dict[str, str] = {}
    for ref in dict.fromkeys(refs):
        try:
            asset_id = UUID(ref)
        except ValueError:
            continue
        asset = repo.get_by_id(asset_id)
        if asset is None or asset.project_id != project_id:
            continue
        known.add(ref)
        path = Path(asset.path)
        if not path.is_absolute():
            path = settings.project_storage_path / str(project_id) / path
        if path.is_file():
            resolved[ref] = str(path.resolve())
    return AssetReferenceContext(
        known_asset_ids=frozenset(known),
        resolved_paths=resolved,
    )


def content_refs_from_plan(plan) -> list[str]:  # noqa: ANN001
    return [el.content_ref for el in plan.elements if el.content_ref]

"""Generate placeholder assets for architectural benchmark cases."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from archium.domain.enums import VisualType
from archium.infrastructure.renderers.diagram_generator import generate_fallback_diagram

from tests.benchmark.architectural_slides.case_catalog import get_catalog_entry


def ensure_case_assets(case_id: str, assets_dir: Path) -> list[str]:
    """Create deterministic placeholder PNG assets for a benchmark case."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    entry = get_catalog_entry(case_id)
    rel_paths: list[str] = []
    for asset in entry.assets:
        rel_paths.append(_write_asset(assets_dir, asset.asset_id, asset.visual_type, asset.placeholder_label))
    return rel_paths


def _write_asset(
    assets_dir: Path,
    asset_id: str | UUID,
    visual_type: VisualType,
    description: str,
) -> str:
    filename = f"{asset_id}.png"
    output_path = assets_dir / filename
    if not output_path.exists():
        generate_fallback_diagram(
            output_path,
            title=description,
            visual_type=visual_type,
            description=description,
            key_points=[description],
            message=description,
        )
    return f"assets/{filename}"


__all__ = ["ensure_case_assets"]

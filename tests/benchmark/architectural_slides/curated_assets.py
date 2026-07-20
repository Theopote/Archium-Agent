"""Curated real assets for architectural slide benchmark cases."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from archium.domain.enums import VisualType
from archium.infrastructure.renderers.diagram_generator import generate_fallback_diagram

from tests.benchmark.architectural_slides.case_catalog import get_catalog_entry

BENCHMARK_ROOT = Path(__file__).resolve().parent
CURATED_ROOT = BENCHMARK_ROOT / "curated_assets"
CURATED_MANIFEST_PATH = CURATED_ROOT / "manifest.json"
CURATED_POOL_DIR = CURATED_ROOT / "pool"


def load_curated_manifest() -> dict[str, str]:
    """Return asset_id -> pool-relative path for curated assets."""
    if not CURATED_MANIFEST_PATH.is_file():
        return {}
    payload = json.loads(CURATED_MANIFEST_PATH.read_text(encoding="utf-8"))
    assets = payload.get("assets")
    if not isinstance(assets, dict):
        return {}
    return {str(key): str(value) for key, value in assets.items()}


def curated_asset_path(asset_id: str) -> Path | None:
    rel = load_curated_manifest().get(asset_id)
    if rel is None:
        return None
    path = (CURATED_ROOT / rel).resolve()
    return path if path.is_file() else None


def is_curated_asset(asset_id: str) -> bool:
    return curated_asset_path(asset_id) is not None


def count_case_asset_provenance(case_dir: Path) -> tuple[int, int, int]:
    """Return (total, curated_real, placeholder) asset counts for one case folder."""
    assets_dir = case_dir / "assets"
    if not assets_dir.is_dir():
        return 0, 0, 0
    total = 0
    curated = 0
    for path in assets_dir.iterdir():
        if not path.is_file() or path.suffix.lower() != ".png":
            continue
        total += 1
        if is_curated_asset(path.stem):
            curated += 1
    return total, curated, total - curated


def ensure_case_assets(case_id: str, assets_dir: Path) -> list[str]:
    """Create benchmark assets, preferring curated pool PNGs when mapped."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    entry = get_catalog_entry(case_id)
    rel_paths: list[str] = []
    for asset in entry.assets:
        rel_paths.append(
            _write_asset(
                assets_dir,
                str(asset.asset_id),
                asset.visual_type,
                asset.placeholder_label,
            )
        )
    return rel_paths


def _write_asset(
    assets_dir: Path,
    asset_id: str,
    visual_type: VisualType,
    description: str,
) -> str:
    filename = f"{asset_id}.png"
    output_path = assets_dir / filename
    if output_path.exists():
        return f"assets/{filename}"
    curated = curated_asset_path(str(asset_id))
    if curated is not None:
        shutil.copy(curated, output_path)
        return f"assets/{filename}"
    generate_fallback_diagram(
        output_path,
        title=description,
        visual_type=visual_type,
        description=description,
        key_points=[description],
        message=description,
    )
    return f"assets/{filename}"


__all__ = [
    "CURATED_MANIFEST_PATH",
    "CURATED_POOL_DIR",
    "CURATED_ROOT",
    "count_case_asset_provenance",
    "curated_asset_path",
    "ensure_case_assets",
    "is_curated_asset",
    "load_curated_manifest",
]

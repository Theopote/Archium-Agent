"""Render manifest helpers for architectural slide benchmark cases."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archium.domain.visual.benchmark import BenchmarkRenderManifest

RENDER_MANIFEST_NAME = "render_manifest.json"
WIREFRAME_NAME = "wireframe.png"
FINAL_RENDER_NAME = "final_render.png"
LEGACY_PREVIEW_NAME = "preview.png"


def wireframe_path(case_dir: Path) -> Path:
    path = case_dir / WIREFRAME_NAME
    if path.is_file():
        return path
    return case_dir / LEGACY_PREVIEW_NAME


def final_render_path(case_dir: Path) -> Path:
    return case_dir / FINAL_RENDER_NAME


def render_manifest_path(case_dir: Path) -> Path:
    return case_dir / RENDER_MANIFEST_NAME


def load_render_manifest(case_dir: Path) -> BenchmarkRenderManifest | None:
    path = render_manifest_path(case_dir)
    if not path.is_file():
        return None
    return BenchmarkRenderManifest.model_validate_json(path.read_text(encoding="utf-8"))


def write_render_manifest(case_dir: Path, manifest: BenchmarkRenderManifest) -> Path:
    path = render_manifest_path(case_dir)
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def write_pending_render_manifest(
    case_dir: Path,
    *,
    asset_count: int = 0,
    placeholder_asset_count: int = 0,
    notes: str = "",
) -> Path:
    """Write a manifest indicating final render is not yet available for visual review."""
    manifest = BenchmarkRenderManifest(
        render_source="pending",
        pptx_path="output.pptx",
        image_path=FINAL_RENDER_NAME,
        rendered_at=None,
        renderer="",
        asset_count=asset_count,
        real_asset_count=max(0, asset_count - placeholder_asset_count),
        placeholder_asset_count=placeholder_asset_count,
        font_fallbacks=[],
        missing_assets=[],
        render_valid=False,
        notes=notes
        or "Final render not yet produced; visual human review is blocked.",
    )
    return write_render_manifest(case_dir, manifest)


def ensure_wireframe_alias(case_dir: Path) -> Path | None:
    """Ensure wireframe.png exists (copy from legacy preview.png when needed)."""
    wireframe = case_dir / WIREFRAME_NAME
    legacy = case_dir / LEGACY_PREVIEW_NAME
    if wireframe.is_file():
        return wireframe
    if legacy.is_file():
        shutil.copy(legacy, wireframe)
        return wireframe
    return None


def visual_review_eligibility(
    case_dir: Path,
) -> tuple[bool, BenchmarkRenderManifest | None, list[str]]:
    """Return whether visual human review may proceed for this case directory."""
    manifest = load_render_manifest(case_dir)
    blockers: list[str] = []
    if manifest is None:
        blockers.append("缺少 render_manifest.json")
    elif not manifest.visual_review_eligible():
        blockers.extend(manifest.eligibility_blockers())
    if not final_render_path(case_dir).is_file():
        blockers.append(f"缺少 {FINAL_RENDER_NAME}")
    return (not blockers, manifest, blockers)


def count_assets(case_dir: Path) -> tuple[int, int]:
    assets_dir = case_dir / "assets"
    if not assets_dir.is_dir():
        return 0, 0
    files = [path for path in assets_dir.iterdir() if path.is_file()]
    # Benchmark fixtures currently generate deterministic placeholder PNGs only.
    return len(files), len(files)


def bootstrap_case_render_artifacts(case_dir: Path) -> dict[str, Any]:
    """Ensure wireframe alias + pending manifest exist for one case folder."""
    ensure_wireframe_alias(case_dir)
    asset_count, placeholder_count = count_assets(case_dir)
    manifest_path = render_manifest_path(case_dir)
    if not manifest_path.is_file():
        write_pending_render_manifest(
            case_dir,
            asset_count=asset_count,
            placeholder_asset_count=placeholder_count,
            notes=(
                "Benchmark assets are placeholder diagrams; "
                "final_render.png and real assets are required before visual review."
            ),
        )
    return {
        "wireframe": str(wireframe_path(case_dir)),
        "render_manifest": str(manifest_path),
        "final_render_exists": final_render_path(case_dir).is_file(),
    }

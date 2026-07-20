"""Render manifest helpers for architectural slide benchmark cases."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from archium.domain.visual.benchmark import BenchmarkRenderManifest

RENDER_MANIFEST_NAME = "render_manifest.json"
WIREFRAME_NAME = "wireframe.png"
FINAL_RENDER_NAME = "final_render.png"
PPTX_RENDER_NAME = "pptx_render.png"
SCENE_JSON_NAME = "scene.json"
SCENE_PREVIEW_NAME = "scene_preview.png"
LEGACY_PREVIEW_NAME = "preview.png"
LAYOUT_SCORE_NAME = "layout_score.json"

LayoutGeometryArtifact = Literal[
    "wireframe.png",
    "layout_plan.json",
    "validation_report.json",
    "layout_score.json",
]
RenderedVisualArtifact = Literal[
    "scene.json",
    "scene_preview.png",
    "output.pptx",
    "pptx_render.png",
    "render_manifest.json",
]


def wireframe_path(case_dir: Path) -> Path:
    path = case_dir / WIREFRAME_NAME
    if path.is_file():
        return path
    return case_dir / LEGACY_PREVIEW_NAME


def scene_preview_path(case_dir: Path) -> Path:
    return case_dir / SCENE_PREVIEW_NAME


def pptx_render_path(case_dir: Path) -> Path:
    return case_dir / PPTX_RENDER_NAME


def final_render_path(case_dir: Path) -> Path:
    return case_dir / FINAL_RENDER_NAME


def render_manifest_path(case_dir: Path) -> Path:
    return case_dir / RENDER_MANIFEST_NAME


def visual_review_image_path(case_dir: Path) -> Path | None:
    """Preferred raster for Rendered Visual human review."""
    for candidate in (pptx_render_path(case_dir), final_render_path(case_dir), scene_preview_path(case_dir)):
        if candidate.is_file():
            return candidate
    return None


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
        image_path=PPTX_RENDER_NAME,
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


def ensure_pptx_render_alias(case_dir: Path) -> Path | None:
    """Copy final_render.png to pptx_render.png when screenshot tooling produced it."""
    pptx_render = pptx_render_path(case_dir)
    if pptx_render.is_file():
        return pptx_render
    final_render = final_render_path(case_dir)
    if final_render.is_file():
        shutil.copy(final_render, pptx_render)
        return pptx_render
    return None


def visual_review_eligibility(
    case_dir: Path,
) -> tuple[bool, BenchmarkRenderManifest | None, list[str]]:
    """Return whether Rendered Visual human review may proceed."""
    manifest = load_render_manifest(case_dir)
    blockers: list[str] = []
    if manifest is None:
        blockers.append("缺少 render_manifest.json")
    elif not manifest.visual_review_eligible():
        blockers.extend(manifest.eligibility_blockers())
    if not scene_preview_path(case_dir).is_file():
        blockers.append(f"缺少 {SCENE_PREVIEW_NAME}")
    pptx_path = case_dir / "output.pptx"
    if not pptx_path.is_file():
        blockers.append("缺少 output.pptx")
    return (not blockers, manifest, blockers)


def editability_review_eligibility(case_dir: Path) -> tuple[bool, list[str]]:
    """Return whether PPTX editability review may proceed."""
    blockers: list[str] = []
    eligible, manifest, visual_blockers = visual_review_eligibility(case_dir)
    if not eligible:
        blockers.extend(visual_blockers)
    pptx_path = case_dir / "output.pptx"
    if not pptx_path.is_file():
        blockers.append("缺少 output.pptx")
    elif manifest is not None and manifest.render_source == "pending":
        blockers.append("render_source=pending")
    return (not blockers, blockers)


def layout_geometry_artifacts(case_dir: Path) -> dict[str, bool]:
    """Report which Layout Geometry Benchmark artifacts exist."""
    return {
        "wireframe.png": wireframe_path(case_dir).is_file(),
        "layout_plan.json": (case_dir / "layout_plan.json").is_file(),
        "validation_report.json": (case_dir / "validation_report.json").is_file(),
        "layout_score.json": (case_dir / LAYOUT_SCORE_NAME).is_file()
        or (case_dir / "score_baseline.json").is_file(),
    }


def rendered_visual_artifacts(case_dir: Path) -> dict[str, bool]:
    """Report which Rendered Visual Benchmark artifacts exist."""
    return {
        "scene.json": (case_dir / SCENE_JSON_NAME).is_file(),
        "scene_preview.png": scene_preview_path(case_dir).is_file(),
        "output.pptx": (case_dir / "output.pptx").is_file(),
        "pptx_render.png": pptx_render_path(case_dir).is_file(),
        "render_manifest.json": render_manifest_path(case_dir).is_file(),
    }


def count_assets(case_dir: Path) -> tuple[int, int, int]:
    """Return (total, curated_real, placeholder) asset counts."""
    from tests.benchmark.architectural_slides.curated_assets import count_case_asset_provenance

    return count_case_asset_provenance(case_dir)


def bootstrap_case_render_artifacts(case_dir: Path) -> dict[str, Any]:
    """Ensure wireframe alias + pending manifest exist for one case folder."""
    ensure_wireframe_alias(case_dir)
    asset_count, curated_count, placeholder_count = count_assets(case_dir)
    manifest_path = render_manifest_path(case_dir)
    if not manifest_path.is_file():
        write_pending_render_manifest(
            case_dir,
            asset_count=asset_count,
            placeholder_asset_count=placeholder_count,
            notes=(
                "Benchmark assets are placeholder diagrams; "
                "scene_preview.png and real assets are required before visual review."
            ),
        )
    return {
        "wireframe": str(wireframe_path(case_dir)),
        "render_manifest": str(manifest_path),
        "scene_preview_exists": scene_preview_path(case_dir).is_file(),
        "pptx_render_exists": pptx_render_path(case_dir).is_file(),
    }

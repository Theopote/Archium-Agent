"""Rendered Visual Benchmark pipeline for architectural slide cases."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from archium.application.visual.benchmark_service import BenchmarkCaseResult
from archium.domain.slide import SlideSpec
from archium.domain.visual.benchmark import BenchmarkRenderManifest
from archium.domain.visual.layout import LayoutPlan
from archium.infrastructure.renderers.pptx_screenshot import (
    export_pptx_slide_pngs,
    screenshot_tools_available,
)
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle
from tests.benchmark.architectural_slides.render_manifest import (
    FINAL_RENDER_NAME,
    count_assets,
    write_render_manifest,
)
from tests.golden.visual.composition.artifacts import maybe_export_pptx

PPTX_NAME = "output.pptx"
_RENDER_TMP_DIR = "_render_tmp"


@dataclass(frozen=True)
class SlideContentBundleBuildResult:
    bundle: SlideContentBundle
    missing_content_refs: tuple[str, ...]
    resolved_asset_count: int


def build_slide_content_bundle(
    plan: LayoutPlan,
    assets_dir: Path,
    slide: SlideSpec,
) -> SlideContentBundleBuildResult:
    """Map LayoutPlan content_ref values to on-disk asset paths for PPTX export."""
    asset_paths: dict[str, str] = {}
    missing: list[str] = []
    for element in plan.elements:
        if not element.content_ref:
            continue
        asset_file = assets_dir / f"{element.content_ref}.png"
        if asset_file.is_file():
            asset_paths[element.content_ref] = str(asset_file.resolve())
        else:
            missing.append(element.content_ref)
    bundle = SlideContentBundle(
        asset_paths=asset_paths,
        page_number=slide.order,
        speaker_notes=slide.speaker_notes or None,
    )
    return SlideContentBundleBuildResult(
        bundle=bundle,
        missing_content_refs=tuple(missing),
        resolved_asset_count=len(asset_paths),
    )


def export_benchmark_pptx(
    result: BenchmarkCaseResult,
    case_dir: Path,
    *,
    assets_dir: Path | None = None,
) -> tuple[Path | None, SlideContentBundleBuildResult]:
    """Export a content-complete PPTX for one benchmark case."""
    assets = assets_dir or (case_dir / "assets")
    build = build_slide_content_bundle(result.plan, assets, result.slide)
    pptx_path = case_dir / PPTX_NAME
    exported = maybe_export_pptx(
        result.plan,
        result.design_system,
        pptx_path,
        title=result.slide.title,
        content_bundle=build.bundle,
    )
    return exported, build


def export_benchmark_final_render(
    pptx_path: Path,
    case_dir: Path,
) -> Path | None:
    """Rasterize the first slide of a benchmark PPTX to ``final_render.png``."""
    if not pptx_path.is_file():
        return None
    if not screenshot_tools_available():
        return None
    tmp_dir = case_dir / _RENDER_TMP_DIR
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
    screenshots = export_pptx_slide_pngs(pptx_path, tmp_dir)
    if not screenshots:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None
    final_path = case_dir / FINAL_RENDER_NAME
    final_path.write_bytes(screenshots[0].read_bytes())
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return final_path


def render_benchmark_visual_artifacts(
    result: BenchmarkCaseResult,
    case_dir: Path,
) -> BenchmarkRenderManifest:
    """Export full-content PPTX and optional final-render PNG; update render manifest."""
    pptx_path, build = export_benchmark_pptx(result, case_dir)
    final_render = None
    renderer = ""
    rendered_at: datetime | None = None
    notes: list[str] = []

    if pptx_path is None or not pptx_path.is_file():
        notes.append("PPTX export skipped (Node/PptxGenJS unavailable).")
    else:
        notes.append("PPTX exported with LayoutPlan text styles and resolved asset paths.")
        final_render = export_benchmark_final_render(pptx_path, case_dir)
        if final_render is not None:
            renderer = "libreoffice+pdftoppm"
            rendered_at = datetime.now(UTC)
            notes.append("final_render.png rasterized from output.pptx.")
        elif screenshot_tools_available():
            notes.append("PPTX present but final_render rasterization failed.")
        else:
            notes.append(
                "Screenshot tools unavailable (LibreOffice + pdftoppm); "
                "final_render.png not produced."
            )

    asset_count, curated_count, placeholder_count = count_assets(case_dir)
    pptx_ok = pptx_path is not None and pptx_path.is_file()
    render_valid = (
        pptx_ok
        and final_render is not None
        and not build.missing_content_refs
    )
    if build.missing_content_refs:
        notes.append(
            "Unresolved content_ref paths: "
            + ", ".join(build.missing_content_refs[:5])
            + (" …" if len(build.missing_content_refs) > 5 else "")
        )
    if placeholder_count > 0:
        notes.append(
            "Some assets remain placeholder diagrams; visual human review stays blocked "
            "until all case assets are curated."
        )
    elif curated_count > 0:
        notes.append("All mapped assets are curated PNGs from the benchmark asset pool.")

    manifest = BenchmarkRenderManifest(
        render_source="pptx_screenshot" if final_render is not None else "pptx_only",
        pptx_path=PPTX_NAME,
        image_path=FINAL_RENDER_NAME,
        rendered_at=rendered_at,
        renderer=renderer or ("pptxgenjs" if pptx_ok else ""),
        asset_count=asset_count,
        real_asset_count=curated_count,
        placeholder_asset_count=placeholder_count,
        font_fallbacks=[],
        missing_assets=list(build.missing_content_refs),
        render_valid=render_valid,
        notes=" ".join(notes),
    )
    write_render_manifest(case_dir, manifest)
    return manifest

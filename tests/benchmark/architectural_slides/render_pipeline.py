"""Rendered Visual Benchmark pipeline for architectural slide cases."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from archium.application.visual.benchmark_service import BenchmarkCaseResult
from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.domain.slide import SlideSpec
from archium.domain.visual.benchmark import BenchmarkRenderManifest
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash
from archium.infrastructure.renderers.png_renderer import PngRenderer
from archium.infrastructure.renderers.pptx_renderer import PptxRenderer, maybe_export_scene_pptx
from archium.infrastructure.renderers.renderer_conformance import assert_renderer_conformance
from archium.infrastructure.renderers.pptx_screenshot import (
    export_pptx_slide_pngs,
    screenshot_tools_available,
)
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle
from tests.benchmark.architectural_slides.render_manifest import (
    FINAL_RENDER_NAME,
    SCENE_JSON_NAME,
    SCENE_PREVIEW_NAME,
    count_assets,
    write_render_manifest,
)

PPTX_NAME = "output.pptx"
_RENDER_TMP_DIR = "_render_tmp"


@dataclass(frozen=True)
class SlideContentBundleBuildResult:
    bundle: SlideContentBundle
    missing_content_refs: tuple[str, ...]
    resolved_asset_count: int


@dataclass(frozen=True)
class SceneRenderResult:
    scene: RenderScene
    scene_path: Path
    scene_preview_path: Path
    scene_hash: str
    unresolved_nodes: tuple[str, ...]


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


def compile_and_render_scene(
    result: BenchmarkCaseResult,
    case_dir: Path,
    *,
    assets_dir: Path | None = None,
) -> SceneRenderResult:
    """Compile RenderScene and write scene.json + scene_preview.png."""
    assets = assets_dir or (case_dir / "assets")
    build = build_slide_content_bundle(result.plan, assets, result.slide)
    compiler = RenderSceneCompiler()
    scene = compiler.compile(
        slide=result.slide,
        layout_plan=result.plan,
        design_system=result.design_system,
        content_bundle=build.bundle,
        visual_intent=result.intent,
    )
    scene_path = case_dir / SCENE_JSON_NAME
    scene_path.write_text(
        json.dumps(scene.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    preview_path = case_dir / SCENE_PREVIEW_NAME
    PngRenderer().render(scene, preview_path)

    unresolved = tuple(
        node.id
        for node in scene.nodes
        if getattr(node, "asset_unresolved", False)
    )
    return SceneRenderResult(
        scene=scene,
        scene_path=scene_path,
        scene_preview_path=preview_path,
        scene_hash=compute_scene_hash(scene),
        unresolved_nodes=unresolved,
    )


def export_benchmark_pptx_from_scene(
    scene: RenderScene,
    case_dir: Path,
    *,
    title: str,
    speaker_notes: str | None = None,
) -> tuple[Path | None, list[str]]:
    """Export editable PPTX from RenderScene."""
    pptx_path = case_dir / PPTX_NAME
    exported = maybe_export_scene_pptx(
        scene,
        pptx_path,
        title=title,
        speaker_notes=speaker_notes,
    )
    fallbacks = PptxRenderer().font_fallbacks(scene) if exported else []
    return exported, fallbacks


def export_benchmark_pptx(
    result: BenchmarkCaseResult,
    case_dir: Path,
    *,
    scene: RenderScene,
    assets_dir: Path | None = None,
) -> tuple[Path | None, SlideContentBundleBuildResult, list[str]]:
    """Export a content-complete PPTX for one benchmark case from RenderScene."""
    assets = assets_dir or (case_dir / "assets")
    build = build_slide_content_bundle(result.plan, assets, result.slide)
    pptx_path, fallbacks = export_benchmark_pptx_from_scene(
        scene,
        case_dir,
        title=result.slide.title,
        speaker_notes=result.slide.speaker_notes or None,
    )
    return pptx_path, build, fallbacks


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
    """Export RenderScene preview, PPTX, and optional final-render PNG."""
    scene_render = compile_and_render_scene(result, case_dir)
    pptx_path, build, font_fallbacks = export_benchmark_pptx(
        result,
        case_dir,
        scene=scene_render.scene,
    )
    conformance_issues: list[str] = []
    if pptx_path is not None and pptx_path.is_file():
        conformance = assert_renderer_conformance(
            scene_render.scene,
            pptx_path=pptx_path,
        )
        conformance_issues = conformance.issues

    final_render = None
    renderer = "png_renderer+pptxgenjs"
    rendered_at = datetime.now(UTC)
    notes: list[str] = [
        "RenderScene compiled from LayoutPlan with resolved text and assets.",
        f"scene_preview.png rendered via png_renderer.",
    ]

    if pptx_path is None or not pptx_path.is_file():
        notes.append("PPTX export skipped (Node/PptxGenJS unavailable).")
        renderer = "png_renderer"
    else:
        notes.append("PPTX exported from RenderScene via render-plan.mjs.")
        if font_fallbacks:
            notes.append(f"Font fallbacks recorded: {', '.join(font_fallbacks)}.")
        if conformance_issues:
            notes.append("Renderer conformance: " + "; ".join(conformance_issues[:3]))
        final_render = export_benchmark_final_render(pptx_path, case_dir)
        if final_render is not None:
            notes.append("final_render.png rasterized from output.pptx.")
        elif not screenshot_tools_available():
            notes.append(
                "Screenshot tools unavailable (LibreOffice + pdftoppm); "
                "final_render.png not produced."
            )

    asset_count, curated_count, placeholder_count = count_assets(case_dir)
    scene_ok = scene_render.scene_preview_path.is_file()
    render_valid = (
        scene_ok
        and not build.missing_content_refs
        and not scene_render.unresolved_nodes
        and placeholder_count == 0
        and not conformance_issues
    )
    if build.missing_content_refs:
        notes.append(
            "Unresolved content_ref paths: "
            + ", ".join(build.missing_content_refs[:5])
            + (" …" if len(build.missing_content_refs) > 5 else "")
        )
    if scene_render.unresolved_nodes:
        notes.append(
            "Unresolved scene nodes: "
            + ", ".join(scene_render.unresolved_nodes[:5])
        )
    if placeholder_count > 0:
        notes.append(
            "Some assets remain placeholder diagrams; scene preview stays invalid "
            "until all case assets are curated."
        )
    elif curated_count > 0:
        notes.append("All mapped assets are curated PNGs from the benchmark asset pool.")

    render_source = "html" if scene_ok else "pending"
    if final_render is not None:
        render_source = "pptx_screenshot"

    manifest = BenchmarkRenderManifest(
        render_source=render_source,
        pptx_path=PPTX_NAME,
        image_path=FINAL_RENDER_NAME,
        scene_path=SCENE_JSON_NAME,
        scene_preview_path=SCENE_PREVIEW_NAME,
        scene_id=str(scene_render.scene.id),
        scene_hash=scene_render.scene_hash,
        rendered_at=rendered_at,
        renderer=renderer if scene_ok else "",
        asset_count=asset_count,
        real_asset_count=curated_count,
        placeholder_asset_count=placeholder_count,
        font_fallbacks=font_fallbacks,
        missing_assets=list(build.missing_content_refs),
        render_valid=render_valid,
        notes=" ".join(notes),
    )
    write_render_manifest(case_dir, manifest)
    return manifest

"""Rendered Visual Benchmark pipeline for architectural slide cases."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from archium.application.visual.asset_path_resolver import (
    AssetPathResolveContext,
    AssetPathResolver,
    benchmark_asset_uri,
    scene_has_machine_absolute_paths,
)
from archium.application.visual.benchmark_service import BenchmarkCaseResult
from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.domain.slide import SlideSpec
from archium.domain.visual.benchmark import BenchmarkRenderManifest
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash
from archium.infrastructure.renderers.png_renderer import PngRenderer
from archium.infrastructure.renderers.pptx_renderer import PptxRenderer, maybe_export_scene_pptx
from archium.infrastructure.renderers.pptx_screenshot import (
    export_pptx_slide_pngs,
    screenshot_tools_available,
)
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle
from archium.infrastructure.renderers.renderer_conformance import assert_renderer_conformance

from tests.benchmark.architectural_slides.render_manifest import (
    FINAL_RENDER_NAME,
    PPTX_NAME,
    PPTX_RENDER_NAME,
    SCENE_JSON_NAME,
    SCENE_PREVIEW_NAME,
    count_assets,
    ensure_pptx_render_alias,
    run_post_render_qa,
    sha256_file,
    write_pptx_render_sidecar,
    write_pptx_sidecar,
    write_render_manifest,
)
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


def _case_id_from_assets_dir(assets_dir: Path, case_dir: Path | None = None) -> str:
    if case_dir is not None:
        return case_dir.name
    return assets_dir.parent.name


def _resolve_ctx(case_dir: Path, assets_dir: Path | None = None) -> AssetPathResolveContext:
    assets = assets_dir or (case_dir / "assets")
    return AssetPathResolveContext(
        case_dir=case_dir,
        case_id=case_dir.name,
        assets_dir=assets,
        benchmark_root=case_dir.parent,
    )


def build_slide_content_bundle(
    plan: LayoutPlan,
    assets_dir: Path,
    slide: SlideSpec,
    *,
    case_id: str | None = None,
) -> SlideContentBundleBuildResult:
    """Map LayoutPlan content_ref values to portable benchmark asset URIs."""
    resolved_case_id = case_id or _case_id_from_assets_dir(assets_dir)
    asset_paths: dict[str, str] = {}
    missing: list[str] = []
    for element in plan.elements:
        if not element.content_ref:
            continue
        asset_file = assets_dir / f"{element.content_ref}.png"
        if asset_file.is_file():
            asset_paths[element.content_ref] = benchmark_asset_uri(
                resolved_case_id,
                f"assets/{element.content_ref}.png",
            )
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
    build = build_slide_content_bundle(
        result.plan,
        assets,
        result.slide,
        case_id=case_dir.name,
    )
    compiler = RenderSceneCompiler()
    scene = compiler.compile(
        slide=result.slide,
        layout_plan=result.plan,
        design_system=result.design_system,
        content_bundle=build.bundle,
        visual_intent=result.intent,
    )
    resolver = AssetPathResolver()
    ctx = _resolve_ctx(case_dir, assets)
    scene = resolver.portableize_scene(scene, ctx)

    scene_path = case_dir / SCENE_JSON_NAME
    scene_path.write_text(
        json.dumps(scene.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    preview_path = case_dir / SCENE_PREVIEW_NAME
    render_scene = resolver.resolve_scene(scene, ctx)
    PngRenderer().render(render_scene, preview_path)

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
    """Export editable PPTX from RenderScene (resolves portable URIs first)."""
    pptx_path = case_dir / PPTX_NAME
    render_scene = AssetPathResolver().resolve_scene(scene, _resolve_ctx(case_dir))
    exported = maybe_export_scene_pptx(
        render_scene,
        pptx_path,
        title=title,
        speaker_notes=speaker_notes,
    )
    fallbacks = PptxRenderer().font_fallbacks(render_scene) if exported else []
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
    build = build_slide_content_bundle(
        result.plan,
        assets,
        result.slide,
        case_id=case_dir.name,
    )
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
    render_attempt_id = uuid4()
    scene_render = compile_and_render_scene(result, case_dir)
    pptx_path, build, font_fallbacks = export_benchmark_pptx(
        result,
        case_dir,
        scene=scene_render.scene,
    )
    conformance_issues: list[str] = []
    if pptx_path is not None and pptx_path.is_file():
        render_scene = AssetPathResolver().resolve_scene(
            scene_render.scene,
            _resolve_ctx(case_dir),
        )
        conformance = assert_renderer_conformance(
            render_scene,
            pptx_path=pptx_path,
        )
        conformance_issues = conformance.issues

    tools_available = screenshot_tools_available()
    pptx_screenshot_generated = False
    pptx_screenshot_reused = False
    final_render = None
    renderer = "png_renderer+pptxgenjs"
    rendered_at = datetime.now(UTC)

    if pptx_path is None or not pptx_path.is_file():
        renderer = "png_renderer"
    else:
        final_render = export_benchmark_final_render(pptx_path, case_dir)
        if final_render is not None:
            pptx_screenshot_generated = True

    existing_pptx_render = (case_dir / PPTX_RENDER_NAME).is_file()
    pptx_render = ensure_pptx_render_alias(case_dir)
    if pptx_render is not None:
        if pptx_screenshot_generated:
            pass
        elif existing_pptx_render and final_render is None:
            pptx_screenshot_reused = True
        elif final_render is not None:
            pptx_screenshot_generated = True

    asset_count, curated_count, placeholder_count = count_assets(case_dir)
    scene_ok = scene_render.scene_preview_path.is_file()
    absolute_paths = scene_has_machine_absolute_paths(scene_render.scene)
    render_valid = (
        scene_ok
        and not build.missing_content_refs
        and not scene_render.unresolved_nodes
        and placeholder_count == 0
        and not conformance_issues
        and not absolute_paths
    )

    render_source = "html" if scene_ok else "pending"
    if pptx_render is not None and (pptx_screenshot_generated or pptx_screenshot_reused):
        render_source = "pptx_screenshot"

    scene_hash = scene_render.scene_hash
    pptx_content_hash = ""
    if pptx_path is not None and pptx_path.is_file():
        pptx_content_hash = sha256_file(pptx_path)
        write_pptx_sidecar(
            case_dir,
            scene_hash=scene_hash,
            pptx_content_hash=pptx_content_hash,
        )
    if pptx_render is not None:
        write_pptx_render_sidecar(
            case_dir,
            scene_hash=scene_hash,
            pptx_content_hash=pptx_content_hash,
        )

    qa_ok, qa_issues = run_post_render_qa(case_dir, scene_render.scene)
    if not qa_ok:
        render_valid = False

    # Structured evidence only — notes is a short non-authoritative summary.
    evidence_bits: list[str] = []
    if not tools_available:
        evidence_bits.append("screenshot_tools_available=false")
    if pptx_screenshot_generated:
        evidence_bits.append("pptx_screenshot_generated=true")
    if pptx_screenshot_reused:
        evidence_bits.append("pptx_screenshot_reused=true")
    if absolute_paths:
        evidence_bits.append("non_portable_asset_paths=true")
        render_valid = False
    if not qa_ok:
        evidence_bits.append("post_render_qa_passed=false")

    manifest = BenchmarkRenderManifest(
        render_source=render_source,
        pptx_path=PPTX_NAME,
        image_path=PPTX_RENDER_NAME,
        scene_path=SCENE_JSON_NAME,
        scene_preview_path=SCENE_PREVIEW_NAME,
        scene_id=str(scene_render.scene.id),
        scene_hash=scene_hash,
        rendered_at=rendered_at,
        renderer=renderer if scene_ok else "",
        asset_count=asset_count,
        real_asset_count=curated_count,
        placeholder_asset_count=placeholder_count,
        font_fallbacks=font_fallbacks,
        missing_assets=list(build.missing_content_refs),
        render_valid=render_valid,
        notes="; ".join(evidence_bits),
        screenshot_tools_available=tools_available,
        pptx_screenshot_generated=pptx_screenshot_generated,
        pptx_screenshot_reused=pptx_screenshot_reused,
        pptx_screenshot_source_hash=scene_hash if pptx_render is not None else "",
        render_attempt_id=render_attempt_id,
        pptx_content_hash=pptx_content_hash,
        post_render_qa_passed=qa_ok,
        post_render_qa_issues=qa_issues,
    )
    write_render_manifest(case_dir, manifest)
    return manifest

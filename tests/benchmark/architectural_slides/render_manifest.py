"""Render manifest helpers for architectural slide benchmark cases."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from archium.application.visual.asset_path_resolver import (
    AssetPathResolveContext,
    AssetPathResolver,
    scene_has_machine_absolute_paths,
)
from archium.application.visual.scene_fonts import detect_font_fallbacks, repair_scene_fonts
from archium.domain.visual.benchmark import BenchmarkRenderManifest
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash

RENDER_MANIFEST_NAME = "render_manifest.json"
WIREFRAME_NAME = "wireframe.png"
FINAL_RENDER_NAME = "final_render.png"
PPTX_RENDER_NAME = "pptx_render.png"
PPTX_RENDER_SIDECAR_NAME = "pptx_render.meta.json"
PPTX_NAME = "output.pptx"
PPTX_SIDECAR_NAME = "output.pptx.meta.json"
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


def pptx_render_sidecar_path(case_dir: Path) -> Path:
    return case_dir / PPTX_RENDER_SIDECAR_NAME


def pptx_path(case_dir: Path) -> Path:
    return case_dir / PPTX_NAME


def pptx_sidecar_path(case_dir: Path) -> Path:
    return case_dir / PPTX_SIDECAR_NAME


def final_render_path(case_dir: Path) -> Path:
    return case_dir / FINAL_RENDER_NAME


def render_manifest_path(case_dir: Path) -> Path:
    return case_dir / RENDER_MANIFEST_NAME


def sha256_file(path: Path) -> str:
    """Return hex SHA-256 of a file (used for PPTX / screenshot provenance)."""
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


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


def write_pptx_sidecar(
    case_dir: Path,
    *,
    scene_hash: str,
    pptx_content_hash: str,
) -> Path:
    """Write provenance sidecar next to output.pptx."""
    path = pptx_sidecar_path(case_dir)
    path.write_text(
        json.dumps(
            {
                "scene_hash": scene_hash,
                "pptx_content_hash": pptx_content_hash,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def write_pptx_render_sidecar(
    case_dir: Path,
    *,
    scene_hash: str,
    pptx_content_hash: str = "",
) -> Path:
    """Write scene_hash (+ optional pptx hash) sidecar next to pptx_render.png."""
    path = pptx_render_sidecar_path(case_dir)
    payload: dict[str, str] = {"scene_hash": scene_hash}
    if pptx_content_hash:
        payload["pptx_content_hash"] = pptx_content_hash
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_json_sidecar(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def load_pptx_render_sidecar(case_dir: Path) -> dict[str, Any] | None:
    return load_json_sidecar(pptx_render_sidecar_path(case_dir))


def load_pptx_sidecar(case_dir: Path) -> dict[str, Any] | None:
    return load_json_sidecar(pptx_sidecar_path(case_dir))


def load_case_scene(case_dir: Path) -> RenderScene | None:
    path = case_dir / SCENE_JSON_NAME
    if not path.is_file():
        return None
    try:
        return RenderScene.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _asset_resolve_context(case_dir: Path) -> AssetPathResolveContext:
    return AssetPathResolveContext(
        case_dir=case_dir,
        case_id=case_dir.name,
        assets_dir=case_dir / "assets",
        benchmark_root=case_dir.parent,
    )


def validate_asset_uris_resolvable(case_dir: Path, scene: RenderScene) -> list[str]:
    """Ensure every scene asset URI resolves to an on-disk file for this case."""
    from archium.application.visual.asset_path_resolver import iter_scene_asset_uris
    from archium.domain.visual.render_scene import DrawingNode, ImageNode

    blockers: list[str] = []
    resolver = AssetPathResolver()
    ctx = _asset_resolve_context(case_dir)
    for uri in iter_scene_asset_uris(scene):
        if not uri:
            continue
        resolved = resolver.resolve(uri, ctx)
        if resolved is None or not resolved.is_file():
            blockers.append(f"unresolvable asset URI: {uri[:96]}")
    for node in scene.nodes:
        if isinstance(node, (ImageNode, DrawingNode)) and node.asset_unresolved:
            blockers.append(f"unresolved asset node: {node.id}")
    return blockers


def validate_font_state(scene: RenderScene) -> list[str]:
    """Block Latin-primary on CJK text; require font_assets for used roles."""
    from archium.application.visual.scene_fonts import (
        DEFAULT_CJK_FONT,
        DEFAULT_LATIN_FONT,
        text_has_cjk,
    )
    from archium.domain.visual.render_scene import TextNode

    blockers: list[str] = []
    for node in scene.nodes:
        if not isinstance(node, TextNode) or not text_has_cjk(node.text):
            continue
        latin = node.font_family_latin or DEFAULT_LATIN_FONT
        cjk = node.font_family_cjk or DEFAULT_CJK_FONT
        if node.font_family == latin and latin != cjk:
            blockers.append(
                f"font state invalid: node `{node.id}` uses Latin primary "
                f"`{latin}` for CJK text (expected `{cjk}`)"
            )
    if any(isinstance(n, TextNode) and n.text.strip() for n in scene.nodes):
        if not scene.font_assets:
            blockers.append("font_assets empty while scene has text nodes")
    # Recorded Latin→CJK glyph substitutions mean the scene was not repaired.
    for note in detect_font_fallbacks(scene):
        if "Latin family lacks CJK glyphs" in note:
            blockers.append(f"font fallback unresolved: {note}")
    return blockers


def run_post_render_qa(case_dir: Path, scene: RenderScene) -> tuple[bool, list[str]]:
    """Run Scene↔PPTX conformance (+ light semantic checks)."""
    from uuid import uuid4

    from archium.application.visual.asset_path_resolver import AssetPathResolver
    from archium.application.visual.scene_semantic_qa_service import run_scene_semantic_qa
    from archium.domain.visual.scene_qa import SceneSemanticCheckCode
    from archium.infrastructure.renderers.renderer_conformance import (
        assert_renderer_conformance,
    )

    hard_codes = frozenset(
        {
            SceneSemanticCheckCode.FONT_FALLBACK_CHANGED_LAYOUT,
            SceneSemanticCheckCode.IMAGE_NOT_RENDERED,
            SceneSemanticCheckCode.SCENE_PPTX_NODE_MISMATCH,
        }
    )
    issues: list[str] = []
    render_scene = AssetPathResolver().resolve_scene(scene, _asset_resolve_context(case_dir))
    pptx = pptx_path(case_dir)
    try:
        conformance = assert_renderer_conformance(
            render_scene,
            pptx_path=pptx if pptx.is_file() else None,
        )
        if not conformance.passed:
            issues.extend(conformance.issues[:8])
    except Exception as exc:  # noqa: BLE001 — gate must not crash on corrupt PPTX
        issues.append(f"pptx conformance error: {exc}")

    try:
        report = run_scene_semantic_qa(
            uuid4(),
            [scene],
            pptx_paths_by_slide={scene.slide_id: pptx} if pptx.is_file() else None,
            slide_orders={scene.slide_id: 0},
        )
        for finding in report.findings:
            if finding.check_code in hard_codes:
                issues.append(f"{finding.check_code}: {finding.title}")
    except Exception as exc:  # noqa: BLE001
        issues.append(f"semantic QA error: {exc}")
    return (not issues, issues)


def validate_scene_manifest_consistency(case_dir: Path) -> list[str]:
    """Strict same-generation provenance gate for visual human review.

    Checks: scene_id / scene_hash identity, portable + resolvable asset URIs,
    font state, PPTX content hash chain, screenshot↔PPTX hash, post-render QA.
    """
    blockers: list[str] = []
    manifest = load_render_manifest(case_dir)
    scene = load_case_scene(case_dir)
    if manifest is None:
        blockers.append("缺少 render_manifest.json")
        return blockers
    if scene is None:
        blockers.append("缺少或无法解析 scene.json")
        return blockers

    if not manifest.scene_id:
        blockers.append("manifest.scene_id missing")
    elif str(scene.id) != manifest.scene_id:
        blockers.append(
            f"scene_id mismatch: scene={scene.id} manifest={manifest.scene_id}"
        )

    expected_hash = compute_scene_hash(scene)
    if not manifest.scene_hash:
        blockers.append("manifest.scene_hash missing")
    elif manifest.scene_hash != expected_hash:
        blockers.append(
            "scene_hash mismatch: "
            f"recomputed={expected_hash[:12]}… manifest={manifest.scene_hash[:12]}…"
        )

    absolute = scene_has_machine_absolute_paths(scene)
    if absolute:
        blockers.append(f"non-portable asset paths ({len(absolute)})")

    blockers.extend(validate_asset_uris_resolvable(case_dir, scene))
    blockers.extend(validate_font_state(scene))

    pptx_file = pptx_path(case_dir)
    actual_pptx_hash = ""
    if pptx_file.is_file():
        actual_pptx_hash = sha256_file(pptx_file)
        if not manifest.pptx_content_hash:
            blockers.append("manifest.pptx_content_hash missing")
        elif manifest.pptx_content_hash != actual_pptx_hash:
            blockers.append(
                "pptx_content_hash mismatch: "
                f"file={actual_pptx_hash[:12]}… manifest={manifest.pptx_content_hash[:12]}…"
            )
        pptx_meta = load_pptx_sidecar(case_dir)
        if pptx_meta is None:
            blockers.append(f"缺少 {PPTX_SIDECAR_NAME}")
        else:
            meta_scene = str(pptx_meta.get("scene_hash") or "")
            meta_pptx = str(pptx_meta.get("pptx_content_hash") or "")
            if not meta_scene:
                blockers.append("output.pptx sidecar scene_hash missing")
            elif manifest.scene_hash and meta_scene != manifest.scene_hash:
                blockers.append("output.pptx sidecar scene_hash mismatch vs manifest")
            if not meta_pptx:
                blockers.append("output.pptx sidecar pptx_content_hash missing")
            elif meta_pptx != actual_pptx_hash:
                blockers.append("output.pptx sidecar pptx_content_hash mismatch vs file")
            elif manifest.pptx_content_hash and meta_pptx != manifest.pptx_content_hash:
                blockers.append("output.pptx sidecar pptx_content_hash mismatch vs manifest")

    pptx_png = pptx_render_path(case_dir)
    if pptx_png.is_file():
        sidecar = load_pptx_render_sidecar(case_dir)
        if sidecar is None:
            blockers.append(f"缺少 {PPTX_RENDER_SIDECAR_NAME}")
        else:
            sidecar_hash = str(sidecar.get("scene_hash") or "")
            sidecar_pptx = str(sidecar.get("pptx_content_hash") or "")
            if not sidecar_hash:
                blockers.append("pptx_render sidecar scene_hash missing")
            elif manifest.scene_hash and sidecar_hash != manifest.scene_hash:
                blockers.append(
                    "pptx_render sidecar scene_hash mismatch vs manifest.scene_hash"
                )
            if (
                manifest.pptx_screenshot_source_hash
                and sidecar_hash
                and sidecar_hash != manifest.pptx_screenshot_source_hash
            ):
                blockers.append(
                    "pptx_render sidecar scene_hash mismatch vs "
                    "manifest.pptx_screenshot_source_hash"
                )
            if not sidecar_pptx:
                blockers.append("pptx_render sidecar pptx_content_hash missing")
            elif actual_pptx_hash and sidecar_pptx != actual_pptx_hash:
                blockers.append(
                    "pptx_render sidecar pptx_content_hash mismatch vs output.pptx"
                )
            elif (
                manifest.pptx_content_hash
                and sidecar_pptx
                and sidecar_pptx != manifest.pptx_content_hash
            ):
                blockers.append(
                    "pptx_render sidecar pptx_content_hash mismatch vs manifest"
                )

    qa_ok, qa_issues = run_post_render_qa(case_dir, scene)
    if not qa_ok:
        blockers.append("post-render QA failed: " + "; ".join(qa_issues[:4]))
    elif not manifest.post_render_qa_passed:
        blockers.append("manifest.post_render_qa_passed=false")

    return blockers


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
        screenshot_tools_available=False,
        pptx_screenshot_generated=False,
        pptx_screenshot_reused=False,
        pptx_screenshot_source_hash="",
        render_attempt_id=uuid4(),
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


def normalize_case_scene_portability(case_dir: Path) -> dict[str, Any]:
    """Rewrite absolute asset paths in scene.json and resync manifest identity fields.

    Does not regenerate PNG/PPTX pixels — only repairs provenance metadata so
    consistency gates can pass after the portable-URI policy landed.
    """
    scene = load_case_scene(case_dir)
    if scene is None:
        return {"ok": False, "error": "scene.json missing or invalid"}

    resolver = AssetPathResolver()
    ctx = AssetPathResolveContext(
        case_dir=case_dir,
        case_id=case_dir.name,
        assets_dir=case_dir / "assets",
        benchmark_root=case_dir.parent,
    )
    portable = resolver.portableize_scene(scene, ctx)
    portable = repair_scene_fonts(portable)
    scene_hash = compute_scene_hash(portable)
    scene_path = case_dir / SCENE_JSON_NAME
    scene_path.write_text(
        json.dumps(portable.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = load_render_manifest(case_dir)
    absolute_left = scene_has_machine_absolute_paths(portable)
    pptx_file = pptx_path(case_dir)
    pptx_png = pptx_render_path(case_dir)
    pptx_content_hash = sha256_file(pptx_file) if pptx_file.is_file() else ""
    if pptx_file.is_file() and pptx_content_hash:
        write_pptx_sidecar(
            case_dir,
            scene_hash=scene_hash,
            pptx_content_hash=pptx_content_hash,
        )
    if pptx_png.is_file():
        write_pptx_render_sidecar(
            case_dir,
            scene_hash=scene_hash,
            pptx_content_hash=pptx_content_hash,
        )

    qa_ok, qa_issues = run_post_render_qa(case_dir, portable)

    if manifest is None:
        return {
            "ok": not absolute_left and qa_ok,
            "scene_id": str(portable.id),
            "scene_hash": scene_hash,
            "absolute_paths_remaining": len(absolute_left),
            "manifest_updated": False,
        }

    consistency_ok = not absolute_left and qa_ok
    render_valid = bool(manifest.render_valid) and consistency_ok
    pptx_exists = pptx_png.is_file()
    font_fallbacks = detect_font_fallbacks(portable)
    updated = manifest.model_copy(
        update={
            "scene_id": str(portable.id),
            "scene_hash": scene_hash,
            "pptx_content_hash": pptx_content_hash,
            "font_fallbacks": font_fallbacks,
            "pptx_screenshot_source_hash": scene_hash if pptx_exists else "",
            "pptx_screenshot_generated": (
                manifest.pptx_screenshot_generated if pptx_exists else False
            ),
            "pptx_screenshot_reused": (
                True
                if pptx_exists and not manifest.pptx_screenshot_generated
                else manifest.pptx_screenshot_reused
            ),
            "post_render_qa_passed": qa_ok,
            "post_render_qa_issues": qa_issues,
            "render_valid": render_valid,
            "notes": (
                "normalized_portable_uris=true"
                + ("; absolute_paths_remaining" if absolute_left else "")
            ),
        }
    )
    write_render_manifest(case_dir, updated)
    blockers = validate_scene_manifest_consistency(case_dir)
    if blockers:
        updated = updated.model_copy(update={"render_valid": False})
        write_render_manifest(case_dir, updated)
        consistency_ok = False

    return {
        "ok": consistency_ok and not blockers,
        "scene_id": str(portable.id),
        "scene_hash": scene_hash,
        "absolute_paths_remaining": len(absolute_left),
        "manifest_updated": True,
        "blockers": blockers,
        "render_valid": updated.render_valid,
    }


def visual_review_eligibility(
    case_dir: Path,
) -> tuple[bool, BenchmarkRenderManifest | None, list[str]]:
    """Return whether Rendered Visual human review may proceed (Phase 9 gates)."""
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
    if not pptx_render_path(case_dir).is_file():
        blockers.append(f"缺少 {PPTX_RENDER_NAME}")
    consistency = validate_scene_manifest_consistency(case_dir)
    if consistency:
        blockers.extend(consistency)
        if manifest is not None and manifest.render_valid:
            blockers.append("render_valid overridden by consistency failure")
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
    asset_count, _curated_count, placeholder_count = count_assets(case_dir)
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

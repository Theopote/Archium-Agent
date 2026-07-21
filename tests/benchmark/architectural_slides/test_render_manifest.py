"""Tests for benchmark render manifest and visual review eligibility."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from archium.domain.visual.benchmark import BenchmarkRenderManifest
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    RenderScene,
    SceneAssetReference,
    compute_scene_hash,
)

from tests.benchmark.architectural_slides.render_manifest import (
    SCENE_JSON_NAME,
    SCENE_PREVIEW_NAME,
    bootstrap_case_render_artifacts,
    editability_review_eligibility,
    normalize_case_scene_portability,
    sha256_file,
    validate_scene_manifest_consistency,
    visual_review_eligibility,
    write_pptx_render_sidecar,
    write_pptx_sidecar,
    write_render_manifest,
)


def _write_minimal_scene(case_dir: Path) -> RenderScene:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[],
    )
    (case_dir / SCENE_JSON_NAME).write_text(
        json.dumps(scene.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return scene


def _write_empty_pptx(path: Path) -> str:
    from pptx import Presentation

    Presentation().save(str(path))
    return sha256_file(path)


def _write_full_provenance(
    case_dir: Path,
    scene: RenderScene,
    *,
    render_valid: bool = True,
    scene_id: str | None = None,
) -> str:
    scene_hash = compute_scene_hash(scene)
    pptx_hash = _write_empty_pptx(case_dir / "output.pptx")
    (case_dir / "pptx_render.png").write_bytes(b"png")
    write_pptx_sidecar(case_dir, scene_hash=scene_hash, pptx_content_hash=pptx_hash)
    write_pptx_render_sidecar(
        case_dir,
        scene_hash=scene_hash,
        pptx_content_hash=pptx_hash,
    )
    write_render_manifest(
        case_dir,
        BenchmarkRenderManifest(
            render_source="pptx_screenshot",
            render_valid=render_valid,
            scene_id=scene_id or str(scene.id),
            scene_hash=scene_hash,
            asset_count=0,
            real_asset_count=0,
            placeholder_asset_count=0,
            rendered_at=datetime.now(UTC),
            renderer="test",
            screenshot_tools_available=True,
            pptx_screenshot_generated=True,
            pptx_screenshot_reused=False,
            pptx_screenshot_source_hash=scene_hash,
            pptx_content_hash=pptx_hash,
            post_render_qa_passed=True,
            post_render_qa_issues=[],
        ),
    )
    return scene_hash


def test_pending_manifest_blocks_visual_review(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / "preview.png").write_bytes(b"png")
    bootstrap_case_render_artifacts(case_dir)
    eligible, manifest, blockers = visual_review_eligibility(case_dir)
    assert manifest is not None
    assert manifest.render_valid is False
    assert eligible is False
    assert any(SCENE_PREVIEW_NAME in item for item in blockers)


def test_valid_manifest_and_scene_preview_allows_visual_review(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / SCENE_PREVIEW_NAME).write_bytes(b"png")
    scene = _write_minimal_scene(case_dir)
    _write_full_provenance(case_dir, scene)
    eligible, _, blockers = visual_review_eligibility(case_dir)
    assert eligible is True, blockers
    assert blockers == []
    edit_ok, edit_blockers = editability_review_eligibility(case_dir)
    assert edit_ok is True
    assert edit_blockers == []


def test_reused_screenshot_blocks_formal_visual_review_but_allows_editability(
    tmp_path: Path,
) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / SCENE_PREVIEW_NAME).write_bytes(b"png")
    scene = _write_minimal_scene(case_dir)
    _write_full_provenance(case_dir, scene)
    manifest = BenchmarkRenderManifest.model_validate_json(
        (case_dir / "render_manifest.json").read_text(encoding="utf-8")
    )
    write_render_manifest(
        case_dir,
        manifest.model_copy(
            update={
                "screenshot_tools_available": False,
                "pptx_screenshot_generated": False,
                "pptx_screenshot_reused": True,
            }
        ),
    )
    eligible, _, blockers = visual_review_eligibility(case_dir)
    assert eligible is False
    assert any("pptx_screenshot_generated=false" in item for item in blockers)
    assert any("pptx_screenshot_reused=true" in item for item in blockers)
    edit_ok, edit_blockers = editability_review_eligibility(case_dir)
    assert edit_ok is True, edit_blockers


def test_scene_id_mismatch_blocks_visual_review(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / SCENE_PREVIEW_NAME).write_bytes(b"png")
    scene = _write_minimal_scene(case_dir)
    _write_full_provenance(case_dir, scene, scene_id=str(uuid4()))
    eligible, _, blockers = visual_review_eligibility(case_dir)
    assert eligible is False
    assert any("scene_id mismatch" in item for item in blockers)
    assert any("consistency" in item for item in blockers)


def test_pptx_hash_mismatch_blocks_visual_review(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / SCENE_PREVIEW_NAME).write_bytes(b"png")
    scene = _write_minimal_scene(case_dir)
    _write_full_provenance(case_dir, scene)
    # Corrupt declared PPTX hash while leaving file sidecars stale.
    manifest = BenchmarkRenderManifest.model_validate_json(
        (case_dir / "render_manifest.json").read_text(encoding="utf-8")
    )
    write_render_manifest(
        case_dir,
        manifest.model_copy(update={"pptx_content_hash": "0" * 64}),
    )
    eligible, _, blockers = visual_review_eligibility(case_dir)
    assert eligible is False
    assert any("pptx_content_hash mismatch" in item for item in blockers)


def test_missing_pptx_render_blocks_visual_review(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / SCENE_PREVIEW_NAME).write_bytes(b"png")
    scene = _write_minimal_scene(case_dir)
    (case_dir / "output.pptx").write_bytes(b"pptx")
    write_render_manifest(
        case_dir,
        BenchmarkRenderManifest(
            render_source="html",
            render_valid=True,
            scene_id=str(scene.id),
            scene_hash=compute_scene_hash(scene),
            asset_count=1,
            real_asset_count=1,
            placeholder_asset_count=0,
            rendered_at=datetime.now(UTC),
            renderer="test",
            post_render_qa_passed=True,
        ),
    )
    eligible, _, blockers = visual_review_eligibility(case_dir)
    assert eligible is False
    assert any("pptx_render.png" in item for item in blockers)


def test_placeholder_assets_block_visual_review(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / SCENE_PREVIEW_NAME).write_bytes(b"png")
    scene = _write_minimal_scene(case_dir)
    write_render_manifest(
        case_dir,
        BenchmarkRenderManifest(
            render_source="html",
            render_valid=True,
            scene_id=str(scene.id),
            scene_hash=compute_scene_hash(scene),
            asset_count=2,
            real_asset_count=0,
            placeholder_asset_count=2,
            rendered_at=datetime.now(UTC),
            renderer="test",
            post_render_qa_passed=True,
        ),
    )
    eligible, _, blockers = visual_review_eligibility(case_dir)
    assert eligible is False
    assert any("placeholder_asset_count" in item for item in blockers)


def test_normalize_rewrites_absolute_and_resyncs_manifest(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_002_site_photos"
    assets = case_dir / "assets"
    assets.mkdir(parents=True)
    asset = assets / "photo.png"
    asset.write_bytes(b"png")
    absolute = str(asset.resolve())
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[],
        asset_manifest=[SceneAssetReference(asset_path=absolute)],
    )
    (case_dir / SCENE_JSON_NAME).write_text(
        json.dumps(scene.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_empty_pptx(case_dir / "output.pptx")
    (case_dir / "pptx_render.png").write_bytes(b"png")
    write_render_manifest(
        case_dir,
        BenchmarkRenderManifest(
            render_source="pptx_screenshot",
            render_valid=True,
            scene_id=str(uuid4()),
            scene_hash="deadbeef",
            placeholder_asset_count=0,
        ),
    )
    result = normalize_case_scene_portability(case_dir)
    assert result["ok"] is True, result
    blockers = validate_scene_manifest_consistency(case_dir)
    assert blockers == [], blockers
    rewritten = json.loads((case_dir / SCENE_JSON_NAME).read_text(encoding="utf-8"))
    assert rewritten["asset_manifest"][0]["storage_uri"].startswith("benchmark://")
    assert "C:" not in rewritten["asset_manifest"][0]["storage_uri"]

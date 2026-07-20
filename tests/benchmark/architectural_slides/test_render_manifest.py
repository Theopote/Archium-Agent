"""Tests for benchmark render manifest and visual review eligibility."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from archium.domain.visual.benchmark import BenchmarkRenderManifest
from tests.benchmark.architectural_slides.render_manifest import (
    SCENE_JSON_NAME,
    SCENE_PREVIEW_NAME,
    bootstrap_case_render_artifacts,
    editability_review_eligibility,
    visual_review_eligibility,
    write_render_manifest,
)


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
    (case_dir / SCENE_JSON_NAME).write_text("{}", encoding="utf-8")
    (case_dir / "output.pptx").write_bytes(b"pptx")
    write_render_manifest(
        case_dir,
        BenchmarkRenderManifest(
            render_source="html",
            render_valid=True,
            scene_hash="deadbeef",
            asset_count=2,
            real_asset_count=2,
            placeholder_asset_count=0,
            rendered_at=datetime.now(UTC),
            renderer="test",
        ),
    )
    eligible, _, blockers = visual_review_eligibility(case_dir)
    assert eligible is True
    assert blockers == []
    edit_ok, edit_blockers = editability_review_eligibility(case_dir)
    assert edit_ok is True
    assert edit_blockers == []


def test_placeholder_assets_block_visual_review(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / SCENE_PREVIEW_NAME).write_bytes(b"png")
    (case_dir / "output.pptx").write_bytes(b"pptx")
    write_render_manifest(
        case_dir,
        BenchmarkRenderManifest(
            render_source="html",
            render_valid=True,
            scene_hash="abc",
            asset_count=2,
            real_asset_count=0,
            placeholder_asset_count=2,
            rendered_at=datetime.now(UTC),
            renderer="test",
        ),
    )
    eligible, _, blockers = visual_review_eligibility(case_dir)
    assert eligible is False
    assert any("placeholder_asset_count" in item for item in blockers)

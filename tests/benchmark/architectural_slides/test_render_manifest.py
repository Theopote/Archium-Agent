"""Tests for benchmark render manifest and visual review eligibility."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from archium.domain.visual.benchmark import BenchmarkRenderManifest, HumanVisualReviewSource
from tests.benchmark.architectural_slides.render_manifest import (
    bootstrap_case_render_artifacts,
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
    assert any("final_render.png" in item for item in blockers)


def test_valid_manifest_and_final_render_allows_visual_review(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / "final_render.png").write_bytes(b"png")
    write_render_manifest(
        case_dir,
        BenchmarkRenderManifest(
            render_source="pptx_screenshot",
            render_valid=True,
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


def test_placeholder_assets_block_visual_review(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / "final_render.png").write_bytes(b"png")
    write_render_manifest(
        case_dir,
        BenchmarkRenderManifest(
            render_source="pptx_screenshot",
            render_valid=True,
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

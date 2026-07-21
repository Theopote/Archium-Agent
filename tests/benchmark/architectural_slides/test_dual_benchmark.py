"""Tests for dual Layout Geometry vs Rendered Visual benchmark layers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from archium.domain.visual.benchmark import (
    BenchmarkRenderManifest,
    HumanVisualReview,
    HumanVisualReviewSource,
    ReviewValidity,
)

from tests.benchmark.architectural_slides.artifacts import case_dir, materialized_benchmark_case_ids
from tests.benchmark.architectural_slides.render_manifest import (
    SCENE_JSON_NAME,
    SCENE_PREVIEW_NAME,
    editability_review_eligibility,
    layout_geometry_artifacts,
    rendered_visual_artifacts,
    visual_review_eligibility,
    write_render_manifest,
)


def _seed_rendered_case(case_dir: Path) -> None:
    (case_dir / SCENE_PREVIEW_NAME).write_bytes(b"png")
    (case_dir / SCENE_JSON_NAME).write_text("{}", encoding="utf-8")
    (case_dir / "output.pptx").write_bytes(b"pptx")
    (case_dir / "pptx_render.png").write_bytes(b"png")
    write_render_manifest(
        case_dir,
        BenchmarkRenderManifest(
            render_source="pptx_screenshot",
            render_valid=True,
            scene_hash="abc123",
            asset_count=1,
            real_asset_count=1,
            placeholder_asset_count=0,
            rendered_at=datetime.now(UTC),
            renderer="png_renderer+pptxgenjs",
        ),
    )


def test_layout_geometry_artifacts_are_separate_from_rendered_visual(tmp_path: Path) -> None:
    case = tmp_path / "case_demo"
    case.mkdir()
    (case / "wireframe.png").write_bytes(b"wire")
    (case / "layout_plan.json").write_text("{}", encoding="utf-8")
    (case / "validation_report.json").write_text("{}", encoding="utf-8")
    (case / "score_baseline.json").write_text("{}", encoding="utf-8")
    _seed_rendered_case(case)

    geometry = layout_geometry_artifacts(case)
    rendered = rendered_visual_artifacts(case)
    assert geometry["wireframe.png"] is True
    assert rendered["scene_preview.png"] is True
    assert rendered["render_manifest.json"] is True


def test_invalidated_manual_review_cannot_count_for_delivery() -> None:
    case_id = "case_001_site_plan"
    path = case_dir(case_id) / "human_review.json"
    if not path.is_file():
        return
    review = HumanVisualReview.model_validate_json(path.read_text(encoding="utf-8"))
    if review.source != HumanVisualReviewSource.INVALIDATED:
        return
    assert not review.accepted_for_delivery
    assert review.validity == ReviewValidity.INVALID_RENDER_ARTIFACT


PILOT_FRESH_SCREENSHOT_CASES = (
    "case_001_site_plan",
    "case_002_site_photos",
    "case_006_project_hero",
)


@pytest.mark.parametrize("case_id", list(PILOT_FRESH_SCREENSHOT_CASES))
def test_pilot_fresh_screenshots_unlock_formal_visual_review(case_id: str) -> None:
    """Pilot trio regenerated via PowerPoint — formal visual scoring may proceed."""
    directory = case_dir(case_id)
    eligible, manifest, blockers = visual_review_eligibility(directory)
    assert manifest is not None
    assert manifest.render_valid is True, blockers
    assert manifest.pptx_screenshot_generated is True
    assert manifest.pptx_screenshot_reused is False
    assert eligible is True, blockers
    edit_ok, edit_blockers = editability_review_eligibility(directory)
    assert edit_ok is True, edit_blockers


@pytest.mark.parametrize("case_id", ["case_003_case_comparison", "case_010_construction_phases"])
def test_reused_screenshots_still_block_non_pilot_cases(case_id: str) -> None:
    """Non-regenerated goldens remain blocked until fresh PPTX screenshots exist."""
    directory = case_dir(case_id)
    eligible, manifest, blockers = visual_review_eligibility(directory)
    assert manifest is not None
    assert manifest.render_valid is True, blockers
    if manifest.pptx_screenshot_generated:
        pytest.skip(f"{case_id} already has a fresh screenshot")
    assert manifest.pptx_screenshot_reused is True
    assert eligible is False, "reused screenshot must not unlock formal visual review"
    assert any("pptx_screenshot_generated" in item for item in blockers)
    edit_ok, edit_blockers = editability_review_eligibility(directory)
    assert edit_ok is True, edit_blockers


def test_all_materialized_cases_have_render_manifest() -> None:
    missing = []
    for case_id in materialized_benchmark_case_ids():
        if not (case_dir(case_id) / "render_manifest.json").is_file():
            missing.append(case_id)
    assert missing == []

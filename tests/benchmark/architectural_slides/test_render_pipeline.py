"""Tests for Rendered Visual Benchmark PPTX/render pipeline."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from archium.domain.slide import SlideSpec
from archium.domain.visual import (
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
    default_presentation_design_system,
)
from archium.domain.visual.enums import LayoutContentType
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import (
    PptxLayoutPlanAdapter,
)
from tests.benchmark.architectural_slides.render_pipeline import (
    build_slide_content_bundle,
    render_benchmark_visual_artifacts,
)


def test_build_slide_content_bundle_maps_assets(tmp_path: Path) -> None:
    asset_id = str(uuid4())
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / f"{asset_id}.png").write_bytes(b"png")
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="drawing_only",
        page_width=10,
        page_height=5.625,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        reading_order=["hero"],
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                content_ref=asset_id,
                x=1,
                y=1,
                width=8,
                height=4,
            )
        ],
    )
    slide = SlideSpec(
        presentation_id=uuid4(),
        title="Demo",
        message="Message",
        chapter_id="ch1",
        order=3,
        speaker_notes="notes",
    )
    build = build_slide_content_bundle(plan, assets_dir, slide)
    assert build.resolved_asset_count == 1
    assert build.missing_content_refs == ()
    assert build.bundle.page_number == 3
    assert build.bundle.speaker_notes == "notes"
    assert asset_id in build.bundle.asset_paths


def test_pptx_adapter_receives_resolved_asset_paths(tmp_path: Path) -> None:
    asset_id = str(uuid4())
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    asset_file = assets_dir / f"{asset_id}.png"
    asset_file.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\x0d\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    design = default_presentation_design_system()
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="drawing_only",
        page_width=10,
        page_height=5.625,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        reading_order=["hero"],
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                content_ref=asset_id,
                x=1,
                y=1,
                width=8,
                height=4,
            )
        ],
    )
    slide = SlideSpec(
        presentation_id=uuid4(),
        title="Demo",
        message="Msg",
        chapter_id="ch1",
        order=1,
    )
    build = build_slide_content_bundle(plan, assets_dir, slide)
    instruction = PptxLayoutPlanAdapter().render_slide(plan, design, build.bundle)
    hero = next(item for item in instruction.elements if item["id"] == "hero")
    assert hero["path"] == str(asset_file.resolve())
    assert "asset_unresolved" not in hero


@pytest.mark.parametrize("case_id", ["case_001_site_plan", "case_002_site_photos"])
def test_render_benchmark_visual_artifacts_exports_pptx(case_id: str, tmp_path: Path) -> None:
    from tests.benchmark.architectural_slides.case_builders import build_benchmark_case
    from tests.benchmark.architectural_slides.fixtures import ensure_case_assets

    result = build_benchmark_case(case_id)
    case_dir = tmp_path / case_id
    case_dir.mkdir()
    ensure_case_assets(case_id, case_dir / "assets")
    manifest = render_benchmark_visual_artifacts(result, case_dir)
    assert (case_dir / "scene.json").is_file()
    assert (case_dir / "scene_preview.png").is_file()
    assert manifest.scene_hash
    pptx = case_dir / "output.pptx"
    if pptx.is_file():
        assert manifest.missing_assets == []
    else:
        pytest.skip("Node/PptxGenJS unavailable in this environment")
    if manifest.render_valid:
        assert manifest.renderer == "png_renderer"
        assert manifest.render_source in {"html", "pptx_screenshot"}

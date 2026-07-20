"""Integration tests for RenderScene HTML/PNG rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from archium.infrastructure.renderers.html_renderer import HtmlRenderer
from archium.infrastructure.renderers.png_renderer import PngRenderer
from tests.benchmark.architectural_slides.case_builders import build_benchmark_case
from tests.benchmark.architectural_slides.fixtures import ensure_case_assets
from tests.benchmark.architectural_slides.render_pipeline import compile_and_render_scene


@pytest.mark.parametrize(
    "case_id",
    ["case_001_site_plan", "case_002_site_photos", "case_006_project_hero"],
)
def test_scene_preview_is_not_wireframe(case_id: str, tmp_path: Path) -> None:
    result = build_benchmark_case(case_id)
    case_dir = tmp_path / case_id
    case_dir.mkdir()
    ensure_case_assets(case_id, case_dir / "assets")

    scene_render = compile_and_render_scene(result, case_dir)
    assert scene_render.scene_path.is_file()
    assert scene_render.scene_preview_path.is_file()
    assert scene_render.scene_hash
    assert scene_render.unresolved_nodes == ()

    html = HtmlRenderer().render(scene_render.scene)
    assert "院区" in html or result.slide.title in html
    assert "missing asset" not in html.lower()

    png_bytes = scene_render.scene_preview_path.read_bytes()
    assert png_bytes.startswith(b"\x89PNG")
    assert len(png_bytes) > 4000

    wireframe = case_dir / "wireframe.png"
    from tests.golden.visual.composition.artifacts import render_layout_preview_png

    render_layout_preview_png(result.plan, wireframe)
    assert png_bytes != wireframe.read_bytes()


def test_png_renderer_writes_real_image(tmp_path: Path) -> None:
    from tests.benchmark.architectural_slides.render_pipeline import build_slide_content_bundle

    result = build_benchmark_case("case_006_project_hero")
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    ensure_case_assets("case_006_project_hero", case_dir / "assets")
    build = build_slide_content_bundle(result.plan, case_dir / "assets", result.slide)
    from archium.application.visual.render_scene_compiler import RenderSceneCompiler

    scene = RenderSceneCompiler().compile(
        slide=result.slide,
        layout_plan=result.plan,
        design_system=result.design_system,
        content_bundle=build.bundle,
        visual_intent=result.intent,
    )
    out = case_dir / "preview.png"
    PngRenderer().render(scene, out)
    assert out.stat().st_size > 3000

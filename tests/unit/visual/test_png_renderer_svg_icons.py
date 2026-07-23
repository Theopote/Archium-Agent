from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.visual.architectural_icon_registry import (
    load_default_architectural_icon_registry,
)
from archium.domain.visual.render_scene import BackgroundStyle, ImageNode, RenderScene
from archium.infrastructure.renderers.png_renderer import PngRenderer
from PIL import Image


def test_png_renderer_rasterizes_svg_icon_with_theme_stroke(tmp_path: Path) -> None:
    registry = load_default_architectural_icon_registry()
    icon = registry.get_by_name("pedestrian_flow")
    assert icon is not None
    svg_path = registry.resolve_svg_path(icon)
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=2.0,
        page_height=2.0,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="icon",
                semantic_role="icon",
                x=0.5,
                y=0.5,
                width=1.0,
                height=1.0,
                storage_uri=str(svg_path),
                asset_path=str(svg_path),
                fit_mode="contain",
                icon_stroke_color="#E63946",
                icon_stroke_token="accent",
            )
        ],
    )
    out = tmp_path / "icon_recolored.png"
    PngRenderer().render(scene, out)

    assert out.is_file()
    with Image.open(out) as image:
        pixels = list(image.convert("RGB").getdata())
    red_pixels = sum(1 for r, g, b in pixels if r > 180 and g < 100 and b < 100)
    dark_pixels = sum(1 for r, g, b in pixels if r < 80 and g < 80 and b < 80)
    assert red_pixels > 10
    assert dark_pixels == 0


def test_png_renderer_rasterizes_svg_icon(tmp_path: Path) -> None:
    registry = load_default_architectural_icon_registry()
    icon = registry.get_by_name("pedestrian_flow")
    assert icon is not None
    svg_path = registry.resolve_svg_path(icon)
    assert svg_path.is_file(), f"fixture SVG missing: {svg_path}"
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=2.0,
        page_height=2.0,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="icon",
                semantic_role="icon",
                x=0.5,
                y=0.5,
                width=1.0,
                height=1.0,
                storage_uri=str(svg_path),
                asset_path=str(svg_path),
                fit_mode="contain",
            )
        ],
    )
    out = tmp_path / "icon_preview.png"
    PngRenderer().render(scene, out)

    assert out.is_file()
    with Image.open(out) as image:
        pixels = list(image.convert("RGB").getdata())
    # Real icon strokes are dark (#1a1a1a). The previous placeholder used only
    # light gray strokes (~210), so dark pixels prove real SVG rasterization.
    dark_pixels = sum(1 for r, g, b in pixels if r < 80 and g < 80 and b < 80)
    assert dark_pixels > 20


def test_png_renderer_cover_fit_mode_rasterizes_svg_icon(tmp_path: Path) -> None:
    registry = load_default_architectural_icon_registry()
    icon = registry.get_by_name("pedestrian_flow")
    assert icon is not None
    svg_path = registry.resolve_svg_path(icon)
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=2.0,
        page_height=2.0,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="icon",
                semantic_role="icon",
                x=0.0,
                y=0.0,
                width=2.0,
                height=2.0,
                storage_uri=str(svg_path),
                asset_path=str(svg_path),
                fit_mode="cover",
            )
        ],
    )
    out = tmp_path / "cover_icon.png"
    PngRenderer().render(scene, out)
    assert out.is_file()
    with Image.open(out) as image:
        pixels = list(image.convert("RGB").getdata())
    dark_pixels = sum(1 for r, g, b in pixels if r < 80 and g < 80 and b < 80)
    assert dark_pixels > 20


def test_png_renderer_resolve_existing_asset_path() -> None:
    registry = load_default_architectural_icon_registry()
    icon = registry.get_by_name("pedestrian_flow")
    assert icon is not None
    svg_path = registry.resolve_svg_path(icon)
    assert PngRenderer._resolve_existing_asset_path(str(svg_path)) == svg_path
    assert PngRenderer._resolve_existing_asset_path("missing/icon.svg") is None


def test_png_renderer_load_image_asset_falls_back_to_simple_parser(
    monkeypatch,
) -> None:
    registry = load_default_architectural_icon_registry()
    icon = registry.get_by_name("pedestrian_flow")
    assert icon is not None
    svg_path = registry.resolve_svg_path(icon)
    renderer = PngRenderer()

    def _fail_cairosvg(*_args, **_kwargs):
        raise OSError("CairoSVG unavailable")

    monkeypatch.setattr(renderer, "_load_svg_via_cairosvg", _fail_cairosvg)
    asset = renderer._load_image_asset(svg_path, target_w=96, target_h=96)
    assert asset.size[0] > 0
    assert asset.size[1] > 0
    dark_pixels = sum(
        1 for r, g, b, a in asset.convert("RGBA").getdata() if a > 0 and r < 80 and g < 80 and b < 80
    )
    assert dark_pixels > 20


def test_png_renderer_draws_svg_placeholder_when_rasterization_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry = load_default_architectural_icon_registry()
    icon = registry.get_by_name("pedestrian_flow")
    assert icon is not None
    svg_path = registry.resolve_svg_path(icon)
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=2.0,
        page_height=2.0,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="icon",
                semantic_role="icon",
                x=0.5,
                y=0.5,
                width=1.0,
                height=1.0,
                storage_uri=str(svg_path),
                asset_path=str(svg_path),
                fit_mode="contain",
            )
        ],
    )
    out = tmp_path / "placeholder.png"
    renderer = PngRenderer()

    def _fail_load(*_args, **_kwargs):
        raise OSError("svg load failed")

    monkeypatch.setattr(renderer, "_load_image_asset", _fail_load)
    renderer.render(scene, out)
    with Image.open(out) as image:
        pixels = list(image.convert("RGB").getdata())
    dark_pixels = sum(1 for r, g, b in pixels if r < 80 and g < 80 and b < 80)
    light_pixels = sum(1 for r, g, b in pixels if r > 200 and g > 200 and b > 200)
    assert dark_pixels == 0
    assert light_pixels > 20

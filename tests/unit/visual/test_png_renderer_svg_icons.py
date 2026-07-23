from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.visual.architectural_icon_registry import (
    load_default_architectural_icon_registry,
)
from archium.domain.visual.render_scene import BackgroundStyle, ImageNode, RenderScene
from archium.infrastructure.renderers.png_renderer import PngRenderer
from PIL import Image


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

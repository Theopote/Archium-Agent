"""PNG stroke_width must use points (pptxgen parity), not layout inches."""

from __future__ import annotations

from pathlib import Path

from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, ShapeNode
from archium.infrastructure.renderers.png_renderer import PngRenderer
from PIL import Image


def test_png_shape_stroke_width_is_points_not_inches(tmp_path: Path) -> None:
    scene = RenderScene(
        slide_id=__import__("uuid").uuid4(),
        page_width=10.0,
        page_height=5.625,
        background=BackgroundStyle(color="#F2F4F6"),
        nodes=[
            ShapeNode(
                id="panel",
                x=1.0,
                y=1.0,
                width=3.0,
                height=2.5,
                fill_color="#FFFFFF",
                stroke_color="#2C5F7C",
                stroke_width=1.4,  # points — must not flood the panel
                z_index=0,
            )
        ],
    )
    out = tmp_path / "stroke.png"
    PngRenderer(dpi=96).render(scene, out)
    image = Image.open(out).convert("RGB")
    # Sample panel interior; must remain white, not accent stroke flood-fill.
    center = image.getpixel((int(2.5 * 96), int(2.25 * 96)))
    assert center[0] > 240 and center[1] > 240 and center[2] > 240

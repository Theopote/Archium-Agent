"""PNG renderer must resolve storage:// URIs to project files."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.domain.visual.render_scene import BackgroundStyle, ImageNode, RenderScene
from archium.infrastructure.renderers.png_renderer import PngRenderer
from PIL import Image


def test_png_renderer_resolves_storage_uri(tmp_path: Path, monkeypatch) -> None:
    project_id = uuid4()
    projects_root = tmp_path / "projects"
    asset_dir = projects_root / str(project_id) / "sources"
    asset_dir.mkdir(parents=True)
    asset_file = asset_dir / "concept.png"
    Image.new("RGB", (120, 80), color=(40, 95, 124)).save(asset_file)

    from archium.config.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "project_storage_path", projects_root)

    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10.0,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="concept",
                x=1.0,
                y=1.0,
                width=4.0,
                height=3.0,
                storage_uri=f"storage://projects/{project_id}/sources/concept.png",
                fit_mode="contain",
            )
        ],
    )
    out = tmp_path / "out.png"
    PngRenderer(dpi=48).render(scene, out)
    image = Image.open(out).convert("RGB")
    # Sample inside the image box — should pick up the teal asset, not white page bg.
    sample = image.getpixel((int(3.0 * 48), int(2.5 * 48)))
    assert sample[2] > sample[0]  # blue-ish from teal concept PNG

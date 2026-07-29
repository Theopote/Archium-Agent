"""PPTX export path contracts: portable URIs must not reach Node."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    ImageNode,
    RenderScene,
)
from archium.infrastructure.renderers.pptx_renderer import scene_pptx_unavailable_reason
from archium.infrastructure.renderers.scene_pptx_adapter import (
    RenderScenePptxAdapter,
    _filesystem_export_path,
)


def test_filesystem_export_path_rejects_portable_uris() -> None:
    assert _filesystem_export_path("storage://proj/a.png") is None
    assert _filesystem_export_path("project://x/y.png", "C:/tmp/a.png") == "C:/tmp/a.png"
    assert _filesystem_export_path(None, "benchmark://case/assets/a.png") is None
    assert (
        _filesystem_export_path("/tmp/resolved.png", "storage://ignored")
        == "/tmp/resolved.png"
    )


def test_adapter_marks_portable_uri_as_unresolved() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="photo",
                x=1,
                y=1,
                width=4,
                height=3,
                storage_uri="storage://demo/photo.png",
                asset_path="storage://demo/photo.png",
            ),
            DrawingNode(
                id="plan",
                x=5,
                y=1,
                width=4,
                height=3,
                storage_uri="project://demo/plan.png",
                asset_path="project://demo/plan.png",
                drawing_type="site_plan",
            ),
        ],
    )
    adapter = RenderScenePptxAdapter()
    instruction = adapter.render_slide(scene)
    image = next(el for el in instruction.elements if el["id"] == "photo")
    drawing = next(el for el in instruction.elements if el["id"] == "plan")
    assert image.get("asset_unresolved") is True
    assert "path" not in image
    assert drawing.get("asset_unresolved") is True
    assert "path" not in drawing


def test_adapter_prefers_resolved_path_over_portable_uri() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="photo",
                x=1,
                y=1,
                width=4,
                height=3,
                storage_uri="storage://demo/photo.png",
                asset_path="storage://demo/photo.png",
                resolved_path="C:/data/photo.png",
            )
        ],
    )
    instruction = RenderScenePptxAdapter().render_slide(scene)
    image = next(el for el in instruction.elements if el["id"] == "photo")
    assert image["path"] == "C:/data/photo.png"
    assert "asset_unresolved" not in image


def test_resolve_for_export_preserves_existing_resolved_path(tmp_path) -> None:
    from archium.infrastructure.renderers.pptx_renderer import PptxRenderer
    from archium.infrastructure.storage.asset_path_resolver import (
        AssetPathResolveContext,
        AssetPathResolver,
    )

    asset = tmp_path / "hero.png"
    asset.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            DrawingNode(
                id="plan",
                x=1,
                y=1,
                width=4,
                height=3,
                storage_uri="benchmark://case_x/assets/hero.png",
                asset_path="benchmark://case_x/assets/hero.png",
                resolved_path=str(asset),
                drawing_type="site_plan",
                asset_unresolved=False,
            )
        ],
    )
    # Empty project-only context used to clear resolved_path before the fix.
    wiped = AssetPathResolver().resolve_scene(scene, AssetPathResolveContext())
    drawing = next(n for n in wiped.nodes if n.id == "plan")
    assert drawing.resolved_path == str(asset)
    assert drawing.asset_unresolved is False

    export_resolved = PptxRenderer()._resolve_for_export(scene, project_id=None)
    exported = next(n for n in export_resolved.nodes if n.id == "plan")
    assert exported.resolved_path == str(asset)
    assert exported.asset_unresolved is False


def test_resolve_for_export_infers_benchmark_root_for_portable_uris() -> None:
    from archium.infrastructure.renderers.pptx_renderer import PptxRenderer

    case_id = "case_001_site_plan"
    asset_name = "c0010001-0001-4001-8001-000000000001.png"
    asset_path = (
        Path(__file__).resolve().parents[2]
        / "benchmark"
        / "architectural_slides"
        / case_id
        / "assets"
        / asset_name
    )
    if not asset_path.is_file():
        import pytest

        pytest.skip("pilot benchmark asset missing")

    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            DrawingNode(
                id="plan",
                x=1,
                y=1,
                width=4,
                height=3,
                storage_uri=f"benchmark://{case_id}/assets/{asset_name}",
                asset_path=f"benchmark://{case_id}/assets/{asset_name}",
                drawing_type="site_plan",
            )
        ],
    )
    export_resolved = PptxRenderer()._resolve_for_export(scene, project_id=None)
    exported = next(n for n in export_resolved.nodes if n.id == "plan")
    assert exported.resolved_path == str(asset_path.resolve())
    assert exported.asset_unresolved is False

    instruction = RenderScenePptxAdapter().render_slide(export_resolved)
    plan = next(el for el in instruction.elements if el["id"] == "plan")
    assert plan["path"] == str(asset_path.resolve())


def test_scene_pptx_unavailable_reason_is_string_or_none() -> None:
    reason = scene_pptx_unavailable_reason()
    assert reason is None or isinstance(reason, str)

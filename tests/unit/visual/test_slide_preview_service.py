"""Unit tests for slide preview resolution."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.visual.slide_preview_service import (
    SlidePreviewService,
    map_preview_pngs_by_order,
)
from archium.config.settings import Settings
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan


def _sample_plan() -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="centered",
        page_width=10,
        page_height=5.625,
        hero_element_id="hero",
        reading_order=["title", "hero"],
        whitespace_ratio=0.35,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=0.8,
                y=0.4,
                width=8.4,
                height=0.7,
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=1.0,
                y=1.4,
                width=8.0,
                height=3.8,
            ),
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )


def test_map_preview_pngs_by_order_sorts_slide_files() -> None:
    mapping = map_preview_pngs_by_order(
        [
            "output/visual-composition/run/slide_previews/slide_02.png",
            "output/visual-composition/run/slide_previews/slide_01.png",
        ]
    )
    assert mapping[0].endswith("slide_01.png")
    assert mapping[1].endswith("slide_02.png")


def test_resolve_previews_prefers_scene_over_screenshot(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, output_path=tmp_path)
    screenshot = tmp_path / "slide_01.png"
    screenshot.write_bytes(b"png")
    scene = tmp_path / "scene_preview.png"
    scene.write_bytes(b"scene")
    service = SlidePreviewService(settings)
    resolutions = service.resolve_previews(
        presentation_id=uuid4(),
        layout_plans=[_sample_plan()],
        render_paths=[str(screenshot)],
        scene_preview_by_index={0: str(scene)},
    )
    assert resolutions[0].kind == "scene"
    assert resolutions[0].path == str(scene)


def test_resolve_previews_prefers_screenshot_over_wireframe(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, output_path=tmp_path)
    screenshot = tmp_path / "slide_01.png"
    screenshot.write_bytes(b"png")
    service = SlidePreviewService(settings)
    resolutions = service.resolve_previews(
        presentation_id=uuid4(),
        layout_plans=[_sample_plan()],
        render_paths=[str(screenshot)],
    )
    assert resolutions[0].kind == "screenshot"
    assert resolutions[0].path == str(screenshot)


def test_resolve_previews_generates_wireframe_when_no_screenshot(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, output_path=tmp_path)
    presentation_id = uuid4()
    plan = _sample_plan()
    service = SlidePreviewService(settings)
    resolutions = service.resolve_previews(
        presentation_id=presentation_id,
        layout_plans=[plan],
    )
    assert resolutions[0].kind == "wireframe"
    assert resolutions[0].path is not None
    assert Path(resolutions[0].path).is_file()

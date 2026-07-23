"""Unit tests for RenderScene → PPTX adapter."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual import (
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
    default_presentation_design_system,
)
from archium.domain.visual.enums import LayoutContentType
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle
from archium.infrastructure.renderers.scene_pptx_adapter import RenderScenePptxAdapter


def test_adapter_maps_text_and_drawing_nodes(tmp_path: Path) -> None:
    asset_id = str(uuid4())
    asset_file = tmp_path / f"{asset_id}.png"
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
        layout_variant="drawing_with_metrics",
        page_width=10,
        page_height=5.625,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        reading_order=["title", "hero"],
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="测试标题",
                x=0.7,
                y=0.45,
                width=8.6,
                height=0.657,
                style_token="title",
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                content_ref=asset_id,
                x=0.7,
                y=1.2,
                width=6,
                height=3,
            ),
        ],
    )
    slide = SlideSpec(
        presentation_id=uuid4(),
        title="测试标题",
        message="说明",
        chapter_id="site_plan",
        order=1,
        visual_requirements=[
            VisualRequirement(type=VisualType.SITE_PLAN, description="总平面")
        ],
    )
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
        content_bundle=SlideContentBundle(asset_paths={asset_id: str(asset_file.resolve())}),
    )
    instruction = RenderScenePptxAdapter().render_slide(scene, design_system_id=design.id)
    payload = instruction.to_dict()
    title = next(item for item in payload["elements"] if item["id"] == "title")
    hero = next(item for item in payload["elements"] if item["id"] == "hero")
    assert title["text"] == "测试标题"
    assert title["font_size"] == design.typography.title.font_size
    assert title["font_family_cjk"] == "Microsoft YaHei"
    assert hero["content_type"] == "drawing"
    assert hero["fit_mode"] == "contain"
    assert hero["path"] == str(asset_file.resolve())


def test_render_deck_uses_render_scene_schema() -> None:
    design = default_presentation_design_system()
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="split",
        page_width=10,
        page_height=5.625,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        reading_order=["title"],
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="封面",
                x=0.7,
                y=0.45,
                width=8,
                height=0.6,
                style_token="title",
            )
        ],
    )
    slide = SlideSpec(
        presentation_id=uuid4(),
        title="封面",
        message="封面说明",
        chapter_id="hero",
        order=1,
    )
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
    )
    deck = RenderScenePptxAdapter().render_deck(title="Deck", scenes=[(scene, None)])
    assert deck["schema"] == "archium.render_scene.v1"
    assert deck["slides"][0]["elements"][0]["text"] == "封面"


def test_adapter_materializes_recolored_icon_svg(tmp_path: Path) -> None:
    from archium.application.visual.architectural_icon_registry import (
        load_default_architectural_icon_registry,
    )
    from archium.domain.visual.render_scene import BackgroundStyle, ImageNode, RenderScene

    registry = load_default_architectural_icon_registry()
    icon = registry.get_by_name("pedestrian_flow")
    assert icon is not None
    svg_path = registry.resolve_svg_path(icon)
    design = default_presentation_design_system().model_copy(deep=True)
    design.colors.accent = "#E63946"
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        design_system_id=design.id,
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="icon",
                semantic_role="icon",
                x=1.0,
                y=1.0,
                width=0.2,
                height=0.2,
                storage_uri=str(svg_path),
                asset_path=str(svg_path),
                fit_mode="contain",
                icon_stroke_color="#E63946",
                icon_stroke_token="accent",
            )
        ],
    )
    instruction = RenderScenePptxAdapter().render_slide(scene, design_system_id=design.id)
    payload = instruction.to_dict()
    icon_el = next(item for item in payload["elements"] if item["id"] == "icon")
    assert icon_el["icon_stroke_color"] == "E63946"
    recolored = Path(str(icon_el["path"]))
    assert recolored.is_file()
    assert recolored != svg_path
    assert 'stroke="#E63946"' in recolored.read_text(encoding="utf-8")

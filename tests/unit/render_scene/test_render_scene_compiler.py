"""Unit tests for LayoutPlan → RenderScene compiler."""

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
from archium.domain.visual.render_scene import DrawingNode, TextNode
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle


def test_compiler_populates_title_and_drawing(tmp_path: Path) -> None:
    asset_id = str(uuid4())
    asset_file = tmp_path / f"{asset_id}.png"
    asset_file.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\x0d\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    design = default_presentation_design_system()
    slide_id = uuid4()
    plan = LayoutPlan(
        slide_id=slide_id,
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
                text_content="院区总平面与改造范围",
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
        title="院区总平面与改造范围",
        message="总平面明确分区",
        chapter_id="site_plan",
        order=1,
        visual_requirements=[
            VisualRequirement(type=VisualType.SITE_PLAN, description="总平面")
        ],
    )
    bundle = SlideContentBundle(asset_paths={asset_id: str(asset_file.resolve())})
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
        content_bundle=bundle,
    )

    title = scene.node_by_id("title")
    hero = scene.node_by_id("hero")
    assert isinstance(title, TextNode)
    assert title.text == "院区总平面与改造范围"
    assert title.font_size == design.typography.title.font_size
    assert isinstance(hero, DrawingNode)
    assert hero.fit_mode == "contain"
    assert hero.asset_path == str(asset_file.resolve()) or hero.storage_uri == str(
        asset_file.resolve()
    )
    assert hero.drawing_type == "site_plan"
    assert scene.background.color == design.colors.resolve("background")
    assert scene.warnings == []


def test_compiler_warns_on_missing_asset() -> None:
    design = default_presentation_design_system()
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="split",
        page_width=10,
        page_height=5.625,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        reading_order=["hero"],
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                content_ref="missing-id",
                x=1,
                y=1,
                width=8,
                height=4,
            )
        ],
    )
    slide = SlideSpec(
        presentation_id=uuid4(),
        title="Hero",
        message="Msg",
        chapter_id="hero",
        order=1,
    )
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
        content_bundle=SlideContentBundle(),
    )
    hero = scene.node_by_id("hero")
    assert hero is not None
    assert getattr(hero, "asset_unresolved", False) is True
    assert any("UNRESOLVED_ASSET" in warning for warning in scene.warnings)

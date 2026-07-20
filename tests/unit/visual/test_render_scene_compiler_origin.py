"""Compiler provenance / semantic_role pass-through tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.visual.asset_reference import infer_asset_origin
from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual import (
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
    default_presentation_design_system,
)
from archium.domain.visual.enums import LayoutContentType
from archium.domain.visual.render_scene import DrawingNode, ImageNode
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle


def _tiny_png(path: Path) -> None:
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\x0d\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_infer_asset_origin_from_tags() -> None:
    asset = Asset(
        project_id=uuid4(),
        filename="x.png",
        path="x.png",
        asset_type=AssetType.PHOTO,
        tags=["ai_generated"],
    )
    assert infer_asset_origin(asset) == "ai_generated"


def test_compiler_propagates_asset_origin_and_semantic_role(tmp_path: Path) -> None:
    asset_id = str(uuid4())
    asset_file = tmp_path / f"{asset_id}.png"
    _tiny_png(asset_file)
    design = default_presentation_design_system()
    slide_id = uuid4()
    plan = LayoutPlan(
        slide_id=slide_id,
        layout_family=LayoutFamily.HERO,
        layout_variant="split",
        page_width=10,
        page_height=5.625,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                content_ref=asset_id,
                x=1,
                y=1,
                width=4,
                height=3,
            )
        ],
    )
    slide = SlideSpec(
        presentation_id=uuid4(),
        title="项目照片",
        message="现状",
        chapter_id="photos",
        order=1,
    )
    bundle = SlideContentBundle(
        asset_paths={asset_id: str(asset_file.resolve())},
        asset_origins={asset_id: "ai_generated"},
    )
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
        content_bundle=bundle,
    )
    hero = scene.node_by_id("hero")
    assert isinstance(hero, ImageNode)
    assert hero.asset_origin == "ai_generated"
    assert hero.semantic_role == "project_photo"


def test_compiler_drawing_cover_warning_and_site_plan_role(tmp_path: Path) -> None:
    from archium.domain.visual.enums import ImageFit

    asset_id = str(uuid4())
    asset_file = tmp_path / f"{asset_id}.png"
    _tiny_png(asset_file)
    design = default_presentation_design_system()
    slide_id = uuid4()
    plan = LayoutPlan(
        slide_id=slide_id,
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="drawing",
        page_width=10,
        page_height=5.625,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                content_ref=asset_id,
                fit_mode=ImageFit.COVER,
                x=0.5,
                y=0.5,
                width=6,
                height=4,
            )
        ],
    )
    slide = SlideSpec(
        presentation_id=uuid4(),
        title="总平面",
        message="分区",
        chapter_id="site",
        order=1,
        visual_requirements=[VisualRequirement(type=VisualType.SITE_PLAN, description="总平面")],
    )
    bundle = SlideContentBundle(asset_paths={asset_id: str(asset_file.resolve())})
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
        content_bundle=bundle,
    )
    hero = scene.node_by_id("hero")
    assert isinstance(hero, DrawingNode)
    assert hero.fit_mode == "contain"
    assert hero.semantic_role == "site_plan"
    assert any(w.startswith("DRAWING_COVER_MODE_FORBIDDEN") for w in scene.warnings)

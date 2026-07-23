"""Unit tests for ExportPolicyService fidelity assessment and enforcement."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.export_policy_service import (
    ExportPolicyService,
    export_policy_from_preset,
)
from archium.domain.export_fidelity import ExportFidelityLevel, ExportPolicy
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    FontAsset,
    ImageNode,
    RenderScene,
    ShapeNode,
    TextNode,
)
from archium.exceptions import WorkflowError


def _scene(*nodes: object, **background: object) -> RenderScene:
    bg = BackgroundStyle(color="#FFFFFF")
    if background:
        bg = BackgroundStyle(**background)  # type: ignore[arg-type]
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=1920,
        page_height=1080,
        background=bg,
        nodes=list(nodes),  # type: ignore[arg-type]
    )


def test_fully_editable_text_and_shapes() -> None:
    scene = _scene(
        TextNode(
            id="t1",
            x=100,
            y=100,
            width=400,
            height=80,
            z_index=1,
            text="标题",
            font_family="Arial",
            font_size=24,
            color="#000",
            line_height=1.2,
        ),
        ShapeNode(
            id="s1",
            x=10,
            y=10,
            width=100,
            height=50,
            z_index=0,
            shape_kind="rectangle",
            fill_color="#EEE",
        ),
    )
    result = ExportPolicyService().assess_scene_fidelity(scene)
    assert result.fidelity_level == ExportFidelityLevel.FULLY_EDITABLE
    assert result.native_text_count == 1
    assert result.native_shape_count == 1


def test_hybrid_editable_text_with_bitmap() -> None:
    scene = _scene(
        TextNode(
            id="t1",
            x=10,
            y=10,
            width=200,
            height=40,
            z_index=2,
            text="混合页",
            font_family="Arial",
            font_size=18,
            color="#000",
            line_height=1.2,
        ),
        ImageNode(
            id="img",
            x=400,
            y=100,
            width=600,
            height=400,
            z_index=1,
            storage_uri="asset://photo.jpg",
        ),
    )
    result = ExportPolicyService().assess_scene_fidelity(scene)
    assert result.fidelity_level == ExportFidelityLevel.HYBRID_EDITABLE
    assert result.bitmap_asset_count == 1


def test_text_editable_with_background_image() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=1920,
        page_height=1080,
        background=BackgroundStyle(color="#FFFFFF", image_asset_path="asset://bg.png"),
        nodes=[
            TextNode(
                id="t1",
                x=10,
                y=10,
                width=200,
                height=40,
                z_index=1,
                text="text over background",
                font_family="Arial",
                font_size=18,
                color="#000",
                line_height=1.2,
            ),
        ],
    )
    result = ExportPolicyService().assess_scene_fidelity(scene)
    assert result.fidelity_level == ExportFidelityLevel.TEXT_EDITABLE


def test_raster_fallback_single_full_page_image() -> None:
    scene = _scene(
        ImageNode(
            id="bg",
            x=0,
            y=0,
            width=1920,
            height=1080,
            z_index=0,
            storage_uri="asset://page.png",
        ),
    )
    result = ExportPolicyService().assess_scene_fidelity(scene)
    assert result.fidelity_level == ExportFidelityLevel.RASTER_FALLBACK


def test_empty_scene_fails() -> None:
    result = ExportPolicyService().assess_scene_fidelity(_scene())
    assert result.fidelity_level == ExportFidelityLevel.FAILED


def test_unresolved_assets_and_font_substitutions() -> None:
    scene = _scene(
        ImageNode(
            id="img",
            x=100,
            y=100,
            width=400,
            height=300,
            z_index=1,
            storage_uri="asset://missing.png",
            asset_unresolved=True,
        ),
        DrawingNode.model_construct(
            id="plan",
            node_type="drawing",
            x=100,
            y=100,
            width=800,
            height=600,
            z_index=2,
            storage_uri="asset://plan.png",
            fit_mode="contain",
            asset_unresolved=True,
        ),
    )
    scene.font_assets = [
        FontAsset(
            family="CustomFont",
            resolved_family="Arial",
        )
    ]
    result = ExportPolicyService().assess_scene_fidelity(scene)
    assert "img" in result.unresolved_assets
    assert "plan" in result.unresolved_assets
    assert any("CustomFont" in item for item in result.font_substitutions)


def test_drawing_cover_mode_is_blocker() -> None:
    scene = _scene(
        DrawingNode.model_construct(
            id="plan",
            node_type="drawing",
            x=100,
            y=100,
            width=800,
            height=600,
            z_index=1,
            storage_uri="asset://plan.png",
            fit_mode="cover",
        ),
    )
    result = ExportPolicyService().assess_scene_fidelity(scene)
    assert any("drawing:plan" in blocker for blocker in result.blockers)


def test_build_deck_manifest_records_fallback_reason() -> None:
    service = ExportPolicyService()
    native = service.assess_scene_fidelity(
        _scene(
            TextNode(
                id="t1",
                x=10,
                y=10,
                width=200,
                height=40,
                z_index=1,
                text="native",
                font_family="Arial",
                font_size=18,
                color="#000",
                line_height=1.2,
            ),
        )
    )
    raster = service.assess_scene_fidelity(
        _scene(
            ImageNode(
                id="full",
                x=0,
                y=0,
                width=1920,
                height=1080,
                z_index=0,
                storage_uri="asset://full.png",
            ),
        )
    )
    manifest = service.build_deck_manifest(
        presentation_id=uuid4(),
        export_format="PPTX",
        policy=ExportPolicy(allow_raster_fallback=True),
        slide_results=[native, raster],
        revision_id=uuid4(),
        file_uri="file://deck.pptx",
        file_hash="abc123",
        qa_status="passed",
    )
    assert manifest.fallback_used is True
    assert manifest.fallback_reason is not None
    assert "raster_fallback" in manifest.fallback_reason


def test_enforce_blocks_unresolved_assets() -> None:
    service = ExportPolicyService()
    slide = service.assess_scene_fidelity(
        _scene(
            ImageNode(
                id="img",
                x=0,
                y=0,
                width=400,
                height=300,
                z_index=0,
                storage_uri="asset://missing.png",
                asset_unresolved=True,
            ),
        )
    )
    manifest = service.build_deck_manifest(
        presentation_id=uuid4(),
        export_format="PPTX",
        policy=ExportPolicy(fail_on_unresolved_assets=True),
        slide_results=[slide],
    )
    with pytest.raises(WorkflowError, match="未解析素材"):
        service.enforce_export_policy(manifest)


def test_enforce_blocks_font_substitutions() -> None:
    service = ExportPolicyService()
    scene = _scene(
        TextNode(
            id="t1",
            x=10,
            y=10,
            width=200,
            height=40,
            z_index=1,
            text="text",
            font_family="Arial",
            font_size=18,
            color="#000",
            line_height=1.2,
        ),
    )
    scene.font_assets = [
        FontAsset(family="Brand", resolved_family="Arial"),
    ]
    slide = service.assess_scene_fidelity(scene)
    manifest = service.build_deck_manifest(
        presentation_id=uuid4(),
        export_format="PPTX",
        policy=ExportPolicy(fail_on_missing_fonts=True),
        slide_results=[slide],
    )
    with pytest.raises(WorkflowError, match="字体替代"):
        service.enforce_export_policy(manifest)


def test_enforce_blocks_drawing_crop_when_policy_requires() -> None:
    service = ExportPolicyService()
    slide = service.assess_scene_fidelity(
        _scene(
            DrawingNode.model_construct(
                id="plan",
                node_type="drawing",
                x=100,
                y=100,
                width=800,
                height=600,
                z_index=1,
                storage_uri="asset://plan.png",
                fit_mode="cover",
            ),
        )
    )
    manifest = service.build_deck_manifest(
        presentation_id=uuid4(),
        export_format="PPTX",
        policy=ExportPolicy(fail_on_drawing_crop=True),
        slide_results=[slide],
    )
    with pytest.raises(WorkflowError, match="图纸保护"):
        service.enforce_export_policy(manifest)


def test_enforce_blocks_slide_level_fallback_when_disabled() -> None:
    service = ExportPolicyService()
    hybrid = service.assess_scene_fidelity(
        _scene(
            TextNode(
                id="t1",
                x=10,
                y=10,
                width=200,
                height=40,
                z_index=2,
                text="混合",
                font_family="Arial",
                font_size=18,
                color="#000",
                line_height=1.2,
            ),
            ImageNode(
                id="img",
                x=400,
                y=100,
                width=600,
                height=400,
                z_index=1,
                storage_uri="asset://photo.jpg",
            ),
        )
    )
    manifest = service.build_deck_manifest(
        presentation_id=uuid4(),
        export_format="PPTX",
        policy=ExportPolicy(
            required_fidelity=ExportFidelityLevel.FULLY_EDITABLE,
            allow_slide_level_fallback=False,
        ),
        slide_results=[hybrid],
    )
    with pytest.raises(WorkflowError, match="不满足要求"):
        service.enforce_export_policy(manifest)


def test_strict_policy_blocks_raster_export() -> None:
    service = ExportPolicyService()
    slide = service.assess_scene_fidelity(
        _scene(
            ImageNode(
                id="full",
                x=0,
                y=0,
                width=1920,
                height=1080,
                z_index=0,
                storage_uri="asset://full.png",
            ),
        )
    )
    manifest = service.build_deck_manifest(
        presentation_id=uuid4(),
        export_format="PPTX",
        policy=ExportPolicy(),
        slide_results=[slide],
    )
    with pytest.raises(WorkflowError, match="raster_fallback"):
        service.enforce_export_policy(manifest)


def test_enforce_blocks_disallowed_fidelity_level() -> None:
    service = ExportPolicyService()
    hybrid = service.assess_scene_fidelity(
        _scene(
            TextNode(
                id="t1",
                x=10,
                y=10,
                width=200,
                height=40,
                z_index=2,
                text="hybrid",
                font_family="Arial",
                font_size=18,
                color="#000",
                line_height=1.2,
            ),
            ImageNode(
                id="img",
                x=400,
                y=100,
                width=600,
                height=400,
                z_index=1,
                storage_uri="asset://photo.jpg",
            ),
        )
    )
    manifest = service.build_deck_manifest(
        presentation_id=uuid4(),
        export_format="PPTX",
        policy=ExportPolicy(
            required_fidelity=ExportFidelityLevel.FULLY_EDITABLE,
            allow_hybrid_editable=False,
            allow_slide_level_fallback=True,
        ),
        slide_results=[hybrid],
    )
    with pytest.raises(WorkflowError, match="超出当前导出策略"):
        service.enforce_export_policy(manifest)


def test_full_page_image_warning_when_no_text() -> None:
    scene = _scene(
        ImageNode(
            id="full",
            x=0,
            y=0,
            width=1920,
            height=1080,
            z_index=0,
            storage_uri="asset://full.png",
        ),
    )
    result = ExportPolicyService().assess_scene_fidelity(scene)
    assert any("full_page_image" in warning for warning in result.warnings)


def test_allow_hybrid_per_slide_fallback_succeeds() -> None:
    service = ExportPolicyService()
    native = service.assess_scene_fidelity(
        _scene(
            TextNode(
                id="t1",
                x=10,
                y=10,
                width=200,
                height=40,
                z_index=1,
                text="native",
                font_family="Arial",
                font_size=18,
                color="#000",
                line_height=1.2,
            ),
        )
    )
    hybrid = service.assess_scene_fidelity(
        _scene(
            TextNode(
                id="t2",
                x=10,
                y=10,
                width=200,
                height=40,
                z_index=2,
                text="hybrid",
                font_family="Arial",
                font_size=18,
                color="#000",
                line_height=1.2,
            ),
            ImageNode(
                id="img",
                x=400,
                y=100,
                width=600,
                height=400,
                z_index=1,
                storage_uri="asset://photo.jpg",
            ),
        )
    )
    policy = ExportPolicy(allow_slide_level_fallback=True, allow_hybrid_editable=True)
    manifest = service.build_deck_manifest(
        presentation_id=uuid4(),
        export_format="PPTX",
        policy=policy,
        slide_results=[native, hybrid],
    )
    service.enforce_export_policy(manifest, policy=policy)
    assert manifest.fallback_used is True


def test_export_policy_from_preset_maps_known_keys() -> None:
    strict = export_policy_from_preset("strict_native")
    hybrid = export_policy_from_preset("allow_hybrid")
    text_bg = export_policy_from_preset("allow_text_bg")
    raster = export_policy_from_preset("allow_raster")
    unknown = export_policy_from_preset("unknown_preset")

    assert strict.allow_raster_fallback is False
    assert hybrid.allow_hybrid_editable is True
    assert text_bg.allow_text_editable_background is True
    assert raster.allow_raster_fallback is True
    assert unknown.required_fidelity == strict.required_fidelity

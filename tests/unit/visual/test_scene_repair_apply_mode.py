"""Tests for Scene Repair safe-auto vs proposal-required apply modes."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.scene_repair_service import SceneRepairService
from archium.domain.slide_semantic_qa import SlideSemanticFinding
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    RenderScene,
    TextNode,
)
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.domain.visual.scene_repair import SceneRepairApplyMode


def test_safe_auto_only_fixes_cover_mode_without_text_changes() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            DrawingNode.model_construct(
                id="plan",
                x=1.0,
                y=1.0,
                width=4.0,
                height=3.0,
                z_index=1,
                storage_uri="project://drawing.png",
                asset_path="project://drawing.png",
                fit_mode="cover",
            ),
            TextNode(
                id="body",
                x=0.5,
                y=4.0,
                width=2.0,
                height=0.4,
                z_index=2,
                text="这是一段非常长的说明文字" * 20,
                font_family="Arial",
                font_size=12,
                color="#000000",
                line_height=1.2,
                overflow_policy="error",
            ),
        ],
    )
    original_text = scene.nodes[1].text  # type: ignore[union-attr]
    findings = [
        SlideSemanticFinding(
            check_code=SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN,
            slide_order=0,
            slide_id=scene.slide_id,
            severity="medium",
            title="cover forbidden",
            description="cover forbidden",
            evidence_refs=["plan"],
        ),
        SlideSemanticFinding(
            check_code=SceneSemanticCheckCode.TEXT_OVERFLOW,
            slide_order=0,
            slide_id=scene.slide_id,
            severity="medium",
            title="overflow",
            description="overflow",
            evidence_refs=["body"],
        ),
    ]

    result = SceneRepairService().repair_scene(
        scene,
        findings,
        apply_mode=SceneRepairApplyMode.SAFE_AUTO_ONLY,
    )

    drawing = result.scene.node_by_id("plan")
    body = result.scene.node_by_id("body")
    assert isinstance(drawing, DrawingNode)
    assert isinstance(body, TextNode)
    assert drawing.fit_mode == "contain"
    assert body.text == original_text
    assert result.applied_count == 1
    assert result.actions[0].action_type == "set_fit_mode_contain"


def test_all_repairable_applies_text_overflow_fixes() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="body",
                x=0.5,
                y=1.0,
                width=2.0,
                height=0.4,
                z_index=1,
                text="这是一段非常长的说明文字" * 20,
                font_family="Arial",
                font_size=12,
                color="#000000",
                line_height=1.2,
                overflow_policy="error",
            )
        ],
    )
    finding = SlideSemanticFinding(
        check_code=SceneSemanticCheckCode.TEXT_OVERFLOW,
        slide_order=0,
        slide_id=scene.slide_id,
        severity="medium",
        title="overflow",
        description="overflow",
        evidence_refs=["body"],
    )

    result = SceneRepairService().repair_scene(
        scene,
        [finding],
        apply_mode=SceneRepairApplyMode.ALL_REPAIRABLE,
    )

    body = result.scene.node_by_id("body")
    assert isinstance(body, TextNode)
    assert len(body.text) < len("这是一段非常长的说明文字" * 20)
    assert result.applied_count >= 1


def test_repair_deck_reports_deferred_overflow_without_auto_shortening() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="body",
                x=0.5,
                y=1.0,
                width=2.0,
                height=0.4,
                z_index=1,
                text="这是一段非常长的说明文字" * 20,
                font_family="Arial",
                font_size=12,
                color="#000000",
                line_height=1.2,
                overflow_policy="error",
            )
        ],
    )
    original_len = len(scene.nodes[0].text)  # type: ignore[union-attr]
    presentation_id = uuid4()

    batch = SceneRepairService().repair_deck(
        presentation_id,
        [scene],
        max_rounds=1,
        slide_orders={scene.slide_id: 0},
        apply_mode=SceneRepairApplyMode.SAFE_AUTO_ONLY,
    )

    body = batch.scenes[0].node_by_id("body")
    assert isinstance(body, TextNode)
    assert len(body.text) == original_len
    assert batch.deferred_findings
    assert batch.deferred_findings[0].check_code == SceneSemanticCheckCode.TEXT_OVERFLOW


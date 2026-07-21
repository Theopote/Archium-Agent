"""Unit tests for per-page pipeline status derivation."""

from __future__ import annotations

from uuid import uuid4

from archium.application.page_status_board_service import _actions_for_phase, _derive_phase, action_label
from archium.domain.enums import SlideDeliveryStatus, VisualType
from archium.domain.page_pipeline_status import (
    PAGE_ACTION_LABELS,
    PagePipelinePhase,
    PageStatusAction,
)
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual.enums import LayoutFamily, LayoutValidationStatus


def _slide(**kwargs) -> SlideSpec:
    defaults = {
        "presentation_id": uuid4(),
        "chapter_id": "ch1",
        "order": 0,
        "title": "入口",
        "message": "人车混行是主因",
    }
    defaults.update(kwargs)
    return SlideSpec(**defaults)


def test_ready_slide_without_layout_is_content_ready() -> None:
    phase, label, _detail, severity = _derive_phase(
        _slide(delivery_status=SlideDeliveryStatus.READY),
        workflow_step=None,
        layout_family=None,
        layout_validation=None,
        has_scene=False,
        free_composition=False,
    )
    assert phase == PagePipelinePhase.CONTENT_READY
    assert "内容" in label
    assert severity == "success"


def test_template_matched_and_complete() -> None:
    phase, label, detail, _ = _derive_phase(
        _slide(delivery_status=SlideDeliveryStatus.READY),
        workflow_step=None,
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_validation=LayoutValidationStatus.VALID,
        has_scene=True,
        free_composition=False,
    )
    assert phase == PagePipelinePhase.COMPLETE
    assert label == "完成"
    assert "模板匹配" in detail


def test_template_matched_before_scene() -> None:
    phase, label, _, _ = _derive_phase(
        _slide(delivery_status=SlideDeliveryStatus.READY, layout_plan_id=uuid4()),
        workflow_step=None,
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_validation=LayoutValidationStatus.VALID,
        has_scene=False,
        free_composition=False,
    )
    assert phase == PagePipelinePhase.COMPILING_SCENE
    assert "RenderScene" in label


def test_free_composition_label() -> None:
    phase, label, _, _ = _derive_phase(
        _slide(delivery_status=SlideDeliveryStatus.READY),
        workflow_step=None,
        layout_family=None,
        layout_validation=None,
        has_scene=True,
        free_composition=True,
    )
    assert phase == PagePipelinePhase.FREE_COMPOSITION
    assert "自由构图" in label


def test_asset_missing_metric_label() -> None:
    slide = _slide(
        delivery_status=SlideDeliveryStatus.ASSET_MISSING,
        visual_requirements=[
            VisualRequirement(
                type=VisualType.CHART,
                description="早高峰车流",
                required=True,
            )
        ],
    )
    phase, label, _, severity = _derive_phase(
        slide,
        workflow_step=None,
        layout_family=None,
        layout_validation=None,
        has_scene=False,
        free_composition=False,
    )
    assert phase == PagePipelinePhase.ASSET_MISSING
    assert label == "缺少指标来源"
    assert severity == "warn"


def test_binding_photos_during_match_assets() -> None:
    slide = _slide(
        delivery_status=SlideDeliveryStatus.READY,
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="入口照片",
                required=True,
            )
        ],
    )
    phase, label, _, _ = _derive_phase(
        slide,
        workflow_step="match_assets",
        layout_family=None,
        layout_validation=None,
        has_scene=False,
        free_composition=False,
    )
    assert phase == PagePipelinePhase.BINDING_ASSETS
    assert "现场照片" in label


def test_compiling_scene_when_layout_without_scene() -> None:
    slide = _slide(
        delivery_status=SlideDeliveryStatus.READY,
        layout_plan_id=uuid4(),
    )
    phase, label, _, _ = _derive_phase(
        slide,
        workflow_step="visual_render",
        layout_family=LayoutFamily.HERO,
        layout_validation=LayoutValidationStatus.VALID,
        has_scene=False,
        free_composition=False,
    )
    assert phase == PagePipelinePhase.COMPILING_SCENE
    assert "RenderScene" in label


def test_drawing_qa_failed() -> None:
    slide = _slide(
        delivery_status=SlideDeliveryStatus.READY,
        visual_requirements=[
            VisualRequirement(type=VisualType.SITE_PLAN, description="总平面", required=True)
        ],
    )
    phase, label, _, severity = _derive_phase(
        slide,
        workflow_step=None,
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_validation=LayoutValidationStatus.INVALID,
        has_scene=True,
        free_composition=False,
    )
    assert phase == PagePipelinePhase.DRAWING_QA_FAILED
    assert "Drawing QA" in label
    assert severity == "error"


def test_skipped_page() -> None:
    phase, label, _, _ = _derive_phase(
        _slide(delivery_status=SlideDeliveryStatus.SKIPPED),
        workflow_step=None,
        layout_family=None,
        layout_validation=None,
        has_scene=False,
        free_composition=False,
    )
    assert phase == PagePipelinePhase.SKIPPED
    assert "跳过" in label


def test_display_line_format() -> None:
    from archium.domain.page_pipeline_status import PagePipelineStatus

    row = PagePipelineStatus(
        order=2,
        phase=PagePipelinePhase.BINDING_ASSETS,
        status_label="正在绑定现场照片",
    )
    assert row.display_line() == "第 3 页：正在绑定现场照片"


def test_required_recovery_actions_cover_user_intents() -> None:
    """User-facing recovery actions must include the five core operations."""
    required = {
        PageStatusAction.RETRY,
        PageStatusAction.CHANGE_TEMPLATE,
        PageStatusAction.REBIND_ASSETS,
        PageStatusAction.OPEN_STUDIO,
        PageStatusAction.SKIP,
    }
    assert required.issubset(set(PAGE_ACTION_LABELS))
    assert action_label(PageStatusAction.RETRY) == "重试当前页"
    assert action_label(PageStatusAction.CHANGE_TEMPLATE) == "更换模板"
    assert action_label(PageStatusAction.REBIND_ASSETS) == "重新绑定素材"
    assert action_label(PageStatusAction.OPEN_STUDIO) == "打开 Studio"
    assert action_label(PageStatusAction.SKIP) == "跳过该页"

    asset_actions = set(_actions_for_phase(PagePipelinePhase.ASSET_MISSING))
    assert PageStatusAction.REBIND_ASSETS in asset_actions
    assert PageStatusAction.SKIP in asset_actions

    qa_actions = set(_actions_for_phase(PagePipelinePhase.DRAWING_QA_FAILED))
    assert PageStatusAction.OPEN_STUDIO in qa_actions
    assert PageStatusAction.CHANGE_TEMPLATE in qa_actions

    skipped_actions = set(_actions_for_phase(PagePipelinePhase.SKIPPED))
    assert PageStatusAction.UNSKIP in skipped_actions

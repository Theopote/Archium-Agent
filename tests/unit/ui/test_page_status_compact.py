"""Unit tests for compact page-status actions and badges."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.page_pipeline_status import (
    PagePipelinePhase,
    PagePipelineStatus,
    PageStatusAction,
)
from archium.ui.page_status_board_panel import (
    pick_primary_action,
    split_primary_and_more,
    status_badge,
    status_short_detail,
)


def test_primary_action_prefers_rebind_for_asset_missing() -> None:
    actions = [
        PageStatusAction.RETRY,
        PageStatusAction.REBIND_ASSETS,
        PageStatusAction.SKIP,
        PageStatusAction.OPEN_STUDIO,
        PageStatusAction.CHANGE_TEMPLATE,
    ]
    primary, more = split_primary_and_more(actions)
    assert primary == PageStatusAction.REBIND_ASSETS
    assert PageStatusAction.REBIND_ASSETS not in more
    assert len(more) == 4


def test_status_badge_symbols() -> None:
    complete = PagePipelineStatus(
        slide_id=uuid4(),
        order=0,
        title="封面",
        phase=PagePipelinePhase.COMPLETE,
        severity="success",
    )
    missing = PagePipelineStatus(
        slide_id=uuid4(),
        order=1,
        title="现状",
        phase=PagePipelinePhase.ASSET_MISSING,
        severity="warn",
        detail="缺少现场照片",
    )
    drawing = PagePipelineStatus(
        slide_id=uuid4(),
        order=2,
        title="总平面",
        phase=PagePipelinePhase.DRAWING_QA_FAILED,
        severity="error",
    )
    generating = PagePipelineStatus(
        slide_id=uuid4(),
        order=3,
        title="策略",
        phase=PagePipelinePhase.GENERATING,
        severity="info",
    )
    assert status_badge(complete) == "✓"
    assert status_badge(missing) == "⚠"
    assert status_badge(drawing) == "✕"
    assert status_badge(generating) == "⏳"
    assert "缺少" in status_short_detail(missing)


def test_pick_primary_action_empty() -> None:
    assert pick_primary_action([]) is None

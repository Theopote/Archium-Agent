"""Unit tests for sidebar / cockpit project progress helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from archium.ui.project_progress_card import (
    CockpitTaskSummary,
    ProjectProgressSnapshot,
    _format_relative_time,
    greeting_for_now,
)


def _snapshot(**overrides: object) -> ProjectProgressSnapshot:
    base = {
        "project_id": uuid4(),
        "project_name": "长安大学图书馆改造",
        "presentation_id": uuid4(),
        "presentation_title": "中期汇报",
        "presentation_type": "client_review",
        "document_count": 3,
        "slide_count": 24,
        "layout_ready_count": 21,
        "has_brief": True,
        "ready_for_export": False,
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return ProjectProgressSnapshot(**base)  # type: ignore[arg-type]


def test_progress_labels_match_user_facing_copy() -> None:
    snap = _snapshot()
    assert snap.materials_label == "已整理"
    assert snap.outline_label == "已确认"
    assert snap.generate_label == "21/24 页"
    assert snap.pending_count == 3
    assert snap.deliver_label == "未通过"
    assert snap.presentation_type_label == "甲方汇报"
    assert snap.current_stage_id == "generate"
    assert snap.completion_label == "21/24 页完成"


def test_progress_empty_project_labels() -> None:
    snap = _snapshot(
        presentation_id=None,
        presentation_title=None,
        presentation_type=None,
        document_count=0,
        slide_count=0,
        layout_ready_count=0,
        has_brief=False,
        ready_for_export=False,
    )
    assert snap.materials_label == "未上传"
    assert snap.outline_label == "未开始"
    assert snap.generate_label == "未开始"
    assert snap.pending_count == 0
    assert snap.deliver_label == "未开始"
    assert snap.current_stage_id == "materials"
    assert snap.presentation_type_label == "尚未创建汇报"


def test_progress_ready_for_export_label() -> None:
    snap = _snapshot(ready_for_export=True, layout_ready_count=24, slide_count=24)
    assert snap.deliver_label == "可交付"
    assert snap.pending_count == 0
    assert snap.current_stage_id == "deliver"


def test_format_relative_time_minutes() -> None:
    moment = datetime.now(UTC) - timedelta(minutes=10)
    assert _format_relative_time(moment) == "10 分钟前"


def test_greeting_is_non_empty() -> None:
    assert greeting_for_now() in {"早上好", "下午好", "晚上好"}


def test_cockpit_task_summary_has_tasks() -> None:
    empty = CockpitTaskSummary()
    assert not empty.has_tasks
    filled = CockpitTaskSummary(lines=("3 页缺少素材",))
    assert filled.has_tasks

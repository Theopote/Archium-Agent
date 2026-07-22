"""UI source tests for Studio visual version timeline."""

from __future__ import annotations

from pathlib import Path


def test_visual_version_timeline_has_restore_and_compare() -> None:
    source = Path("archium/ui/studio/visual_version_timeline.py").read_text(encoding="utf-8")
    assert "版本时间线" in source
    assert "恢复" in source
    assert "对比 A" in source
    assert "对比 B" in source
    assert "当前正式版本" in source
    assert "不会覆盖" in source or "不会覆盖或删除" in source


def test_history_panel_embeds_scene_timeline() -> None:
    source = Path("archium/ui/studio/history_panel.py").read_text(encoding="utf-8")
    assert "render_scene_version_timeline_panel" in source
    assert "版本时间线" in source


def test_restore_result_exposes_source_version() -> None:
    source = Path("archium/domain/scene_revision_summary.py").read_text(encoding="utf-8")
    assert "source_revision_id" in source
    assert "source_version" in source
    assert "is_current" in source

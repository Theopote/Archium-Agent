"""UI source tests for slide design brief review panel."""

from __future__ import annotations

from pathlib import Path


def test_design_brief_panel_has_approve_actions() -> None:
    source = Path("archium/ui/outline/design_brief_panel.py").read_text(encoding="utf-8")
    assert "批准本页" in source
    assert "批量批准" in source
    assert "重生成摘要" in source
    assert "视觉语法原型" in source
    assert "page_archetype" in source


def test_outline_page_has_design_brief_tab() -> None:
    source = Path("archium/ui/pages/flow/outline.py").read_text(encoding="utf-8")
    assert "页面设计摘要" in source
    assert "render_design_brief_panel" in source


def test_visual_workflow_gated_by_design_briefs() -> None:
    source = Path("archium/ui/visual_service.py").read_text(encoding="utf-8")
    assert "design_briefs_ready" in source

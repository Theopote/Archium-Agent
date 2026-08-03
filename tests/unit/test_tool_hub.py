"""Tool hub catalog honesty checks."""

from __future__ import annotations

from archium.ui.pages.tool_hub import tool_hub_entries


def test_tool_hub_exposes_existing_pages_and_honest_placeholders() -> None:
    entries = tool_hub_entries()
    available = {item.title: item for item in entries if item.available}
    upcoming = {item.title: item for item in entries if not item.available}

    assert available["页面复活"].page_key == "slide-recovery"
    assert available["模板库"].page_key == "template-library"
    assert "从 PDF 提取指标" in upcoming
    assert upcoming["从 PDF 提取指标"].page_key is None
    assert upcoming["从 PDF 提取指标"].via_hint

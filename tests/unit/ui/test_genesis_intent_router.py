"""Guards for genesis Intent Router entry UX."""

from __future__ import annotations

from pathlib import Path


def test_genesis_has_orientation_chooser_and_classifier() -> None:
    src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "project_genesis.py"
    )
    text = src.read_text(encoding="utf-8")
    assert "以想法为主" in text
    assert "以现有资料为主" in text
    assert "说不清，描述一下" in text
    assert "classify_entry_intent" in text
    assert "地点（可选）" in text
    assert "st.tabs(" not in text


def test_home_empty_state_mentions_orientation() -> None:
    src = Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "home.py"
    text = src.read_text(encoding="utf-8")
    assert "主路径" in text
    assert "开始项目（选主路径）" in text

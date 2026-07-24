"""Guards for genesis Knowledge State entry UX."""

from __future__ import annotations

from pathlib import Path


def test_genesis_uses_context_intelligence_not_mode_cards() -> None:
    src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "project_genesis.py"
    )
    text = src.read_text(encoding="utf-8")
    assert "描述你的建筑项目、问题或灵感" in text
    assert "开始理解项目" in text
    assert "assess_project_context" in text
    assert "建议下一步" in text
    assert "以想法为主" not in text
    assert "以现有资料为主" not in text
    assert "说不清，描述一下" not in text
    assert "st.tabs(" not in text


def test_home_empty_state_invites_idea_not_mode_choice() -> None:
    src = Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "home.py"
    text = src.read_text(encoding="utf-8")
    assert "告诉我你的想法" in text
    assert "知识状态" in text
    assert "开始项目（选主路径）" not in text

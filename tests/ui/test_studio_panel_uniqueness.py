"""Studio inspector / dock must not duplicate interactive repair panels."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / "archium" / "ui" / "pages" / "studio.py"


def _count_calls(tree: ast.AST, name: str) -> int:
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == name)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == name)
        )
    )


def test_scene_repair_and_human_review_appear_once_in_studio_module() -> None:
    source = STUDIO.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert _count_calls(tree, "render_deferred_scene_repair_panel") == 1
    assert _count_calls(tree, "render_human_review_panel") == 1


def test_info_menus_do_not_embed_full_repair_controls() -> None:
    source = STUDIO.read_text(encoding="utf-8")
    info_start = source.index("def _render_studio_info_menus")
    info_end = source.index("\ndef render(", info_start)
    info_block = source[info_start:info_end]
    assert "render_deferred_scene_repair_panel" not in info_block
    assert "render_human_review_panel" not in info_block
    assert "_render_deck_issue_list" in info_block


def test_inspector_is_lazy_not_st_tabs() -> None:
    source = STUDIO.read_text(encoding="utf-8")
    assert "st.tabs(" not in source
    assert "_select_inspector_tab" in source
    assert 'if active == "检查"' not in source  # check is the default fallthrough
    assert "render_deferred_scene_repair_panel" in source
    # Repair only after AI branch returns — not executed for every tab.
    assert 'if active == "AI":' in source

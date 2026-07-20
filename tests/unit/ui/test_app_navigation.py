"""Unit tests for shared Streamlit navigation page registry and product flow."""

from __future__ import annotations

import pytest
from archium.ui import app_navigation
from archium.ui.product_flow import (
    ADVANCED_SECTION,
    PRIMARY_SECTION,
    advanced_page_keys,
    get_stage,
    next_stage,
    previous_stage,
    primary_page_keys,
    primary_stage_ids,
    product_flow_chain,
    product_flow_home_steps,
)


def test_get_app_page_unknown_raises() -> None:
    app_navigation._PAGES.clear()
    with pytest.raises(KeyError, match="Unknown app page"):
        app_navigation.get_app_page("missing")


def test_product_flow_has_five_ordered_stages() -> None:
    assert primary_stage_ids() == (
        "materials",
        "outline",
        "generate",
        "edit",
        "deliver",
    )
    assert primary_page_keys() == primary_stage_ids()
    assert product_flow_chain() == "资料 → 大纲 → 生成 → 编辑 → 交付"
    assert len(product_flow_home_steps()) == 5
    assert get_stage("materials").title == "资料"
    assert previous_stage("materials") is None
    assert next_stage("deliver") is None
    assert next_stage("materials").id == "outline"
    assert previous_stage("deliver").id == "edit"


def test_build_app_pages_registers_primary_and_advanced_keys() -> None:
    sections = app_navigation.build_app_pages()
    assert PRIMARY_SECTION in sections
    assert ADVANCED_SECTION in sections
    primary = sections[PRIMARY_SECTION]
    # home + 5 stages
    assert len(primary) == 6
    for key in primary_page_keys():
        assert app_navigation.get_app_page(key) is not None
    for key in advanced_page_keys():
        assert app_navigation.get_app_page(key) is not None
    # Legacy aliases still resolve
    assert app_navigation.get_app_page("studio") is not None
    assert app_navigation.get_app_page("workspace") is not None
    assert app_navigation.get_app_page("home") is not None


def test_home_copy_is_five_stage_not_nine_step() -> None:
    from pathlib import Path

    home_src = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "home.py"
    )
    text = home_src.read_text(encoding="utf-8")
    assert "9 步" not in text
    assert "5 步" in text
    assert "product_flow_chain" in text

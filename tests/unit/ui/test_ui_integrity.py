"""UI integrity guards for Architecture V1 / Interaction Hardening."""

from __future__ import annotations

from pathlib import Path

from archium.ui import app_navigation, icons
from archium.ui.product_flow import (
    LEGACY_STUDIO_PAGE_KEY,
    MAKE_SECTION,
    PRODUCT_STUDIO_PAGE_KEY,
    PROJECT_SECTION,
    RESOURCE_SECTION,
    SYSTEM_SECTION,
    hidden_page_keys,
    primary_page_keys,
    primary_stages,
    product_studio_page_key,
)


def test_primary_stage_icons_are_material_not_emoji() -> None:
    for stage in primary_stages():
        assert stage.icon.startswith(":material/"), stage.id
        assert not any(ord(ch) > 0x1F300 for ch in stage.icon)


def test_sidebar_four_sections_exclude_legacy_tools() -> None:
    sections = app_navigation.build_app_pages()
    assert set(sections) == {
        PROJECT_SECTION,
        MAKE_SECTION,
        RESOURCE_SECTION,
        SYSTEM_SECTION,
    }
    visible = {id(page) for pages in sections.values() for page in pages}
    for key in hidden_page_keys():
        assert id(app_navigation.get_app_page(key)) not in visible
    assert LEGACY_STUDIO_PAGE_KEY not in primary_page_keys()
    assert product_studio_page_key() == PRODUCT_STUDIO_PAGE_KEY
    assert id(app_navigation.get_app_page(PRODUCT_STUDIO_PAGE_KEY)) in {
        id(page) for page in sections[MAKE_SECTION]
    }


def test_flow_pages_use_compact_project_context() -> None:
    root = Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "flow"
    for name in ("materials.py", "outline.py", "generate.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "render_flow_project_context" in text, name


def test_bootstrap_avoids_inter_default_stack() -> None:
    css = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "bootstrap.py"
    ).read_text(encoding="utf-8")
    assert "Inter" not in css
    assert "Source Sans 3" in css
    assert "--archium-ink" in css
    assert "status-chip" in css


def test_nav_icons_module_covers_primary_pages() -> None:
    assert icons.HOME.startswith(":material/")
    assert icons.STUDIO.startswith(":material/")
    assert icons.MATERIALS.startswith(":material/")

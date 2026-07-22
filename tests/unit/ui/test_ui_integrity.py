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


def test_bootstrap_stays_init_styles_brand_only() -> None:
    bootstrap = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "bootstrap.py"
    ).read_text(encoding="utf-8")
    assert "module_status_pipeline" not in bootstrap
    assert "module_status_marp_export" not in bootstrap
    assert "module_status_legacy_ppt" not in bootstrap
    assert "def render_module_status" not in bootstrap
    assert "def render_system_diagnostics" not in bootstrap
    assert "def init_app" in bootstrap
    assert "def inject_styles" in bootstrap
    assert "def render_branding" in bootstrap
    diagnostics = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "system_diagnostics.py"
    ).read_text(encoding="utf-8")
    assert "def module_status_pipeline" in diagnostics
    assert "def render_system_diagnostics" in diagnostics


def test_bootstrap_avoids_inter_default_stack() -> None:
    css = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "bootstrap.py"
    ).read_text(encoding="utf-8")
    assert "Inter" not in css
    assert "fonts.googleapis.com" not in css
    assert "@import url" not in css
    assert "--archium-font-sans" in css
    assert "--archium-ink" in css
    assert "status-chip" in css
    assert "archium-page-header" in css
    assert "archium-stepper" in css
    assert "archium-callout" in css
    assert "archium-empty" in css


def test_ui_chrome_component_layer_exists() -> None:
    from archium.ui.components import (
        render_empty_state,
        render_inspector_section,
        render_page_header,
        render_panel,
        render_primary_action,
        render_status_badge,
        render_toolbar,
        render_warning_callout,
    )

    chrome = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "components"
        / "chrome.py"
    ).read_text(encoding="utf-8")
    for name in (
        "render_page_header",
        "render_panel",
        "render_status_badge",
        "render_empty_state",
        "render_primary_action",
        "render_warning_callout",
        "render_inspector_section",
        "render_toolbar",
    ):
        assert f"def {name}" in chrome
    assert callable(render_page_header)
    assert callable(render_panel)
    assert callable(render_status_badge)
    assert callable(render_empty_state)
    assert callable(render_primary_action)
    assert callable(render_warning_callout)
    assert callable(render_inspector_section)
    assert callable(render_toolbar)


def test_flow_header_uses_chrome_primitives() -> None:
    flow_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "flow"
        / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "render_page_header" in flow_src
    assert "render_stepper" in flow_src
    assert "render_warning_callout" in flow_src


def test_nav_icons_module_covers_primary_pages() -> None:
    assert icons.HOME.startswith(":material/")
    assert icons.STUDIO.startswith(":material/")
    assert icons.MATERIALS.startswith(":material/")

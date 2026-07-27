"""Guard modern Streamlit APIs on the user-facing product path."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIMARY_PAGES = (
    "archium/ui/pages/flow/materials.py",
    "archium/ui/pages/flow/outline.py",
    "archium/ui/pages/flow/generate.py",
    "archium/ui/pages/flow/edit.py",
    "archium/ui/pages/flow/deliver.py",
    "archium/ui/pages/studio.py",
)


def test_primary_pages_do_not_use_deprecated_container_width() -> None:
    offenders = [
        relative
        for relative in PRIMARY_PAGES
        if "use_container_width=" in (ROOT / relative).read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_home_only_keeps_internal_compatibility_argument() -> None:
    text = (ROOT / "archium/ui/pages/home.py").read_text(encoding="utf-8")
    occurrences = [
        line.strip()
        for line in text.splitlines()
        if "use_container_width=" in line
    ]
    assert occurrences == [
        'if render_primary_action("重试", key="home_retry_load", use_container_width=False):'
    ]

"""Home cockpit must distinguish EMPTY vs LOAD_FAILED."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT / "archium" / "ui" / "pages" / "home.py"


def test_home_source_has_load_failed_path() -> None:
    text = HOME.read_text(encoding="utf-8")
    assert "_render_load_failed" in text
    assert "项目列表暂时无法加载" in text
    assert "_render_empty_state" in text
    # Must not swallow exceptions into an empty snapshot list.
    assert "except Exception:\n        snapshots = []" not in text
    assert "except Exception as exc:" in text


def test_home_load_failure_does_not_call_empty_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """When snapshot loading raises, UI must show failure — not first-project empty."""
    calls: dict[str, int] = {"empty": 0, "failed": 0}

    def fake_empty() -> None:
        calls["empty"] += 1

    def fake_failed(exc: Exception) -> None:
        calls["failed"] += 1
        assert isinstance(exc, RuntimeError)

    import archium.ui.pages.home as home

    monkeypatch.setattr(home, "_render_empty_state", fake_empty)
    monkeypatch.setattr(home, "_render_load_failed", fake_failed)

    with patch(
        "archium.ui.pages.home.list_recent_project_snapshots",
        side_effect=RuntimeError("db down"),
    ):
        home.render()

    assert calls["failed"] == 1
    assert calls["empty"] == 0


def test_home_other_projects_continue_into_work() -> None:
    text = HOME.read_text(encoding="utf-8")
    block = text.split("def _render_other_projects")[1].split("def render")[0]
    assert "_select_and_continue(snapshot)" in block
    assert "继续工作" in block
    assert "st.rerun()" not in block

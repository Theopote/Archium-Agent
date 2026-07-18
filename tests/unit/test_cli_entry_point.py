"""Tests for v0.2 default CLI entry point."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_cli_app_path_points_to_root_app() -> None:
    from archium.cli import _APP_PATH

    assert _APP_PATH.name == "app.py"
    assert _APP_PATH.is_file()
    assert _APP_PATH.resolve().parent == Path(__file__).resolve().parents[2]


def test_cli_main_exits_when_streamlit_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "streamlit":
            raise ImportError("streamlit not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from archium.cli import main

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1

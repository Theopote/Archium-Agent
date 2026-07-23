"""Tests for unified application bootstrap."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from archium.config.settings import _PROJECT_ROOT, Settings


def test_project_root_points_at_repo() -> None:
    from archium.bootstrap import ENV_PATH, PROJECT_ROOT

    assert (PROJECT_ROOT / "app.py").is_file()
    assert (PROJECT_ROOT / "archium" / "bootstrap.py").is_file()
    assert ENV_PATH == PROJECT_ROOT / ".env"


def test_load_environment_ignores_cwd_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from archium import bootstrap as boot

    root_env = tmp_path / "repo" / ".env"
    root_env.parent.mkdir(parents=True)
    root_env.write_text("ARCHIUM_BOOTSTRAP_PROBE=from_root\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".env").write_text("ARCHIUM_BOOTSTRAP_PROBE=from_cwd\n", encoding="utf-8")

    monkeypatch.setattr(boot, "ENV_PATH", root_env)
    monkeypatch.setattr(boot, "PROJECT_ROOT", root_env.parent)
    monkeypatch.delenv("ARCHIUM_BOOTSTRAP_PROBE", raising=False)
    monkeypatch.chdir(elsewhere)

    loaded = boot.load_environment()
    assert loaded == root_env
    assert os.environ.get("ARCHIUM_BOOTSTRAP_PROBE") == "from_root"


def test_app_py_is_thin_create_application_wrapper() -> None:
    app_src = Path(__file__).resolve().parents[2] / "app.py"
    text = app_src.read_text(encoding="utf-8")
    assert "create_application" in text
    assert "st.set_page_config" not in text
    assert "init_database" not in text
    assert "load_dotenv" not in text
    assert "build_app_pages" not in text


def test_create_application_owns_streamlit_shell() -> None:
    boot_src = Path(__file__).resolve().parents[2] / "archium" / "bootstrap.py"
    text = boot_src.read_text(encoding="utf-8")
    assert "def create_application" in text
    assert "def bootstrap_runtime" in text
    assert "st.set_page_config" in text
    assert "build_app_pages" in text
    assert "render_project_progress_card" in text
    assert "load_dotenv(ENV_PATH)" in text


def test_settings_env_file_is_project_root_absolute() -> None:
    env_file = Settings.model_config.get("env_file")
    assert env_file == str(_PROJECT_ROOT / ".env")

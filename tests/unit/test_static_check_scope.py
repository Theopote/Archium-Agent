"""Guard: static-check config scope matches what CI actually runs."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _ROOT / "pyproject.toml"
_CI = _ROOT / ".github" / "workflows" / "ci.yml"


def test_ruff_and_mypy_exclude_frozen_legacy() -> None:
    payload = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    ruff_src = list(payload["tool"]["ruff"]["src"])
    mypy_packages = list(payload["tool"]["mypy"]["packages"])
    assert ruff_src == ["archium", "tests"]
    assert mypy_packages == ["archium"]
    assert "legacy" not in ruff_src
    assert "legacy" not in mypy_packages
    assert "config.py" not in ruff_src


def test_mypy_does_not_globally_ignore_missing_imports() -> None:
    payload = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    assert payload["tool"]["mypy"].get("ignore_missing_imports") is False
    override_list = payload["tool"]["mypy"].get("overrides", [])
    assert override_list, "expected third-party ignore_missing_imports overrides"
    assert any(
        item.get("ignore_missing_imports") is True
        and any(
            str(mod).startswith("streamlit") or str(mod) == "streamlit"
            for mod in item.get("module", [])
        )
        for item in override_list
    )


def test_ci_ruff_mypy_commands_match_config_scope() -> None:
    text = _CI.read_text(encoding="utf-8")
    assert re.search(r"^\s+run:\s+ruff check archium tests\s*$", text, re.M)
    assert re.search(r"^\s+run:\s+mypy archium\b", text, re.M)
    assert "ruff check archium legacy" not in text
    assert "mypy archium legacy" not in text
    assert "compatibility" in text
    assert "quality-full" in text
    assert "--materialize-ci-samples" in text
    assert "--write-goldens" not in text

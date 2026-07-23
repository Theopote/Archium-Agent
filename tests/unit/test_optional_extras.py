"""Guardrails for pyproject optional-dependency extras."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _ROOT / "pyproject.toml"

# Product runtime extras that ``full`` must cover. ``dev`` is intentionally excluded.
_RUNTIME_EXTRAS = ("ui", "documents", "workflow", "vector", "llm", "postgres")


def _load_optional_dependencies() -> dict[str, list[str]]:
    payload = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    return dict(payload["project"]["optional-dependencies"])


def _requirement_identity(raw: str) -> str:
    """Normalize a requirement to name[+extras]+specifier for set comparison."""
    req = Requirement(raw)
    extras = f"[{','.join(sorted(req.extras))}]" if req.extras else ""
    return f"{req.name.lower()}{extras}{req.specifier}"


def test_full_extra_contains_all_runtime_extras() -> None:
    extras = _load_optional_dependencies()
    missing_extras = [name for name in _RUNTIME_EXTRAS if name not in extras]
    assert not missing_extras, f"pyproject missing runtime extras: {missing_extras}"
    assert "full" in extras

    runtime: set[str] = set()
    for name in _RUNTIME_EXTRAS:
        runtime.update(_requirement_identity(item) for item in extras[name])
    full = {_requirement_identity(item) for item in extras["full"]}
    missing = sorted(runtime - full)
    assert not missing, (
        "full extra is missing runtime requirements "
        "(add them to [project.optional-dependencies].full):\n  - "
        + "\n  - ".join(missing)
    )


def test_documentation_url_uses_default_branch_master() -> None:
    text = _PYPROJECT.read_text(encoding="utf-8")
    assert "tree/master/docs" in text
    assert "tree/main/docs" not in text

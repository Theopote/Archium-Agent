"""DOM-018: enums package split guards."""

from __future__ import annotations

from pathlib import Path

import archium.domain.enums as enums_pkg
from archium.domain.enums import (
    ApprovalStatus,
    RevisionSource,
    SlideChangeSource,
    WorkflowStep,
)

_ENUMS_DIR = Path(enums_pkg.__file__).resolve().parent
_MAX_MODULE_LINES = 250


def test_enums_is_package_not_monolith() -> None:
    assert _ENUMS_DIR.is_dir()
    assert not (_ENUMS_DIR.parent / "enums.py").exists()
    assert ( _ENUMS_DIR / "__init__.py").is_file()


def test_enum_submodules_under_line_budget() -> None:
    oversized: list[str] = []
    for path in sorted(_ENUMS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > _MAX_MODULE_LINES:
            oversized.append(f"{path.name}:{lines}")
    assert oversized == [], f"enum modules exceed {_MAX_MODULE_LINES} lines: {oversized}"


def test_compat_reexports_and_aliases() -> None:
    assert SlideChangeSource is RevisionSource
    assert WorkflowStep.EXPORT.value == "export"
    assert ApprovalStatus.CHANGES_PENDING.value == "changes_pending"
    assert "WorkflowStep" in enums_pkg.__all__

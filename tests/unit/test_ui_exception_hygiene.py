"""Hygiene: UI must not silently swallow unexpected exceptions."""

from __future__ import annotations

import re
from pathlib import Path

# Bare ``except Exception: pass`` hides failures from operators and logs.
_SILENT_PASS = re.compile(
    r"except Exception(?: as \w+)?:\r?\n[ \t]+pass\b",
    re.MULTILINE,
)

# Catch-alls that surface errors without logging unknowns.
_FORMAT_WITHOUT_REPORT = re.compile(
    r"except Exception as \w+:\r?\n(?:[ \t]+.+\r?\n){0,2}[ \t]+st\.(?:error|warning|caption)\(\s*format_user_error\(",
    re.MULTILINE,
)


def test_ui_has_no_silent_exception_pass() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "ui"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _SILENT_PASS.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(f"{path.relative_to(root.parent.parent)}:{line_no}")
    # session_actor may run outside ScriptRunContext; allow only that module.
    hits = [
        h
        for h in hits
        if Path(h.split(":")[0]).as_posix() != "archium/ui/session_actor.py"
    ]
    assert hits == [], "silent except Exception: pass in UI:\n" + "\n".join(hits)


def test_ui_exception_handlers_prefer_report_user_error() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "ui"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _FORMAT_WITHOUT_REPORT.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(f"{path.relative_to(root.parent.parent)}:{line_no}")
    assert hits == [], (
        "except Exception should use report_user_error (logs unknowns), "
        "not format_user_error:\n" + "\n".join(hits)
    )

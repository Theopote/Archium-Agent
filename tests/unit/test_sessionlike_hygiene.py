"""SessionLike hygiene — migration must not break APP-003 transaction ownership."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Closing the caller's Session from a SessionLike service would abort the outer UoW.
_SESSION_CLOSE = re.compile(
    r"(?<![\w.])(?:session|_session|self\._session)\.close\s*\("
)

# Nested get_session inside SessionLike helpers opens a second transaction;
# allow only known short-lived read/composition roots (not service ctors).
_NESTED_GET_SESSION_ALLOWLIST = frozenset(
    {
        "archium/application/llm_settings_resolver.py",
        "archium/application/evidence_readiness_service.py",
        "archium/application/unit_of_work.py",
    }
)


def test_sessionlike_services_do_not_close_caller_session() -> None:
    """SessionLike services must not close the outer unit-of-work Session."""
    root = _REPO_ROOT / "archium" / "application"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        # Only modules that accept SessionLike are in scope for this regression.
        if "SessionLike" not in text and "session_of" not in text:
            continue
        for match in _SESSION_CLOSE.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            line = text.splitlines()[line_no - 1].strip()
            # Exclude unrelated .close() on workflow/checkpointer services.
            if "checkpointer" in line.lower() or "manager" in line.lower():
                continue
            if re.search(r"\b(?:session|_session|self\._session)\.close\s*\(", line):
                rel = path.relative_to(_REPO_ROOT).as_posix()
                hits.append(f"{rel}:{line_no}: {line}")
    assert hits == [], (
        "SessionLike modules must not close the caller's Session:\n" + "\n".join(hits)
    )


def test_nested_get_session_only_at_composition_roots() -> None:
    """Avoid opening a second get_session() from typical SessionLike services."""
    root = _REPO_ROOT / "archium" / "application"
    pattern = re.compile(
        r"^\s*(?:from\s+archium\.infrastructure\.database\.session\s+import\s+.*\bget_session\b"
        r"|from\s+archium\.infrastructure\.database\s+import\s+session\b"
        r"|with\s+get_session\s*\()"
    )
    hits: list[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(_REPO_ROOT).as_posix()
        if rel in _NESTED_GET_SESSION_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if "SessionLike" not in text and "session_of" not in text:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if "get_session" not in line:
                continue
            if pattern.search(line) or re.search(r"\bget_session\s*\(", line):
                # Allow mentions in comments/docstrings.
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                if "get_session()" in stripped or "import" in stripped and "get_session" in stripped:
                    hits.append(f"{rel}:{i}: {stripped}")
    assert hits == [], (
        "SessionLike services should not open nested get_session() "
        f"(allowlist={sorted(_NESTED_GET_SESSION_ALLOWLIST)}):\n" + "\n".join(hits)
    )

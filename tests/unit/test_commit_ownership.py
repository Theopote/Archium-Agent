"""Guard APP-003 / DB-005 / DB-007: commit only at allowed transaction boundaries."""

from __future__ import annotations

import re
from pathlib import Path

_COMMIT_CALL = re.compile(r"(?<![\w.])(?:session|_session|self\._session)\.commit\s*\(")

# Application modules allowed to own an explicit commit (use-case / visibility).
_APPLICATION_COMMIT_ALLOWLIST = frozenset(
    {
        "archium/application/visual/transaction_executor.py",
        "archium/application/workflow_checkpoint.py",
        "archium/application/presentation_workflow_service.py",
        "archium/application/planning_workflow_service.py",
        "archium/application/visual/visual_workflow_service.py",
        "archium/application/project_deletion_service.py",
        "archium/application/project_management_service.py",
    }
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _hits_in(root: Path) -> list[str]:
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _COMMIT_CALL.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            rel = path.relative_to(_REPO_ROOT).as_posix()
            hits.append(f"{rel}:{line_no}")
    return hits


def test_ui_does_not_call_session_commit() -> None:
    """UI relies on get_session() exit (or application use-case) for commit."""
    hits = _hits_in(_REPO_ROOT / "archium" / "ui")
    assert hits == [], "UI must not call session.commit():\n" + "\n".join(hits)


def test_infrastructure_does_not_own_session_commit() -> None:
    """Only session.py may commit inside infrastructure (DB-007)."""
    hits = [
        hit
        for hit in _hits_in(_REPO_ROOT / "archium" / "infrastructure")
        if not hit.startswith("archium/infrastructure/database/session.py:")
    ]
    assert hits == [], "infrastructure must not session.commit():\n" + "\n".join(hits)


def test_application_commits_only_at_allowlisted_boundaries() -> None:
    """Nested helpers flush; use-case owners may commit (APP-003 / DB-005)."""
    hits = _hits_in(_REPO_ROOT / "archium" / "application")
    offenders = [
        hit
        for hit in hits
        if hit.rsplit(":", 1)[0] not in _APPLICATION_COMMIT_ALLOWLIST
    ]
    assert offenders == [], (
        "unexpected application session.commit() outside allowlist:\n"
        + "\n".join(offenders)
    )

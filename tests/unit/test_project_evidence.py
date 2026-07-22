"""Project evidence availability is tri-state and fail-closed."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from archium.application.project_evidence import (
    ProjectEvidenceStatus,
    resolve_project_evidence,
    resolve_project_evidence_safe,
)
from archium.domain.enums import EvidenceAvailability


def test_resolve_evidence_available() -> None:
    session = MagicMock()
    with patch(
        "archium.infrastructure.database.repositories.DocumentRepository"
    ) as repo_cls:
        repo_cls.return_value.list_by_project.return_value = [object(), object()]
        status = resolve_project_evidence(session, uuid4())
    assert status.availability == EvidenceAvailability.AVAILABLE
    assert status.document_count == 2
    assert status.allows_formal_export


def test_resolve_evidence_missing() -> None:
    session = MagicMock()
    with patch(
        "archium.infrastructure.database.repositories.DocumentRepository"
    ) as repo_cls:
        repo_cls.return_value.list_by_project.return_value = []
        status = resolve_project_evidence(session, uuid4())
    assert status.availability == EvidenceAvailability.MISSING
    assert status.is_concept_draft
    assert not status.allows_formal_export


def test_resolve_evidence_safe_unknown_on_failure() -> None:
    with patch(
        "archium.infrastructure.database.session.get_session",
        side_effect=RuntimeError("db down"),
    ):
        status = resolve_project_evidence_safe(uuid4())
    assert status.availability == EvidenceAvailability.UNKNOWN
    assert status.is_unknown
    assert not status.allows_formal_export


def test_studio_and_deliver_both_fail_closed_on_unknown() -> None:
    """Regression: Studio must not treat query failure as has_docs=True."""
    from pathlib import Path

    export = (
        Path(__file__).resolve().parents[2]
        / "archium"
        / "ui"
        / "studio"
        / "export_panel.py"
    ).read_text(encoding="utf-8")
    deliver = (
        Path(__file__).resolve().parents[2]
        / "archium"
        / "ui"
        / "pages"
        / "flow"
        / "deliver.py"
    ).read_text(encoding="utf-8")
    assert "_project_has_documents" not in export
    assert "resolve_project_evidence_safe" in export
    assert "allows_formal_export" in export
    assert "resolve_project_evidence_safe" in deliver
    assert "资料状态无法验证" in deliver
    assert (
        ProjectEvidenceStatus(
            availability=EvidenceAvailability.UNKNOWN
        ).allows_formal_export
        is False
    )

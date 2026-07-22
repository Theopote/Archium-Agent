"""Tests for unified evidence + delivery readiness service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from archium.application.evidence_readiness_service import (
    DeliveryReadinessReport,
    ProjectEvidenceStatus,
    assert_formal_export_allowed,
    resolve_project_evidence,
    resolve_project_evidence_safe,
)
from archium.domain.enums import EvidenceAvailability
from archium.exceptions import WorkflowError


def test_resolve_evidence_available() -> None:
    session = MagicMock()
    with patch(
        "archium.infrastructure.database.repositories.DocumentRepository"
    ) as repo_cls:
        repo_cls.return_value.list_by_project.return_value = [object(), object()]
        status = resolve_project_evidence(session, uuid4())
    assert status.availability == EvidenceAvailability.AVAILABLE
    assert status.document_count == 2


def test_resolve_evidence_safe_unknown_on_failure() -> None:
    with patch(
        "archium.infrastructure.database.session.get_session",
        side_effect=RuntimeError("db down"),
    ):
        status = resolve_project_evidence_safe(uuid4())
    assert status.availability == EvidenceAvailability.UNKNOWN


def test_formal_export_gate_blocks_draft() -> None:
    report = DeliveryReadinessReport(
        evidence=ProjectEvidenceStatus(
            availability=EvidenceAvailability.MISSING,
            document_count=0,
        ),
        pptx_ready=True,
        pdf_ready=True,
    )
    try:
        assert_formal_export_allowed(report, export_format="PPTX")
        raised = False
    except WorkflowError:
        raised = True
    assert raised


def test_formal_export_gate_requires_pptx_ready() -> None:
    report = DeliveryReadinessReport(
        evidence=ProjectEvidenceStatus(
            availability=EvidenceAvailability.AVAILABLE,
            document_count=2,
        ),
        pptx_ready=False,
        pdf_ready=False,
        export_blocker_count=0,
    )
    with __import__("pytest").raises(WorkflowError, match="PPTX"):
        assert_formal_export_allowed(report, export_format="PPTX")


def test_studio_and_deliver_share_readiness_service() -> None:
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
    assert "evidence_readiness_service" in export
    assert "_assert_export_gate" in export
    assert "evidence_readiness_service" in deliver
    assert "revision_id" in export

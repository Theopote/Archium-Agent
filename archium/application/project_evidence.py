"""Backward-compatible re-exports — prefer evidence_readiness_service."""

from __future__ import annotations

from archium.application.evidence_readiness_service import (
    ProjectEvidenceStatus,
    resolve_project_evidence,
    resolve_project_evidence_safe,
)

__all__ = [
    "ProjectEvidenceStatus",
    "resolve_project_evidence",
    "resolve_project_evidence_safe",
]

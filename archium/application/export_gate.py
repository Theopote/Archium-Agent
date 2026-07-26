"""Formal export gate facade (APP-004).

QA stacks (AutomatedReview / DeckQA / SceneSemantic / PresentationCritic /
citation gaps / materials evidence) **only produce evidence**. Product export
UI and formal export actions must read a single ``ExportVerdict``.

Canonical entrypoints:
- ``resolve_export_verdict`` / ``resolve_export_verdict_safe``
- ``assert_formal_export_allowed`` (accepts ExportVerdict; DeliveryReadinessReport
  still accepted for legacy callers and converts via ``to_export_verdict``)
"""

from __future__ import annotations

from archium.application.evidence_readiness_service import (
    assert_formal_export_allowed,
    resolve_export_verdict,
    resolve_export_verdict_safe,
)
from archium.domain.export_verdict import ExportVerdict, ExportVerdictStatus

__all__ = [
    "ExportVerdict",
    "ExportVerdictStatus",
    "assert_formal_export_allowed",
    "resolve_export_verdict",
    "resolve_export_verdict_safe",
]

"""Automated presentation review — content / evidence / architectural / layout / visual QA."""

from archium.application.review.design_critique_service import (
    DesignCritiqueGateResult,
    DesignCritiqueService,
)
from archium.application.review.export_gating import (
    critical_export_block_messages,
    export_blocking_open_issues,
)
from archium.application.review.service import AutomatedReviewService

__all__ = [
    "AutomatedReviewService",
    "DesignCritiqueGateResult",
    "DesignCritiqueService",
    "critical_export_block_messages",
    "export_blocking_open_issues",
]

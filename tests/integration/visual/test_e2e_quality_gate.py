"""E2E Quality Gate (nightly).

Proves post-hoc layout quality with the real ``LayoutValidationService`` (no
``always_valid_layouts`` monkeypatch).

Does **not** assert pixel-level screenshot regression; Pipeline Gate only checks
``screenshot_count >= slide_count``. Visual baseline comparison remains future work.
"""

from __future__ import annotations

import pytest
from archium.application.visual.e2e_benchmark_service import E2EBenchmarkService
from tests.integration.visual.e2e_quality_gate_cases import (
    E2E_QUALITY_GATE_CASE_ID,
    QUALITY_GATE_PROJECT_PROPOSAL,
)

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_quality]


class TestE2EQualityGate:
    def test_quality_gate_real_layout_validation(
        self,
        gate_service: E2EBenchmarkService,
    ) -> None:
        """No validation bypass: rule pass rate and layout scores must meet thresholds."""
        result = gate_service.run_case(QUALITY_GATE_PROJECT_PROPOSAL)
        assert result.case_id == E2E_QUALITY_GATE_CASE_ID
        assert result.quality_metrics.passed, result.failure_reasons
        assert result.quality_metrics.rule_pass_rate >= 0.75

    def test_quality_gate_screenshot_scope_is_count_only(
        self,
        gate_service: E2EBenchmarkService,
    ) -> None:
        """Document current screenshot QA limits (no blank/duplicate image detection)."""
        result = gate_service.run_case(QUALITY_GATE_PROJECT_PROPOSAL)
        deliverable = result.deliverable
        if deliverable is None or not deliverable.screenshot_tools_available:
            pytest.skip("Screenshot tools unavailable in this environment")
        assert deliverable.screenshot_count >= result.actual_slide_count
        assert all(path.exists() for path in deliverable.screenshot_paths)

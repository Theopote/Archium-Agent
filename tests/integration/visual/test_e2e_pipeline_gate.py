"""E2E Pipeline Gate (nightly).

Proves the deliverable chain runs end-to-end:

content planning → visual workflow → PPTX export → screenshot count check.

Uses ``always_valid_layouts`` so in-workflow ``LayoutValidationService`` does not
block export. This gate does **not** prove real layout validation passes; see
``test_e2e_quality_gate.py`` for that.
"""

from __future__ import annotations

import pytest
from archium.application.visual.e2e_benchmark_service import (
    E2E_DELIVERABLE_NOTES,
    E2EBenchmarkService,
)
from archium.infrastructure.renderers.pptx_screenshot import screenshot_tools_available
from tests.integration.visual.e2e_quality_gate_cases import (
    E2E_QUALITY_GATE_CASE_ID,
    E2E_QUALITY_GATE_CASES,
    E2E_QUALITY_GATE_MIN_PASS_RATE,
    QUALITY_GATE_PROJECT_PROPOSAL,
)

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_pipeline]


def _assert_pipeline_gate_passed(result, *, case_id: str) -> None:  # noqa: ANN001
    assert result.case_id == case_id
    assert result.execution_mode == "full"
    assert result.notes == E2E_DELIVERABLE_NOTES
    assert result.passed, (
        f"E2E pipeline gate failed for {case_id}: {result.failure_reasons}"
    )
    assert result.deliverable is not None
    assert result.deliverable.pptx_exported
    assert result.deliverable.pptx_path
    if result.deliverable.screenshot_tools_available:
        assert result.deliverable.screenshot_count >= result.actual_slide_count, (
            f"screenshots {result.deliverable.screenshot_count} "
            f"< slides {result.actual_slide_count} "
            "(count-only check; pixel regression not implemented)"
        )
    assert result.quality_metrics.passed


class TestE2EPipelineGate:
    def test_pipeline_gate_deliverable_case_passes(
        self,
        gate_service: E2EBenchmarkService,
        always_valid_layouts: None,
    ) -> None:
        result = gate_service.run_case(QUALITY_GATE_PROJECT_PROPOSAL)
        _assert_pipeline_gate_passed(result, case_id=E2E_QUALITY_GATE_CASE_ID)

    def test_pipeline_gate_suite_pass_rate(
        self,
        gate_service: E2EBenchmarkService,
        always_valid_layouts: None,
    ) -> None:
        summary = gate_service.run_suite(list(E2E_QUALITY_GATE_CASES))
        assert summary.total_cases == len(E2E_QUALITY_GATE_CASES)
        assert summary.pass_rate >= E2E_QUALITY_GATE_MIN_PASS_RATE, (
            f"pass rate {summary.pass_rate} below {E2E_QUALITY_GATE_MIN_PASS_RATE}; "
            f"failures: {summary.common_failures}"
        )

    @pytest.mark.skipif(
        not screenshot_tools_available(),
        reason="LibreOffice/pdftoppm required for real screenshot export gate",
    )
    def test_pipeline_gate_real_pptx_screenshots(
        self,
        gate_service: E2EBenchmarkService,
        always_valid_layouts: None,
    ) -> None:
        """Real PptxGen + LibreOffice/pdftoppm; screenshot QA is count-only."""
        result = gate_service.run_case(QUALITY_GATE_PROJECT_PROPOSAL)
        _assert_pipeline_gate_passed(result, case_id=E2E_QUALITY_GATE_CASE_ID)
        assert result.deliverable is not None
        assert result.deliverable.screenshot_tools_available
        assert result.deliverable.screenshot_count >= result.actual_slide_count

"""Nightly E2E Benchmark quality gate (M5).

Runs the full deliverable pipeline and requires ``passed=True``.
Excluded from PR CI via ``@pytest.mark.e2e``; scheduled in
``.github/workflows/e2e-benchmark-nightly.yml``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from archium.application.visual.e2e_benchmark_service import (
    E2E_DELIVERABLE_NOTES,
    E2EBenchmarkService,
)
from archium.infrastructure.llm import MockLLMProvider
from archium.infrastructure.renderers.pptx_screenshot import screenshot_tools_available
from sqlalchemy.orm import Session
from tests.fixtures.mock_llm import pipeline_mock_selector
from tests.golden.fixtures.loader import materialize_inline_docx
from tests.integration.visual.e2e_quality_gate_cases import (
    E2E_QUALITY_GATE_CASE_ID,
    E2E_QUALITY_GATE_CASES,
    E2E_QUALITY_GATE_MIN_PASS_RATE,
    QUALITY_GATE_PROJECT_PROPOSAL,
)

pytestmark = pytest.mark.e2e


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    return MockLLMProvider(selector=pipeline_mock_selector)


@pytest.fixture
def sample_docx_file(tmp_path: Path) -> Path:
    return materialize_inline_docx(
        tmp_path / "source.docx",
        {
            "paragraphs": [
                "老院区交通组织混乱，人车混行严重。",
                "需要通过交通重组改善患者到达体验。",
            ],
        },
    )


@pytest.fixture
def sample_image_file(tmp_path: Path) -> Path:
    source = (
        Path(__file__).resolve().parents[2]
        / "calibration"
        / "visual_qa"
        / "corpus"
        / "images"
        / "photo_005.png"
    )
    target = tmp_path / "hero_candidate.png"
    shutil.copy(source, target)
    return target


@pytest.fixture
def always_valid_layouts(monkeypatch: pytest.MonkeyPatch) -> None:
    from archium.domain.visual.validation import LayoutValidationReport

    def _always_valid(self, layout_plan, design_system, **kwargs):  # noqa: ANN001, ARG001
        return LayoutValidationReport(issues=[], score=1.0)

    monkeypatch.setattr(
        "archium.application.visual.layout_validation_service.LayoutValidationService.validate",
        _always_valid,
    )


@pytest.fixture
def quality_gate_data_files(
    sample_docx_file: Path,
    sample_image_file: Path,
    tmp_path: Path,
) -> Path:
    """Materialize gate inputs into the service data directory."""
    data_dir = tmp_path / "quality_gate_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for source in (sample_docx_file, sample_image_file):
        target = data_dir / source.name
        target.write_bytes(source.read_bytes())
    return data_dir


@pytest.fixture
def quality_gate_service(
    db_session: Session,
    quality_gate_data_files: Path,
    test_settings: object,
    mock_llm: MockLLMProvider,
) -> E2EBenchmarkService:
    return E2EBenchmarkService(
        db_session,
        quality_gate_data_files,
        llm=mock_llm,
        settings=test_settings,  # type: ignore[arg-type]
    )


def _assert_result_passed(result, *, case_id: str) -> None:  # noqa: ANN001
    assert result.case_id == case_id
    assert result.execution_mode == "full"
    assert result.notes == E2E_DELIVERABLE_NOTES
    assert result.passed, (
        f"E2E quality gate failed for {case_id}: {result.failure_reasons}"
    )
    assert result.deliverable is not None
    assert result.deliverable.pptx_exported
    assert result.deliverable.pptx_path
    if result.deliverable.screenshot_tools_available:
        assert result.deliverable.screenshot_count >= result.actual_slide_count, (
            f"screenshots {result.deliverable.screenshot_count} "
            f"< slides {result.actual_slide_count}"
        )
    assert result.quality_metrics.passed


class TestE2EBenchmarkQualityGate:
    def test_quality_gate_case_passes(
        self,
        quality_gate_service: E2EBenchmarkService,
        always_valid_layouts: None,
    ) -> None:
        """Nightly gate: full deliverable pipeline must reach passed=True."""
        result = quality_gate_service.run_case(QUALITY_GATE_PROJECT_PROPOSAL)
        _assert_result_passed(result, case_id=E2E_QUALITY_GATE_CASE_ID)

    def test_quality_gate_posthoc_layout_quality(
        self,
        quality_gate_service: E2EBenchmarkService,
    ) -> None:
        """Assert real LayoutValidationService scoring (no workflow validation bypass)."""
        result = quality_gate_service.run_case(QUALITY_GATE_PROJECT_PROPOSAL)
        assert result.case_id == E2E_QUALITY_GATE_CASE_ID
        assert result.quality_metrics.passed, result.failure_reasons
        assert result.quality_metrics.rule_pass_rate >= 0.75

    def test_quality_gate_suite_pass_rate(
        self,
        quality_gate_service: E2EBenchmarkService,
        always_valid_layouts: None,
    ) -> None:
        summary = quality_gate_service.run_suite(list(E2E_QUALITY_GATE_CASES))
        assert summary.total_cases == len(E2E_QUALITY_GATE_CASES)
        assert summary.pass_rate >= E2E_QUALITY_GATE_MIN_PASS_RATE, (
            f"pass rate {summary.pass_rate} below {E2E_QUALITY_GATE_MIN_PASS_RATE}; "
            f"failures: {summary.common_failures}"
        )

    @pytest.mark.skipif(
        not screenshot_tools_available(),
        reason="LibreOffice/pdftoppm required for real screenshot export gate",
    )
    def test_quality_gate_real_pptx_screenshots(
        self,
        quality_gate_service: E2EBenchmarkService,
        always_valid_layouts: None,
    ) -> None:
        """Uses real PptxGen + LibreOffice/pdftoppm (no screenshot monkeypatch)."""
        result = quality_gate_service.run_case(QUALITY_GATE_PROJECT_PROPOSAL)
        _assert_result_passed(result, case_id=E2E_QUALITY_GATE_CASE_ID)
        assert result.deliverable is not None
        assert result.deliverable.screenshot_tools_available
        assert result.deliverable.screenshot_count >= result.actual_slide_count

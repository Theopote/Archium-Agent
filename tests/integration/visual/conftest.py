"""Shared fixtures for visual integration tests (E2E gates and related)."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.visual.e2e_benchmark_service import E2EBenchmarkService
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session
from tests.fixtures.mock_llm import pipeline_mock_selector
from tests.golden.fixtures.loader import materialize_inline_docx, materialize_inline_image


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
    # Inline image keeps gate fixtures independent of optional calibration corpus binaries.
    return materialize_inline_image(
        tmp_path / "hero_candidate.png",
        {"width": 640, "height": 480, "color": [120, 140, 160]},
    )

@pytest.fixture
def always_valid_layouts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass in-workflow LayoutValidationService (Pipeline Gate only)."""
    from archium.domain.visual.validation import LayoutValidationReport

    def _always_valid(self, layout_plan, design_system, **kwargs):  # noqa: ANN001, ARG001
        return LayoutValidationReport(issues=[], score=1.0)

    monkeypatch.setattr(
        "archium.application.visual.layout_validation_service.LayoutValidationService.validate",
        _always_valid,
    )


@pytest.fixture
def gate_data_files(
    sample_docx_file: Path,
    sample_image_file: Path,
    tmp_path: Path,
) -> Path:
    data_dir = tmp_path / "gate_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for source in (sample_docx_file, sample_image_file):
        target = data_dir / source.name
        target.write_bytes(source.read_bytes())
    return data_dir


@pytest.fixture
def gate_service(
    db_session: Session,
    gate_data_files: Path,
    test_settings: object,
    mock_llm: MockLLMProvider,
) -> E2EBenchmarkService:
    return E2EBenchmarkService(
        db_session,
        gate_data_files,
        llm=mock_llm,
        settings=test_settings,  # type: ignore[arg-type]
    )

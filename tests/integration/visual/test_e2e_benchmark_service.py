"""Integration tests for E2EBenchmarkService (E2E Lite)."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from archium.application.visual.e2e_benchmark_service import (
    E2E_CONTENT_NOTES,
    E2E_DELIVERABLE_NOTES,
    E2E_FULL_NOTES,
    E2E_LITE_NOTES,
    E2EBenchmarkService,
)
from archium.infrastructure.llm import MockLLMProvider
from archium.domain.visual.e2e_benchmark import (
    E2EBenchmarkCase,
    E2EContentExpectation,
    E2EExpectedOutcomes,
    E2EHeroAssetExpectation,
)

from tests.fixtures.mock_llm import pipeline_mock_selector
from tests.golden.fixtures.loader import materialize_inline_docx


@pytest.fixture
def benchmark_service(db_session: Session, tmp_path: Path) -> E2EBenchmarkService:
    return E2EBenchmarkService(db_session, tmp_path)


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    return MockLLMProvider(selector=pipeline_mock_selector)


@pytest.fixture
def benchmark_service_with_llm(
    db_session: Session,
    tmp_path: Path,
    test_settings: object,
    mock_llm: MockLLMProvider,
) -> E2EBenchmarkService:
    return E2EBenchmarkService(
        db_session,
        tmp_path,
        llm=mock_llm,
        settings=test_settings,  # type: ignore[arg-type]
    )


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
def sample_benchmark_case(sample_image_file: Path) -> E2EBenchmarkCase:
    return E2EBenchmarkCase(
        case_id="test_case_001",
        scenario="project_proposal",
        title="Lite benchmark smoke",
        description="Verify E2E Lite wiring without full content planning.",
        task_description="根据测试资料生成一页说明性汇报",
        input_documents=[],
        input_images=[sample_image_file.name],
        expected_outcomes=E2EExpectedOutcomes(
            min_slide_count=1,
            max_slide_count=3,
            content_expectations=E2EContentExpectation(
                required_keywords=["测试", "说明"],
            ),
            hero_asset_expectations=E2EHeroAssetExpectation(
                min_usage_ratio=0.0,
                max_reuse_count=3,
            ),
            min_rule_pass_rate=0.0,
            min_avg_layout_score=0.0,
            min_deck_qa_score=0.0,
        ),
    )


@pytest.fixture
def content_planning_benchmark_case(
    sample_docx_file: Path,
    sample_image_file: Path,
) -> E2EBenchmarkCase:
    return E2EBenchmarkCase(
        case_id="content_planning_001",
        scenario="project_proposal",
        title="老院区更新概念汇报",
        description="Verify Brief→Storyline→SlideSpec from imported DOCX.",
        task_description="根据任务书制作交通改造汇报",
        input_documents=[sample_docx_file.name],
        input_images=[sample_image_file.name],
        enable_content_planning=True,
        expected_outcomes=E2EExpectedOutcomes(
            min_slide_count=4,
            max_slide_count=4,
            content_expectations=E2EContentExpectation(
                required_keywords=["交通", "改造"],
            ),
            hero_asset_expectations=E2EHeroAssetExpectation(
                min_usage_ratio=0.0,
                max_reuse_count=3,
            ),
            min_rule_pass_rate=0.0,
            min_avg_layout_score=0.0,
            min_deck_qa_score=0.0,
        ),
    )


@pytest.fixture
def full_benchmark_case(content_planning_benchmark_case: E2EBenchmarkCase) -> E2EBenchmarkCase:
    return content_planning_benchmark_case.model_copy(
        update={
            "case_id": "full_pipeline_001",
            "enable_visual_workflow": True,
        }
    )


@pytest.fixture
def deliverable_benchmark_case(full_benchmark_case: E2EBenchmarkCase) -> E2EBenchmarkCase:
    return full_benchmark_case.model_copy(
        update={
            "case_id": "deliverable_001",
            "enable_pptx_export": True,
            "enable_screenshot_check": True,
        }
    )


@pytest.fixture
def fake_pptx_export(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_export(
        self,
        deck,
        *,
        output_dir,
        pptx_name: str = "presentation.layout_plan.pptx",
        deck_name: str = "presentation.layout_instructions.json",
    ):  # noqa: ANN001
        from pathlib import Path

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        deck_path = out / deck_name
        if not deck_path.exists():
            deck_path.write_text("{}", encoding="utf-8")
        pptx_path = out / pptx_name
        pptx_path.write_bytes(b"PK\x03\x04fake")
        return deck_path, pptx_path

    def _fake_export_pptx_slide_pngs(
        pptx_path,
        output_dir,
        **kwargs,  # noqa: ANN003, ARG001
    ):
        from pathlib import Path

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths = []
        for index in range(1, 5):
            png_path = out / f"slide_{index:02d}.png"
            png_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            paths.append(png_path)
        return paths

    monkeypatch.setattr(
        "archium.infrastructure.renderers.pptxgen_renderer.PptxGenPresentationRenderer.export_pptx_from_layout_instructions",
        _fake_export,
    )
    monkeypatch.setattr(
        "archium.infrastructure.renderers.pptx_screenshot.export_pptx_slide_pngs",
        _fake_export_pptx_slide_pngs,
    )
    monkeypatch.setattr(
        "archium.application.visual.e2e_benchmark_service.screenshot_tools_available",
        lambda: True,
    )


@pytest.fixture
def always_valid_layouts(monkeypatch: pytest.MonkeyPatch) -> None:
    from archium.domain.visual.validation import LayoutValidationReport

    def _always_valid(self, layout_plan, design_system, **kwargs):  # noqa: ANN001, ARG001
        return LayoutValidationReport(issues=[], score=1.0)

    monkeypatch.setattr(
        "archium.application.visual.layout_validation_service.LayoutValidationService.validate",
        _always_valid,
    )


class TestE2EBenchmarkServiceBasic:
    def test_service_initialization(self, db_session: Session, tmp_path: Path) -> None:
        service = E2EBenchmarkService(db_session, tmp_path)
        assert service._session == db_session
        assert service._data_dir == tmp_path

    def test_service_has_required_dependencies(self, benchmark_service: E2EBenchmarkService) -> None:
        assert benchmark_service._projects is not None
        assert benchmark_service._presentations is not None
        assert benchmark_service._ingestion is not None
        assert benchmark_service._layout_planning is not None
        assert benchmark_service._validation is not None
        assert benchmark_service._deck_qa is not None
        assert benchmark_service._layout_plans is not None
        assert benchmark_service._design_systems is not None


class TestE2EBenchmarkServiceFileHandling:
    def test_handles_missing_input_file(
        self,
        benchmark_service: E2EBenchmarkService,
        sample_benchmark_case: E2EBenchmarkCase,
    ) -> None:
        case = sample_benchmark_case.model_copy(
            update={
                "case_id": "test_missing_file",
                "input_documents": ["nonexistent.md"],
                "input_images": [],
            }
        )
        result = benchmark_service.run_case(case)
        assert result.execution_mode == "lite"
        assert not result.passed
        assert any("不存在" in reason for reason in result.failure_reasons)

    def test_handles_empty_document_list(
        self,
        benchmark_service: E2EBenchmarkService,
        sample_benchmark_case: E2EBenchmarkCase,
    ) -> None:
        case = sample_benchmark_case.model_copy(update={"case_id": "test_empty_docs"})
        result = benchmark_service.run_case(case)
        assert result.case_id == "test_empty_docs"
        assert result.execution_mode == "lite"
        assert result.design_system_id is not None
        assert isinstance(result.failure_reasons, list)


@pytest.mark.integration
class TestE2EBenchmarkServiceIntegration:
    def test_run_case_lite_produces_layout_and_case_scoped_design_system(
        self,
        benchmark_service: E2EBenchmarkService,
        sample_benchmark_case: E2EBenchmarkCase,
    ) -> None:
        """CI-runnable Lite test: verify wiring, not full product quality."""
        result = benchmark_service.run_case(sample_benchmark_case)

        assert result.case_id == "test_case_001"
        assert result.execution_mode == "lite"
        assert result.design_system_id is not None
        assert result.notes == E2E_LITE_NOTES
        assert result.actual_slide_count >= sample_benchmark_case.expected_outcomes.min_slide_count
        assert result.quality_metrics is not None
        assert result.imported_asset_count == 1
        assert len(result.slide_details) == result.actual_slide_count
        if result.slide_details:
            assert result.slide_details[0]["layout_family"] is not None

    def test_design_system_is_isolated_per_case(
        self,
        benchmark_service: E2EBenchmarkService,
        sample_benchmark_case: E2EBenchmarkCase,
    ) -> None:
        case_a = sample_benchmark_case.model_copy(update={"case_id": "case_a"})
        case_b = sample_benchmark_case.model_copy(update={"case_id": "case_b"})
        result_a = benchmark_service.run_case(case_a)
        result_b = benchmark_service.run_case(case_b)
        assert result_a.design_system_id is not None
        assert result_b.design_system_id is not None
        assert result_a.design_system_id != result_b.design_system_id

    def test_image_import_records_assets(
        self,
        benchmark_service: E2EBenchmarkService,
        sample_benchmark_case: E2EBenchmarkCase,
    ) -> None:
        result = benchmark_service.run_case(sample_benchmark_case)
        assert result.imported_asset_count == 1

    def test_content_planning_generates_slides_from_imported_document(
        self,
        benchmark_service_with_llm: E2EBenchmarkService,
        content_planning_benchmark_case: E2EBenchmarkCase,
    ) -> None:
        result = benchmark_service_with_llm.run_case(content_planning_benchmark_case)

        assert result.execution_mode == "content"
        assert result.notes == E2E_CONTENT_NOTES
        assert result.actual_slide_count == 4
        assert result.design_system_id is not None
        titles = [detail["title"] for detail in result.slide_details]
        assert "院区现状" in titles
        assert "改造策略" in titles

    def test_full_pipeline_runs_visual_workflow(
        self,
        benchmark_service_with_llm: E2EBenchmarkService,
        full_benchmark_case: E2EBenchmarkCase,
        always_valid_layouts: None,
    ) -> None:
        result = benchmark_service_with_llm.run_case(full_benchmark_case)

        assert result.execution_mode == "full"
        assert result.notes == E2E_FULL_NOTES
        assert result.actual_slide_count == 4
        assert result.visual_layout_plan_count == 4
        assert result.design_system_id is not None
        assert all(detail["layout_family"] is not None for detail in result.slide_details)

    def test_deliverable_export_produces_pptx_and_screenshots(
        self,
        benchmark_service_with_llm: E2EBenchmarkService,
        deliverable_benchmark_case: E2EBenchmarkCase,
        always_valid_layouts: None,
        fake_pptx_export: None,
    ) -> None:
        result = benchmark_service_with_llm.run_case(deliverable_benchmark_case)

        assert result.execution_mode == "full"
        assert result.notes == E2E_DELIVERABLE_NOTES
        assert result.actual_slide_count == 4
        assert result.deliverable is not None
        assert result.deliverable.pptx_exported is True
        assert result.deliverable.pptx_path is not None
        assert result.deliverable.pptx_path.endswith(".pptx")
        assert result.deliverable.screenshot_tools_available is True
        assert result.deliverable.screenshot_count == 4
        assert len(result.deliverable.screenshot_paths) == 4
        assert result.deliverable.passed is True

    def test_layout_plan_repository_integration(
        self,
        benchmark_service: E2EBenchmarkService,
    ) -> None:
        fake_id = uuid4()
        assert benchmark_service._layout_plans.get(fake_id) is None


@pytest.mark.e2e
class TestE2EBenchmarkServiceEndToEnd:
    def test_complete_workflow_smoke(
        self,
        benchmark_service_with_llm: E2EBenchmarkService,
        full_benchmark_case: E2EBenchmarkCase,
        always_valid_layouts: None,
    ) -> None:
        """Marked e2e: content planning + VisualWorkflowService."""
        result = benchmark_service_with_llm.run_case(full_benchmark_case)
        assert result.execution_mode == "full"
        assert result.actual_slide_count >= 1
        assert result.visual_layout_plan_count >= 1
        assert result.design_system_id is not None
        assert isinstance(result.failure_reasons, list)


class TestE2EBenchmarkServiceAPIUsage:
    def test_uses_import_file_not_import_from_files(self, benchmark_service: E2EBenchmarkService) -> None:
        assert hasattr(benchmark_service._ingestion, "import_file")
        assert not hasattr(benchmark_service._ingestion, "import_from_files")

    def test_uses_layout_plan_repository_get(self, benchmark_service: E2EBenchmarkService) -> None:
        assert hasattr(benchmark_service._layout_plans, "get")
        assert not hasattr(benchmark_service._presentations, "get_layout_plan")

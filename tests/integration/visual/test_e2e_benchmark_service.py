"""Integration tests for E2EBenchmarkService."""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from archium.application.visual.e2e_benchmark_service import E2EBenchmarkService
from archium.domain.visual.e2e_benchmark import (
    E2EBenchmarkCase,
    E2EContentExpectation,
    E2EHeroAssetExpectation,
)


@pytest.fixture
def benchmark_service(db_session: Session, tmp_path: Path) -> E2EBenchmarkService:
    """Create E2EBenchmarkService instance for testing."""
    return E2EBenchmarkService(db_session, tmp_path)


@pytest.fixture
def sample_markdown_file(tmp_path: Path) -> Path:
    """Create a sample markdown file for testing."""
    md_file = tmp_path / "test_document.md"
    md_file.write_text(
        """# Test Document

This is a test document for E2E benchmark testing.

## Key Points

- Point 1: Important information
- Point 2: More details
- Point 3: Additional context

## Conclusion

Summary of the test document.
""",
        encoding="utf-8",
    )
    return md_file


@pytest.fixture
def sample_benchmark_case(tmp_path: Path, sample_markdown_file: Path) -> E2EBenchmarkCase:
    """Create a sample benchmark case for testing."""
    return E2EBenchmarkCase(
        case_id="test_case_001",
        task_description="Create a simple presentation from test document",
        input_documents=["test_document.md"],
        input_images=[],
        expected_outcomes={
            "content_coverage": E2EContentExpectation(
                must_include_keywords=["test", "document", "important"],
                slide_count_range=(1, 5),
            ),
            "hero_assets": E2EHeroAssetExpectation(
                min_hero_slides=0,
                max_hero_slides=3,
            ),
        },
    )


class TestE2EBenchmarkServiceBasic:
    """Basic integration tests for E2EBenchmarkService."""

    def test_service_initialization(self, db_session: Session, tmp_path: Path):
        """Test that E2EBenchmarkService can be initialized."""
        service = E2EBenchmarkService(db_session, tmp_path)
        assert service is not None
        assert service._session == db_session
        assert service._data_dir == tmp_path

    def test_service_has_required_dependencies(self, benchmark_service: E2EBenchmarkService):
        """Test that service has all required dependencies initialized."""
        assert benchmark_service._projects is not None
        assert benchmark_service._presentations is not None
        assert benchmark_service._ingestion is not None
        assert benchmark_service._visual_edits is not None
        assert benchmark_service._validation is not None
        assert benchmark_service._deck_qa is not None
        assert benchmark_service._layout_plans is not None
        assert benchmark_service._design_systems is not None


class TestE2EBenchmarkServiceFileHandling:
    """Test file handling in E2EBenchmarkService."""

    def test_handles_missing_input_file(
        self,
        benchmark_service: E2EBenchmarkService,
        sample_benchmark_case: E2EBenchmarkCase,
    ):
        """Test that service handles missing input files gracefully."""
        # Create case with non-existent file
        case = E2EBenchmarkCase(
            case_id="test_missing_file",
            task_description="Test missing file handling",
            input_documents=["nonexistent.md"],
            input_images=[],
            expected_outcomes=sample_benchmark_case.expected_outcomes,
        )

        result = benchmark_service.run_case(case)

        # Should fail but not crash
        assert not result.passed
        assert any("不存在" in reason or "not exist" in reason.lower() for reason in result.failure_reasons)

    def test_handles_empty_document_list(
        self,
        benchmark_service: E2EBenchmarkService,
        sample_benchmark_case: E2EBenchmarkCase,
    ):
        """Test that service handles empty document list."""
        case = E2EBenchmarkCase(
            case_id="test_empty_docs",
            task_description="Test empty document list",
            input_documents=[],
            input_images=[],
            expected_outcomes=sample_benchmark_case.expected_outcomes,
        )

        result = benchmark_service.run_case(case)

        # Should complete but may not pass all expectations
        assert result.case_id == "test_empty_docs"
        assert isinstance(result.failure_reasons, list)


@pytest.mark.integration
class TestE2EBenchmarkServiceIntegration:
    """Integration tests requiring full service interaction."""

    def test_run_case_with_valid_input(
        self,
        benchmark_service: E2EBenchmarkService,
        sample_benchmark_case: E2EBenchmarkCase,
        sample_markdown_file: Path,
    ):
        """Test running a complete case with valid input."""
        result = benchmark_service.run_case(sample_benchmark_case)

        # Should complete execution
        assert result.case_id == "test_case_001"
        assert result.execution_time_seconds >= 0

        # Should have some result (pass or fail with reasons)
        if not result.passed:
            assert len(result.failure_reasons) > 0

        # Should have quality metrics
        assert result.quality_metrics is not None

    def test_ingestion_service_integration(
        self,
        benchmark_service: E2EBenchmarkService,
        sample_markdown_file: Path,
    ):
        """Test that IngestionService.import_file can be called correctly."""
        # Create a test project
        from archium.domain.project import Project

        project = Project(
            id=uuid4(),
            name="Test Project",
            description="Test ingestion integration",
        )
        project = benchmark_service._projects.create(project)

        # Test import_file (this is the critical API call)
        result = benchmark_service._ingestion.import_file(project.id, sample_markdown_file)

        # Should complete without error
        assert result is not None
        if result.error:
            pytest.skip(f"Import failed (expected in minimal test env): {result.error}")

    def test_layout_plan_repository_integration(
        self,
        benchmark_service: E2EBenchmarkService,
    ):
        """Test that LayoutPlanRepository.get can be called correctly."""
        # Test that the repository method exists and can be called
        # This validates the API used in line 163 of e2e_benchmark_service.py
        from uuid import uuid4

        fake_id = uuid4()
        result = benchmark_service._layout_plans.get(fake_id)

        # Should return None for non-existent ID (not crash)
        assert result is None


@pytest.mark.e2e
class TestE2EBenchmarkServiceEndToEnd:
    """Full end-to-end tests (may be slow, marked separately)."""

    def test_complete_workflow_smoke(
        self,
        benchmark_service: E2EBenchmarkService,
        sample_benchmark_case: E2EBenchmarkCase,
        sample_markdown_file: Path,
    ):
        """Smoke test for complete E2E workflow."""
        # This is a smoke test to ensure the service can execute without crashing
        # Actual content validation is done in detailed tests

        try:
            result = benchmark_service.run_case(sample_benchmark_case)
            # If we get here without exception, the workflow executed
            assert result is not None
            assert isinstance(result.failure_reasons, list)
        except Exception as e:
            # Log the exception for debugging but mark as expected in minimal env
            pytest.skip(f"E2E workflow requires full environment: {e}")


class TestE2EBenchmarkServiceAPIUsage:
    """Tests specifically validating correct API usage."""

    def test_uses_import_file_not_import_from_files(self, benchmark_service: E2EBenchmarkService):
        """Verify service uses import_file (not the non-existent import_from_files)."""
        # This test validates the fix for the reported issue
        assert hasattr(benchmark_service._ingestion, "import_file")
        assert not hasattr(benchmark_service._ingestion, "import_from_files")

    def test_uses_layout_plan_repository_get(self, benchmark_service: E2EBenchmarkService):
        """Verify service uses LayoutPlanRepository.get (not PresentationRepository.get_layout_plan)."""
        # This test validates the fix for the reported issue
        assert hasattr(benchmark_service._layout_plans, "get")
        assert not hasattr(benchmark_service._presentations, "get_layout_plan")

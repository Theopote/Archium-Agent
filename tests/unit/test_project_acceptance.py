"""Unit tests for real-project acceptance models."""

from __future__ import annotations

from datetime import UTC, datetime

from archium.domain.project_acceptance import (
    RealProjectAcceptanceMetrics,
    RealProjectAcceptanceRecord,
    RealProjectScenario,
)


def test_metrics_meets_automated_scope() -> None:
    metrics = RealProjectAcceptanceMetrics(
        first_generation_seconds=12.5,
        generation_succeeded=True,
        slide_count=20,
        asset_count=12,
        layout_plan_count=20,
        critical_layout_page_count=0,
        error_layout_page_count=3,
        drawing_crop_issue_count=0,
        export_acceptable=True,
        real_asset_utilization_rate=0.85,
    )
    assert metrics.meets_automated_scope()


def test_record_round_trip() -> None:
    record = RealProjectAcceptanceRecord(
        project_id="project_001_new_building",
        scenario=RealProjectScenario.NEW_BUILDING,
        title="测试",
        run_at=datetime.now(UTC),
        metrics=RealProjectAcceptanceMetrics(
            first_generation_seconds=1.0,
            generation_succeeded=True,
            slide_count=18,
            asset_count=10,
            layout_plan_count=18,
            critical_layout_page_count=0,
            error_layout_page_count=0,
            drawing_crop_issue_count=0,
            export_acceptable=True,
            fact_error_count=1,
            citation_error_count=2,
            image_usage_error_count=3,
            deliverable_ready=False,
            top_dissatisfactions=["主图偏小"],
            top_satisfactions=["故事线清晰"],
        ),
    )
    restored = RealProjectAcceptanceRecord.model_validate(record.model_dump(mode="json"))
    assert restored.project_id == record.project_id
    assert restored.metrics.fact_error_count == 1
    assert restored.metrics.top_satisfactions == ["故事线清晰"]

"""Unit tests for rule-based architectural metric extraction."""

from __future__ import annotations

from uuid import uuid4

from archium.application.fact_metric_extractor import extract_metrics_from_chunks
from archium.domain.document import DocumentChunk


def _chunk(content: str) -> DocumentChunk:
    return DocumentChunk(
        project_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content=content,
        page_number=1,
    )


def test_extract_plot_ratio_and_height() -> None:
    metrics = extract_metrics_from_chunks(
        [_chunk("规划指标：容积率 2.35，建筑高度 80 米，绿地率 35%。")]
    )
    by_key = {item.key: item for item in metrics}
    assert by_key["plot_ratio"].value == "2.35"
    assert by_key["height"].value == "80"
    assert by_key["height"].unit == "米"
    assert by_key["green_ratio"].value == "35"


def test_extract_site_area_and_bed_count() -> None:
    metrics = extract_metrics_from_chunks(
        [_chunk("用地面积约 12.5 公顷，规划床位 500 张。")]
    )
    by_key = {item.key: item for item in metrics}
    assert by_key["site_area"].value == "12.5"
    assert by_key["site_area"].unit == "公顷"
    assert by_key["bed_count"].value == "500"

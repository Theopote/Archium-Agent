"""Tests for table-row metric extraction."""

from __future__ import annotations

from uuid import uuid4

from archium.application.fact_metric_extractor import extract_metrics_from_chunks
from archium.domain.document import DocumentChunk


def test_extract_metrics_from_table_rows() -> None:
    chunk = DocumentChunk(
        project_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content="指标 | 数值\n用地面积 | 12000\n容积率 | 2.5\n",
        page_number=1,
        content_type="sheet",
    )
    metrics = extract_metrics_from_chunks([chunk])
    by_key = {item.key: item for item in metrics}
    assert by_key["site_area"].value == "12000"
    assert by_key["plot_ratio"].value == "2.5"

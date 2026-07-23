"""DOM-012: Layout / Scene / Spec share one chart-table payload VO."""

from __future__ import annotations

import pytest
from archium.domain.presentation_spec import SpecChart, SpecChartSeries, SpecTable
from archium.domain.visual.layout import LayoutChartData, LayoutTableData
from archium.domain.visual.render_scene import ChartSeriesData
from archium.domain.visual.structured_payload import (
    ChartDataPayload,
    TableDataPayload,
)

pytestmark = pytest.mark.unit


def test_layout_chart_table_are_canonical_payload_aliases() -> None:
    assert LayoutChartData is ChartDataPayload
    assert LayoutTableData is TableDataPayload
    assert SpecChart is ChartDataPayload
    assert SpecTable is TableDataPayload
    assert SpecChartSeries is ChartSeriesData


def test_chart_payload_round_trip_matches_series_type() -> None:
    payload = ChartDataPayload(
        chart_type="bar",
        title="规模",
        series=[ChartSeriesData(name="A", labels=["x"], values=[1.0])],
    )
    as_layout = LayoutChartData.model_validate(payload.model_dump())
    as_spec = SpecChart.model_validate(payload.model_dump())
    assert as_layout.series[0].name == "A"
    assert as_spec.title == "规模"
    assert as_layout.has_series_data is True
    table = TableDataPayload(headers=["h"], rows=[["v"]])
    assert SpecTable.model_validate(table.model_dump()).has_grid_data is True

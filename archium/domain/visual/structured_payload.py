"""Canonical structured chart/table payloads shared by LayoutPlan and RenderScene.

DOM-012: one VO for chart/table *data* (not style). Nodes and layout elements
embed or alias these types so fields do not drift.
"""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel


class ChartSeriesData(DomainModel):
    """One data series for a native or shape-baked chart."""

    name: str = Field(min_length=1)
    labels: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)


class ChartDataPayload(DomainModel):
    """Structured chart payload (layout element or scene node data fields)."""

    chart_type: str = Field(default="bar", min_length=1)
    title: str | None = None
    series: list[ChartSeriesData] = Field(default_factory=list)
    show_legend: bool = True
    show_value: bool = False

    @property
    def has_series_data(self) -> bool:
        return any(series.values for series in self.series)


class TableDataPayload(DomainModel):
    """Structured table grid payload."""

    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)

    @property
    def has_grid_data(self) -> bool:
        return bool(self.headers) and bool(self.rows)


# Layout-facing aliases (stable import paths for existing code).
LayoutChartData = ChartDataPayload
LayoutTableData = TableDataPayload

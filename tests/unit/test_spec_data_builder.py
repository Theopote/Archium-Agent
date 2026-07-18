"""Unit tests for chart/table spec data builder."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.enums import SlideType, VerificationStatus, VisualType
from archium.domain.fact import ProjectFact
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.renderers.spec_data_builder import (
    build_chart,
    build_table,
    resolve_numeric_layout,
)


def _slide(**overrides: object) -> SlideSpec:
    base = {
        "presentation_id": uuid4(),
        "chapter_id": "ch1",
        "order": 0,
        "title": "关键指标",
        "message": "核心规模数据",
        "key_points": ["总建筑面积：120000 ㎡", "床位数：800", "绿地率：35%"],
    }
    base.update(overrides)
    return SlideSpec.model_validate(base)


def test_build_chart_from_key_points() -> None:
    chart = build_chart(_slide())
    assert chart is not None
    assert chart.chart_type == "bar"
    assert chart.series[0].labels == ["总建筑面积", "床位数", "绿地率"]
    assert chart.series[0].values == [120000.0, 800.0, 35.0]


def test_build_chart_prefers_matching_project_facts() -> None:
    slide = _slide(
        title="规模指标",
        key_points=["建筑面积：120000", "床位数：800"],
    )
    facts = [
        ProjectFact(
            project_id=uuid4(),
            key="building_area",
            label="建筑面积",
            value=120000,
            unit="㎡",
            category="area",
            verification_status=VerificationStatus.USER_CONFIRMED,
        ),
        ProjectFact(
            project_id=uuid4(),
            key="bed_count",
            label="床位数",
            value=800,
            category="capacity",
            verification_status=VerificationStatus.USER_CONFIRMED,
        ),
    ]
    chart = build_chart(slide, facts)
    assert chart is not None
    assert chart.series[0].labels == ["建筑面积", "床位数"]
    assert chart.series[0].values == [120000.0, 800.0]


def test_build_table_from_facts_includes_units() -> None:
    slide = _slide(
        title="投资估算",
        key_points=[],
        visual_requirements=[VisualRequirement(type=VisualType.TABLE, description="造价表")],
    )
    facts = [
        ProjectFact(
            project_id=uuid4(),
            key="building_area",
            label="建筑面积",
            value=120000,
            unit="㎡",
            category="area",
            verification_status=VerificationStatus.USER_CONFIRMED,
        ),
        ProjectFact(
            project_id=uuid4(),
            key="plot_ratio",
            label="容积率",
            value="2.5",
            category="ratio",
            verification_status=VerificationStatus.USER_CONFIRMED,
        ),
    ]
    table = build_table(slide, facts)
    assert table is not None
    assert table.headers == ["指标", "数值", "单位"]
    assert table.rows[0] == ["建筑面积", "120000㎡", "㎡"]


def test_resolve_numeric_layout_for_chart_visual_requirement() -> None:
    slide = _slide(
        visual_requirements=[VisualRequirement(type=VisualType.CHART, description="规模对比图")],
    )
    assert resolve_numeric_layout(slide) == "chart"


def test_resolve_numeric_layout_for_table_visual_requirement() -> None:
    slide = _slide(
        key_points=["指标|改造前|改造后", "建筑面积|80000|120000", "床位数|600|800"],
        visual_requirements=[VisualRequirement(type=VisualType.TABLE, description="对比表")],
    )
    assert resolve_numeric_layout(slide) == "table"


def test_data_slide_with_single_metric_stays_on_data_layout() -> None:
    slide = _slide(slide_type=SlideType.DATA, key_points=["床位数：800"])
    assert resolve_numeric_layout(slide) == "data"

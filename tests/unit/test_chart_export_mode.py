"""Tests for ChartExportMode dual chart/table export strategy."""

from __future__ import annotations

from uuid import uuid4

from archium.application.export_policy_service import ExportPolicyService
from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.domain.export_fidelity import ChartExportMode, ExportPolicy
from archium.domain.powerpoint_capability import PowerPointFidelity, capability_for_scene_node
from archium.domain.slide import SlideSpec
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutChartData, LayoutElement, LayoutPlan, LayoutTableData
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    ChartNode,
    ChartSeriesData,
    RenderScene,
    TableNode,
)
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import PptxLayoutPlanAdapter
from archium.infrastructure.renderers.scene_pptx_adapter import RenderScenePptxAdapter


def test_chart_export_mode_enum_values() -> None:
    assert ChartExportMode.CROSS_APP_STABLE.value == "cross_app_stable"
    assert ChartExportMode.NATIVE_DATA_BACKED.value == "native_data_backed"
    policy = ExportPolicy(chart_export_mode=ChartExportMode.NATIVE_DATA_BACKED)
    assert policy.chart_export_mode is ChartExportMode.NATIVE_DATA_BACKED


def test_capability_maps_chart_and_table() -> None:
    assert capability_for_scene_node("chart").fidelity == PowerPointFidelity.NATIVE_STABLE
    assert capability_for_scene_node("table").fidelity == PowerPointFidelity.NATIVE_STABLE


def test_compiler_emits_chart_and_table_nodes() -> None:
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.METRIC_DASHBOARD,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        elements=[
            LayoutElement(
                id="chart1",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.CHART,
                x=0.5,
                y=1.0,
                width=4.5,
                height=3.0,
                chart_data=LayoutChartData(
                    chart_type="bar",
                    title="能耗",
                    series=[
                        ChartSeriesData(
                            name="kWh",
                            labels=["A", "B", "C"],
                            values=[10.0, 20.0, 15.0],
                        )
                    ],
                ),
            ),
            LayoutElement(
                id="table1",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TABLE,
                x=5.2,
                y=1.0,
                width=4.3,
                height=3.0,
                table_data=LayoutTableData(
                    headers=["项", "值"],
                    rows=[["面积", "12000"], ["层数", "8"]],
                ),
            ),
        ],
    )
    scene = RenderSceneCompiler().compile(
        slide=SlideSpec(
            id=plan.slide_id,
            presentation_id=uuid4(),
            chapter_id="ch1",
            order=0,
            title="指标",
            message="图表表格双导出",
        ),
        layout_plan=plan,
        design_system=default_presentation_design_system(),
    )
    chart = next(n for n in scene.nodes if isinstance(n, ChartNode))
    table = next(n for n in scene.nodes if isinstance(n, TableNode))
    assert chart.has_series_data
    assert table.has_grid_data
    assert chart.series[0].values == [10.0, 20.0, 15.0]
    assert table.headers == ["项", "值"]


def test_scene_adapter_emits_chart_series_and_mode() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ChartNode(
                id="c1",
                x=0.5,
                y=1.0,
                width=4,
                height=3,
                chart_type="bar",
                series=[
                    ChartSeriesData(name="S1", labels=["a", "b"], values=[1.0, 2.0])
                ],
            ),
            TableNode(
                id="t1",
                x=5,
                y=1,
                width=4,
                height=3,
                headers=["H1", "H2"],
                rows=[["1", "2"]],
            ),
        ],
    )
    deck = RenderScenePptxAdapter().render_deck(
        title="Charts",
        scenes=[(scene, None)],
        chart_export_mode=ChartExportMode.NATIVE_DATA_BACKED,
    )
    assert deck["chart_export_mode"] == "native_data_backed"
    chart_el = next(el for el in deck["slides"][0]["elements"] if el["content_type"] == "chart")
    table_el = next(el for el in deck["slides"][0]["elements"] if el["content_type"] == "table")
    assert chart_el["series"][0]["values"] == [1.0, 2.0]
    assert table_el["headers"] == ["H1", "H2"]


def test_layout_adapter_embeds_chart_data_and_mode() -> None:
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.METRIC_DASHBOARD,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        elements=[
            LayoutElement(
                id="chart1",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.CHART,
                x=0.5,
                y=1.0,
                width=4.5,
                height=3.0,
                chart_data=LayoutChartData(
                    series=[
                        ChartSeriesData(name="S", labels=["x"], values=[3.0])
                    ]
                ),
            )
        ],
    )
    design = default_presentation_design_system()
    deck = PptxLayoutPlanAdapter().render_deck(
        title="Layout chart",
        slides=[(plan, design, None)],
        chart_export_mode=ChartExportMode.CROSS_APP_STABLE,
    )
    assert deck["chart_export_mode"] == "cross_app_stable"
    assert deck["slides"][0]["elements"][0]["series"][0]["values"] == [3.0]


def test_export_policy_counts_native_charts_and_tables() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ChartNode(
                id="c1",
                x=0.5,
                y=1.0,
                width=4,
                height=3,
                series=[ChartSeriesData(name="S", labels=["a"], values=[1.0])],
            ),
            TableNode(
                id="t1",
                x=5,
                y=1,
                width=4,
                height=3,
                headers=["A"],
                rows=[["1"]],
            ),
        ],
    )
    result = ExportPolicyService().assess_scene_fidelity(scene)
    assert result.native_chart_count == 1
    assert result.native_table_count == 1

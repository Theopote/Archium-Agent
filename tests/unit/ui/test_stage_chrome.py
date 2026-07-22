"""Unit tests for product-flow stage chrome (stepper + gates)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from archium.ui.pages.flow import evaluate_stage_gate
from archium.ui.project_progress_card import ProjectProgressSnapshot


def _snapshot(**overrides: object) -> ProjectProgressSnapshot:
    base = {
        "project_id": uuid4(),
        "project_name": "测试项目",
        "presentation_id": uuid4(),
        "presentation_title": "汇报",
        "presentation_type": "client_review",
        "document_count": 2,
        "slide_count": 10,
        "layout_ready_count": 8,
        "has_brief": True,
        "ready_for_export": False,
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return ProjectProgressSnapshot(**base)  # type: ignore[arg-type]


def test_outline_gate_requires_materials_and_structure() -> None:
    empty = _snapshot(
        document_count=0,
        has_brief=False,
        presentation_id=None,
        slide_count=0,
        layout_ready_count=0,
    )
    gate = evaluate_stage_gate("outline", empty)
    assert not gate.can_proceed
    assert any("资料" in item for item in gate.blockers)


def test_generate_gate_requires_slides() -> None:
    gate = evaluate_stage_gate(
        "generate",
        _snapshot(slide_count=0, layout_ready_count=0, has_brief=True, document_count=1),
    )
    assert not gate.can_proceed
    ready = evaluate_stage_gate("generate", _snapshot(slide_count=3, layout_ready_count=1))
    assert ready.can_proceed


def test_stage_header_uses_stepper_not_plain_chain() -> None:
    flow_src = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "flow" / "__init__.py"
    )
    text = flow_src.read_text(encoding="utf-8")
    assert "render_flow_stepper" in text
    assert "制作流程：" not in text
    assert "主流程：" not in text
    assert "evaluate_stage_gate" in text
    assert "确认大纲并开始生成" in text


def test_generate_page_has_single_primary_studio_path() -> None:
    generate_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "flow"
        / "generate.py"
    )
    text = generate_src.read_text(encoding="utf-8")
    assert "前往工作室" not in text
    assert "前往交付与导出" not in text
    assert "进入工作室" in text or "render_stage_nav" in text
    assert 'get_app_page("deliver")' in text  # secondary under 更多


def test_deliver_page_hides_benchmark_and_has_readiness() -> None:
    deliver_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "flow"
        / "deliver.py"
    )
    settings_src = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "settings.py"
    )
    deliver_text = deliver_src.read_text(encoding="utf-8")
    settings_text = settings_src.read_text(encoding="utf-8")
    assert "交付准备度" in deliver_text
    assert "交付记录" in deliver_text
    assert "Benchmark" not in deliver_text or "开发者与验收" in deliver_text
    assert "render_benchmark_review_panel" not in deliver_text
    assert "开发者与验收" in settings_text
    assert "render_benchmark_review_panel" in settings_text


def test_studio_supports_canvas_maximize() -> None:
    studio_src = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "studio.py"
    )
    text = studio_src.read_text(encoding="utf-8")
    assert "画布最大化" in text
    assert "studio_show_nav" in text
    assert "studio_show_inspector" in text


def test_home_avoids_five_column_stage_grid() -> None:
    home_src = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "home.py"
    )
    text = home_src.read_text(encoding="utf-8")
    assert "st.columns(5)" not in text
    assert "st.columns(len(stages))" not in text

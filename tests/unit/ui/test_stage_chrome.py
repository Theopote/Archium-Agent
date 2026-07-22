"""Unit tests for product-flow stage chrome (stepper + gates)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from archium.ui.pages.flow import evaluate_stage_gate, stage_completion_status
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
        "outline_approved": False,
    }
    base.update(overrides)
    return ProjectProgressSnapshot(**base)  # type: ignore[arg-type]


def test_stage_completion_does_not_fake_done_from_navigation() -> None:
    empty = _snapshot(
        document_count=0,
        has_brief=False,
        outline_approved=False,
        presentation_id=None,
        slide_count=0,
        layout_ready_count=0,
        ready_for_export=False,
    )
    # Opening 工作室 must not mark earlier stages done.
    assert stage_completion_status("materials", empty) == "warn"
    assert stage_completion_status("outline", empty) == "todo"
    assert stage_completion_status("generate", empty) == "todo"
    assert stage_completion_status("edit", empty) == "blocked"
    assert stage_completion_status("deliver", empty) == "todo"

    ready = _snapshot(
        document_count=3,
        has_brief=True,
        outline_approved=True,
        slide_count=5,
        layout_ready_count=5,
        ready_for_export=True,
    )
    assert stage_completion_status("materials", ready) == "done"
    assert stage_completion_status("outline", ready) == "done"
    assert stage_completion_status("generate", ready) == "done"
    assert stage_completion_status("edit", ready) == "done"
    assert stage_completion_status("deliver", ready) == "done"


def test_outline_gate_allows_concept_draft_without_materials() -> None:
    empty = _snapshot(
        document_count=0,
        has_brief=False,
        presentation_id=None,
        slide_count=0,
        layout_ready_count=0,
    )
    gate = evaluate_stage_gate("outline", empty)
    assert not gate.can_proceed
    assert not any("资料" in item for item in gate.blockers)
    assert any("草稿" in item or "资料" in item for item in gate.warnings)
    assert any("大纲" in item or "汇报" in item for item in gate.blockers)


def test_materials_gate_allows_continue_as_draft() -> None:
    gate = evaluate_stage_gate(
        "materials",
        _snapshot(document_count=0, has_brief=False, presentation_id=None, slide_count=0),
    )
    assert gate.can_proceed
    assert any("草稿" in item or "资料" in item for item in gate.warnings)


def test_deliver_gate_blocks_concept_draft() -> None:
    gate = evaluate_stage_gate(
        "deliver",
        _snapshot(document_count=0, ready_for_export=True, slide_count=3, layout_ready_count=3),
    )
    assert not gate.can_proceed
    assert any("交付" in item or "资料" in item for item in gate.blockers)


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
    assert "准备度" in deliver_text
    assert "版本记录" in deliver_text
    assert "render_benchmark_review_panel" not in deliver_text
    assert "开发者与验收" in settings_text
    assert "render_benchmark_review_panel" in settings_text


def test_studio_supports_canvas_maximize() -> None:
    studio_src = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "studio.py"
    )
    text = studio_src.read_text(encoding="utf-8")
    assert "_render_view_controls" in text
    assert "画布专注" in text
    assert "恢复三栏" in text
    assert "studio_show_nav" in text
    assert "studio_show_inspector" in text


def test_home_other_projects_continue_into_project() -> None:
    home = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "home.py"
    ).read_text(encoding="utf-8")
    other_block = home.split("def _render_other_projects")[1].split("def render")[0]
    assert "_select_and_continue(snapshot)" in other_block
    assert 'key=f"home_open_{snapshot.project_id}"' in other_block
    assert "继续工作" in other_block
    assert "st.rerun()" not in other_block


def test_home_avoids_five_column_stage_grid() -> None:
    home_src = (
        Path(__file__).resolve().parents[3] / "archium" / "ui" / "pages" / "home.py"
    )
    text = home_src.read_text(encoding="utf-8")
    assert "st.columns(5)" not in text
    assert "st.columns(len(stages))" not in text
    assert "项目列表暂时无法加载" in text
    assert "_render_load_failed" in text


def test_deliver_readiness_shows_separate_metrics() -> None:
    deliver_src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "flow"
        / "deliver.py"
    )
    text = deliver_src.read_text(encoding="utf-8")
    assert "页面完成" in text
    assert 'metric("警告"' in text or 'metric("警告",' in text
    assert "待完成页" in text
    assert "DeliveryRecordService" in text

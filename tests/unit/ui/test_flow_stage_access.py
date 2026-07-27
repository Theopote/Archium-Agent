"""Unit tests for product-flow stage access advisories and captions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from archium.domain.enums import EvidenceAvailability, ProjectOriginMode
from archium.ui.pages.flow import evaluate_stage_access
from archium.ui.project_progress_card import ProjectProgressSnapshot
from archium.ui.workspace_mode_chrome import flow_stage_caption


def _snapshot(**overrides) -> ProjectProgressSnapshot:
    base = {
        "project_id": uuid4(),
        "project_name": "测试项目",
        "presentation_id": uuid4(),
        "presentation_title": "测试汇报",
        "presentation_type": "concept",
        "document_count": 0,
        "slide_count": 0,
        "layout_ready_count": 0,
        "has_brief": False,
        "ready_for_export": False,
        "updated_at": datetime.now(UTC),
        "outline_approved": False,
        "has_outline": False,
        "evidence_availability": EvidenceAvailability.MISSING,
    }
    base.update(overrides)
    return ProjectProgressSnapshot(**base)


def test_evaluate_stage_access_warns_on_genesis_shortcut_deliver() -> None:
    snapshot = _snapshot(slide_count=6, layout_ready_count=6, has_outline=True)
    warnings = evaluate_stage_access("deliver", snapshot)
    assert any("大纲尚未确认" in item for item in warnings)


def test_evaluate_stage_access_warns_generate_without_outline() -> None:
    snapshot = _snapshot()
    warnings = evaluate_stage_access("generate", snapshot)
    assert any("大纲" in item for item in warnings)


def test_flow_stage_caption_deliver_when_formal_ready() -> None:
    snapshot = _snapshot(
        document_count=2,
        slide_count=6,
        layout_ready_count=6,
        pptx_ready=True,
        pdf_ready=True,
        evidence_availability=EvidenceAvailability.AVAILABLE,
        export_blocker_count=0,
        ready_for_export=True,
        outline_approved=True,
        has_outline=True,
    )
    caption = flow_stage_caption(
        "deliver",
        snapshot.project_id,
        default="默认",
        snapshot=snapshot,
    )
    assert "正式导出" in caption


def test_flow_stage_caption_deliver_partial_with_docs_not_ready() -> None:
    snapshot = _snapshot(
        document_count=1,
        slide_count=6,
        layout_ready_count=6,
        pptx_ready=True,
        evidence_availability=EvidenceAvailability.AVAILABLE,
        export_blocker_count=1,
        ready_for_export=True,
        has_outline=True,
    )
    caption = flow_stage_caption(
        "deliver",
        snapshot.project_id,
        default="默认",
        snapshot=snapshot,
    )
    assert "阻塞" in caption


def test_narrative_summary_genesis_shortcut() -> None:
    snapshot = _snapshot(slide_count=6, has_outline=True)
    assert "Genesis" in snapshot.narrative_summary
    assert "大纲" in snapshot.narrative_summary


def test_narrative_summary_prefers_outline_over_formal_ready() -> None:
    snapshot = _snapshot(
        slide_count=6,
        has_outline=True,
        outline_approved=False,
        pptx_ready=True,
        pdf_ready=True,
        document_count=2,
        evidence_availability=EvidenceAvailability.AVAILABLE,
        export_blocker_count=0,
        ready_for_export=True,
        layout_ready_count=6,
    )
    assert "大纲待确认" in snapshot.narrative_summary
    assert snapshot.deliver_label == "草稿"
    assert snapshot.formal_delivery_ready  # evidence gate unchanged


def test_stage_order_for_redirect_hint() -> None:
    from archium.ui.pages.flow import _STAGE_ORDER

    assert _STAGE_ORDER.index("deliver") > _STAGE_ORDER.index("outline")

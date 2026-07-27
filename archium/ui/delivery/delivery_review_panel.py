"""Delivery Review — architect-facing pre-export checklist and quality score."""

from __future__ import annotations

import html
from dataclasses import dataclass

import streamlit as st

from archium.application.export_gate import resolve_export_verdict_safe
from archium.application.visual.visual_workflow_service import VisualWorkflowResult
from archium.domain.export_verdict import ExportVerdict, ExportVerdictStatus
from archium.ui.delivery.fidelity_report_panel import get_stored_manifest
from archium.ui.studio_service import StudioPresentationContext


@dataclass(frozen=True)
class DeliveryCheckItem:
    label: str
    passed: bool
    detail: str
    tone: str


def _deck_qa_report(context: StudioPresentationContext) -> dict | None:
    result = st.session_state.get("last_visual_workflow_result")
    if isinstance(result, VisualWorkflowResult) and isinstance(result.deck_qa_report, dict):
        return result.deck_qa_report
    snapshot_qa = context.snapshot.deck_qa_report
    return snapshot_qa if isinstance(snapshot_qa, dict) else None


def build_delivery_checklist(
    *,
    context: StudioPresentationContext,
    verdict: ExportVerdict,
) -> list[DeliveryCheckItem]:
    items: list[DeliveryCheckItem] = []
    slide_count = context.slide_count
    layout_ready = context.layout_ready_count
    preview_ready = context.preview_ready_count

    items.append(
        DeliveryCheckItem(
            label="页面版式",
            passed=slide_count > 0 and layout_ready >= slide_count,
            detail=f"{layout_ready}/{slide_count} 页已生成版式",
            tone="ok" if layout_ready >= slide_count and slide_count else "warn",
        )
    )
    items.append(
        DeliveryCheckItem(
            label="预览就绪",
            passed=slide_count > 0 and preview_ready >= slide_count,
            detail=f"{preview_ready}/{slide_count} 页有预览图",
            tone="ok" if preview_ready >= slide_count and slide_count else "info",
        )
    )
    items.append(
        DeliveryCheckItem(
            label="PPTX 可导出",
            passed=verdict.pptx_ready,
            detail="格式与版式满足导出条件" if verdict.pptx_ready else "尚有阻塞或未齐",
            tone="ok" if verdict.pptx_ready else "error",
        )
    )
    items.append(
        DeliveryCheckItem(
            label="PDF 可导出",
            passed=verdict.pdf_ready,
            detail="可生成 PDF" if verdict.pdf_ready else "需先完成 PPTX 或检查环境",
            tone="ok" if verdict.pdf_ready else "warn",
        )
    )

    manifest = get_stored_manifest()
    if manifest is not None:
        editable = not manifest.fallback_used
        items.append(
            DeliveryCheckItem(
                label="可编辑性",
                passed=editable,
                detail=manifest.summary_lines_zh()[0] if manifest.summary_lines_zh() else "已检查忠实度",
                tone="ok" if editable else "warn",
            )
        )
    else:
        items.append(
            DeliveryCheckItem(
                label="可编辑性",
                passed=verdict.pptx_ready,
                detail="导出后将生成忠实度报告",
                tone="info",
            )
        )

    deck_qa = _deck_qa_report(context)
    qa_ok = deck_qa is None or int(deck_qa.get("blocker_count") or 0) == 0
    items.append(
        DeliveryCheckItem(
            label="整套一致性",
            passed=qa_ok and verdict.deck_qa_blocker_count == 0,
            detail="Deck QA 无阻塞" if qa_ok else "存在需处理的 QA 项",
            tone="ok" if qa_ok else "warn",
        )
    )
    items.append(
        DeliveryCheckItem(
            label="证据与引用",
            passed=verdict.citation_gap_count == 0,
            detail="引用完整" if verdict.citation_gap_count == 0 else f"{verdict.citation_gap_count} 处缺口",
            tone="ok" if verdict.citation_gap_count == 0 else "warn",
        )
    )
    items.append(
        DeliveryCheckItem(
            label="视觉一致性",
            passed=len(verdict.critic_lines) == 0 and len(verdict.blockers) == 0,
            detail="无视觉批判阻塞" if not verdict.critic_lines else f"{len(verdict.critic_lines)} 条批判待阅",
            tone="ok" if not verdict.critic_lines else "info",
        )
    )
    return items


def estimate_delivery_quality_score(
    *,
    context: StudioPresentationContext,
    verdict: ExportVerdict,
    checklist: list[DeliveryCheckItem],
) -> int:
    if context.slide_count <= 0:
        return 0
    weights = 0.0
    total = 0.0
    layout_ratio = context.layout_ready_count / max(1, context.slide_count)
    preview_ratio = context.preview_ready_count / max(1, context.slide_count)
    weights += layout_ratio * 25
    total += 25
    weights += preview_ratio * 15
    total += 15
    if verdict.pptx_ready:
        weights += 20
    total += 20
    if verdict.pdf_ready:
        weights += 5
    total += 5
    passed = sum(1 for item in checklist if item.passed)
    weights += (passed / max(1, len(checklist))) * 35
    total += 35
    if verdict.status == ExportVerdictStatus.BLOCKED:
        weights *= 0.75
    deck_qa = _deck_qa_report(context)
    if isinstance(deck_qa, dict):
        score = deck_qa.get("total_score")
        if isinstance(score, (int, float)):
            weights = weights * 0.7 + (float(score) * 100 if score <= 1 else float(score)) * 0.3
    return max(0, min(100, int(round(weights))))


def render_delivery_review_panel(*, context: StudioPresentationContext) -> ExportVerdict:
    """Render delivery checklist and estimated quality before export actions."""
    deck_qa = _deck_qa_report(context)
    critique = st.session_state.get("last_presentation_critique")
    verdict = resolve_export_verdict_safe(
        project_id=context.project.id,
        presentation_id=context.presentation.id,
        deck_qa_report=deck_qa,
        presentation_critique=critique if isinstance(critique, dict) else None,
    )
    checklist = build_delivery_checklist(context=context, verdict=verdict)
    quality = estimate_delivery_quality_score(
        context=context,
        verdict=verdict,
        checklist=checklist,
    )

    st.markdown("#### 交付检查")
    cols = st.columns([1.2, 2.8])
    with cols[0]:
        st.metric("预计质量", f"{quality}/100")
        st.caption(verdict.partner_summary())
    with cols[1]:
        for item in checklist:
            mark = "✓" if item.passed else "○"
            tone_class = f"status-chip-{item.tone}"
            st.markdown(
                f'<div class="delivery-check-row">'
                f'<span class="status-chip {tone_class}">'
                f'<span class="status-chip-mark">{mark}</span>{item.label}</span>'
                f'<span class="delivery-check-detail">{html.escape(item.detail)}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

    if verdict.blockers:
        st.warning("阻塞项：" + "；".join(verdict.blockers[:3]))
    elif verdict.warnings:
        st.info("建议复核：" + "；".join(verdict.warnings[:3]))

    if context.layout_ready_count < context.slide_count or verdict.blockers:
        from archium.ui.app_navigation import get_app_page

        st.page_link(get_app_page("edit"), label="回工作室处理问题页 →")

    return verdict

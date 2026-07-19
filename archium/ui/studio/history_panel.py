"""Bottom status and history panel for Presentation Studio."""

from __future__ import annotations

import streamlit as st

from archium.infrastructure.database.session import get_session
from archium.ui.label_map import STATUS_LABELS, entity_label
from archium.ui.studio.deck_repair_panel import render_deck_repair_panel
from archium.ui.studio.revision_restore_panel import (
    render_content_revision_panel,
    render_visual_revision_panel,
)
from archium.ui.slide_history_panel import render_slide_history_panel
from archium.ui.studio_service import (
    StudioPresentationContext,
    count_visual_revisions,
    studio_readiness_label,
)
from archium.ui.visual_service import SlideVisualSnapshot


def render_history_panel(
    *,
    context: StudioPresentationContext,
    advanced: bool,
    slide_snapshot: SlideVisualSnapshot | None = None,
) -> None:
    """Render workflow status, deck QA summary, and revision history."""
    st.markdown("**状态与版本**")
    readiness = studio_readiness_label(context)
    cols = st.columns(4)
    cols[0].metric("页面数", context.slide_count)
    cols[1].metric("版式就绪", f"{context.layout_ready_count}/{context.slide_count or 0}")
    cols[2].metric("导出状态", STATUS_LABELS.get(readiness, readiness))
    deck = context.snapshot.deck_qa_report
    deck_score = deck.get("total_score") if isinstance(deck, dict) else None
    cols[3].metric(
        entity_label("Deck QA", advanced=advanced),
        f"{deck_score:.2f}" if isinstance(deck_score, (int, float)) else "—",
    )

    if isinstance(deck, dict) and deck.get("findings"):
        with st.expander(f"{entity_label('Deck QA', advanced=advanced)} · 发现", expanded=False):
            for item in list(deck.get("findings") or [])[:8]:
                st.write(
                    f"- {item.get('severity')} · {item.get('message')}"
                )
        render_deck_repair_panel(context=context)

    result = st.session_state.get("last_visual_workflow_result")
    if result is not None:
        st.caption(
            f"最近编排：{result.workflow_run.status.value} · "
            f"意图 {len(result.visual_intent_ids)} · 版式 {len(result.layout_plan_ids)}"
        )

    if slide_snapshot is not None:
        with get_session() as session:
            revision_count = count_visual_revisions(session, slide_snapshot.slide.id)
        st.caption(f"当前页视觉修订：{revision_count} 条（可逐步撤销或恢复到任意版本）")
        render_visual_revision_panel(slide_snapshot=slide_snapshot)
        render_content_revision_panel(slide_snapshot=slide_snapshot)

    with st.expander("页面内容修订历史", expanded=False):
        slides = [item.slide for item in context.snapshot.slides]
        render_slide_history_panel(
            presentation_id=context.presentation.id,
            slides=slides,
        )

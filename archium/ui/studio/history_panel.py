"""Bottom status and history panel for Presentation Studio."""

from __future__ import annotations

import streamlit as st

from archium.ui.label_map import STATUS_LABELS, entity_label
from archium.ui.slide_history_panel import render_slide_history_panel
from archium.ui.studio_service import StudioPresentationContext, studio_readiness_label


def render_history_panel(*, context: StudioPresentationContext, advanced: bool) -> None:
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

    result = st.session_state.get("last_visual_workflow_result")
    if result is not None:
        st.caption(
            f"最近编排：{result.workflow_run.status.value} · "
            f"意图 {len(result.visual_intent_ids)} · 版式 {len(result.layout_plan_ids)}"
        )

    with st.expander("页面内容修订历史", expanded=False):
        slides = [item.slide for item in context.snapshot.slides]
        render_slide_history_panel(
            presentation_id=context.presentation.id,
            slides=slides,
        )

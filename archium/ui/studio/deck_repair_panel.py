"""Actionable deck-level repair suggestions in Presentation Studio."""

from __future__ import annotations

import streamlit as st

from archium.application.visual.deck_repair_service import DeckRepairService
from archium.domain.visual.deck_repair import DeckRepairSuggestion
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.studio_service import StudioPresentationContext, apply_deck_repair_suggestion


def render_deck_repair_panel(*, context: StudioPresentationContext) -> None:
    """Render repair actions derived from the latest Deck QA report."""
    deck = context.snapshot.deck_qa_report
    if not isinstance(deck, dict) or not deck.get("findings"):
        return

    suggestions = DeckRepairService().suggest_from_report(deck)
    if not suggestions:
        return

    st.markdown("**整套修复建议**")
    st.caption("基于整套一致性检查，可一键跳转到对应页面并应用修改。")

    slide_index_by_id = {
        str(item.slide.id): index for index, item in enumerate(context.snapshot.slides)
    }

    for index, suggestion in enumerate(suggestions[:6]):
        cols = st.columns([3, 1])
        with cols[0]:
            slide_no = slide_index_by_id.get(str(suggestion.slide_id))
            page_label = f"P{slide_no + 1}" if slide_no is not None else "页面"
            st.write(f"{page_label} · {suggestion.label}")
            st.caption(suggestion.reason)
        with cols[1]:
            if st.button(
                "应用",
                key=f"studio_deck_repair_{suggestion.rule_code}_{index}",
                use_container_width=True,
            ):
                _apply_suggestion(suggestion, slide_index_by_id.get(str(suggestion.slide_id)))


def _apply_suggestion(
    suggestion: DeckRepairSuggestion,
    slide_index: int | None,
) -> None:
    try:
        with st.spinner("正在应用整套修复建议…"), get_session() as session:
            apply_deck_repair_suggestion(session, suggestion)
        if slide_index is not None:
            st.session_state.studio_selected_slide_index = slide_index
        st.success("已应用修复建议。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))

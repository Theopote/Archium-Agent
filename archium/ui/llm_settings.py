"""Streamlit helpers for resolving effective LLM settings."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.llm_settings_resolver import get_effective_settings
from archium.config.settings import Settings


def session_api_key() -> str | None:
    value = st.session_state.get("llm_session_api_key")
    return value if isinstance(value, str) and value else None


def _selected_project_id() -> UUID | None:
    raw = st.session_state.get("selected_project_id")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None


def get_ui_effective_settings(*, project_id: UUID | None = None) -> Settings:
    """Resolve LLM settings using the current Streamlit session state."""
    return get_effective_settings(
        session_api_key=session_api_key(),
        project_id=project_id if project_id is not None else _selected_project_id(),
    )


def render_project_llm_tier_selector(
    project_id: UUID,
    *,
    key_prefix: str = "llm_tier",
) -> None:
    """Compact partner control: 快速概念 vs 高质量竞赛."""
    from archium.application.project_llm_tier_service import (
        ProjectLLMTierService,
        tier_label,
    )
    from archium.domain.project_llm_tier import ProjectLLMTier
    from archium.infrastructure.database.session import get_session

    with get_session() as session:
        service = ProjectLLMTierService(session)
        current = service.get_tier(project_id)
    options = [ProjectLLMTier.FAST, ProjectLLMTier.QUALITY]
    index = options.index(current) if current in options else 1
    choice = st.selectbox(
        "模型档位",
        options=options,
        index=index,
        format_func=tier_label,
        key=f"{key_prefix}_{project_id}",
        help="快速概念用轻量模型；竞赛 / 正式汇报可用高质量模型。",
    )
    if choice != current:
        with get_session() as session:
            ProjectLLMTierService(session).set_tier(project_id, choice)
        st.caption(f"已切换为「{tier_label(choice)}」。")
        st.rerun()

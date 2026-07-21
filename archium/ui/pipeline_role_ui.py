"""Streamlit helpers for PipelineRole labels (UI only)."""

from __future__ import annotations

import streamlit as st

from archium.domain.enums import PipelineRole
from archium.domain.pipeline_role_mapping import pipeline_role_label


def role_caption(*roles: PipelineRole) -> None:
    """Show a one-line logical-role hint above an action."""
    if not roles:
        return
    text = " · ".join(pipeline_role_label(role) for role in roles)
    st.caption(f"逻辑角色：{text}")


def role_button_label(label: str, *roles: PipelineRole) -> str:
    """Append role tag to button text for quick scan."""
    if not roles:
        return label
    tags = "/".join(role.value for role in roles)
    return f"{label} 〔{tags}〕"

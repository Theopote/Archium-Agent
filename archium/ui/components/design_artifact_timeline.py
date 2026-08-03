"""DesignArtifact timeline chrome for materials / deliver (Topic 07 L3)."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.unit_of_work import unit_of_work


def render_design_artifact_timeline(
    project_id: UUID,
    *,
    title: str = "设计产物（示意）",
    limit: int = 12,
) -> None:
    """Show Vision DesignArtifact stamps; never claims evidence."""
    try:
        from archium.application.design_artifact_catalog import list_design_artifacts

        with unit_of_work() as uow:
            rows = list_design_artifacts(uow, project_id, limit=limit)
    except Exception:
        return
    if not rows:
        return
    with st.expander(title, expanded=False):
        st.caption("AI 示意出图身份（DesignArtifact）；不可作场地证据。")
        for row in rows:
            st.markdown(f"- {row.display_line()}")

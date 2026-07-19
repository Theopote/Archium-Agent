"""Streamlit UI for Brief and Storyline revision history."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import streamlit as st

from archium.application.artifact_history_service import (
    BriefHistoryService,
    StorylineHistoryService,
)
from archium.application.slide_diff import change_source_label
from archium.domain.revision import EntityRevision
from archium.infrastructure.database.session import get_session
from archium.ui.label_map import revision_history_label


def _render_revision_table(
    revisions: list[EntityRevision],
    *,
    label_fn: Callable[[EntityRevision], str],
) -> None:
    if not revisions:
        st.caption("保存或重新生成后，可在此查看修订历史。")
        return

    rows = [
        {
            "修订号": revision.revision_number,
            "版本链": str(revision.lineage_id)[:8],
            "来源": change_source_label(revision.change_source),
            "摘要": label_fn(revision),
            "时间": revision.created_at.strftime("%Y-%m-%d %H:%M"),
            "备注": revision.note or "",
        }
        for revision in revisions[:20]
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_brief_history_panel(*, brief_id: UUID) -> None:
    with st.expander(revision_history_label("PresentationBrief"), expanded=False):
        with get_session() as session:
            history = BriefHistoryService(session)
            revisions = history.list_revisions(brief_id)
        _render_revision_table(
            revisions,
            label_fn=BriefHistoryService.revision_label,
        )


def render_storyline_history_panel(*, storyline_id: UUID) -> None:
    with st.expander(revision_history_label("Storyline"), expanded=False):
        with get_session() as session:
            history = StorylineHistoryService(session)
            revisions = history.list_revisions(storyline_id)
        _render_revision_table(
            revisions,
            label_fn=StorylineHistoryService.revision_label,
        )

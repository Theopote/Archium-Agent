"""Streamlit UI for SlideSpec revision history and diff."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.slide_diff import change_source_label
from archium.application.slide_history_service import SlideHistoryService
from archium.domain.revision import SlideLineageOption
from archium.domain.slide import SlideSpec
from archium.domain.slide_history import SlideFieldChange, SlideRevision
from archium.infrastructure.database.session import get_session
from archium.ui.label_map import entity_label


def _revision_option_label(revision: SlideRevision) -> str:
    title = str(revision.snapshot.get("title", ""))
    order = revision.snapshot.get("order", "?")
    return (
        f"#{revision.revision_number} · p{order} · "
        f"{change_source_label(revision.change_source)} · {title}"
    )


def _render_diff_result(
    *,
    before_label: str,
    after_label: str,
    changes: list[SlideFieldChange],
) -> None:
    if not changes:
        st.caption("两次修订之间没有字段差异。")
        return

    st.caption(f"对比：**{before_label}** → **{after_label}**")
    rows = [
        {
            "字段": change.label,
            "修改前": change.before[:200] + ("…" if len(change.before) > 200 else ""),
            "修改后": change.after[:200] + ("…" if len(change.after) > 200 else ""),
        }
        for change in changes
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    for change in changes:
        if change.unified_diff:
            with st.expander(f"Diff · {change.label}", expanded=False):
                st.code(change.unified_diff, language="diff")


def render_slide_history_panel(*, presentation_id: UUID, slides: list[SlideSpec]) -> None:
    """Render revision timeline and diff tools for SlideSpec."""
    with get_session() as session:
        history = SlideHistoryService(session)
        revisions = history.list_presentation_revisions(presentation_id)
        lineage_options = history.list_lineage_options(presentation_id, slides)

    if not revisions:
        st.caption(
            f"保存或重新生成{entity_label('SlideSpec')}后，可在此查看页面修订历史。"
        )
        return

    st.markdown("**修订历史**")
    preview_rows = [
        {
            "修订号": revision.revision_number,
            "版本链": str(revision.lineage_id)[:8],
            "页面顺序": revision.snapshot.get("order", "-"),
            "标题": revision.snapshot.get("title", ""),
            "来源": change_source_label(revision.change_source),
            "时间": revision.created_at.strftime("%Y-%m-%d %H:%M"),
            "备注": revision.note or "",
        }
        for revision in revisions[:30]
    ]
    st.dataframe(preview_rows, use_container_width=True, hide_index=True)

    if not lineage_options:
        return

    option_map = {str(option.lineage_id): option for option in lineage_options}
    selected_lineage_id = st.selectbox(
        "选择页面版本链",
        options=list(option_map.keys()),
        format_func=lambda value: option_map[value].label,
        key=f"history_lineage_{presentation_id}",
    )
    selected_option: SlideLineageOption = option_map[selected_lineage_id]
    lineage_id = UUID(selected_lineage_id)

    with get_session() as session:
        history = SlideHistoryService(session)
        slide_revisions = history.list_revisions_by_lineage(lineage_id)
        current_slide = next(
            (slide for slide in slides if slide.lineage_id == lineage_id),
            None,
        )

    if selected_option.status != "current":
        st.info(
            f"该版本链状态：**{selected_option.label.split(' · ', 1)[0]}**。"
            " 可查看重新生成前后的完整修订记录。"
        )

    if len(slide_revisions) < 1:
        st.caption("该版本链尚无修订记录。")
        return

    revision_labels = {
        str(revision.id): _revision_option_label(revision) for revision in slide_revisions
    }

    if current_slide is not None:
        restore_id = st.selectbox(
            "恢复到历史版本",
            options=list(revision_labels.keys()),
            format_func=lambda value: revision_labels[value],
            key=f"history_restore_{presentation_id}",
        )
        if st.button(
            "恢复到此版本",
            key=f"history_restore_btn_{presentation_id}",
            use_container_width=True,
        ):
            with get_session() as session:
                SlideHistoryService(session).restore_at_revision(UUID(restore_id))
                session.commit()
            st.success("页面内容已恢复到所选版本。")
            st.rerun()

    compare_mode = st.radio(
        "对比方式",
        options=["与上一版对比", "与当前版本对比", "选择两个版本"],
        horizontal=True,
        key=f"history_mode_{presentation_id}",
    )

    with get_session() as session:
        history = SlideHistoryService(session)
        if compare_mode == "与上一版对比":
            if len(slide_revisions) < 2:
                st.caption("至少需要两次修订才能对比。")
                return
            diff = history.diff_with_previous(slide_revisions[0].id)
            if diff is None:
                st.caption("无法找到上一版修订。")
                return
            _render_diff_result(
                before_label=diff.before_label,
                after_label=diff.after_label,
                changes=diff.changes,
            )
            return

        if compare_mode == "与当前版本对比":
            if current_slide is None:
                st.caption("当前实体已删除；请在下方选择两个历史版本对比。")
                return
            selected_revision_id = st.selectbox(
                "选择历史版本",
                options=list(revision_labels.keys()),
                format_func=lambda value: revision_labels[value],
                key=f"history_revision_current_{presentation_id}",
            )
            diff = history.diff_revision_to_current(UUID(selected_revision_id), current_slide)
            _render_diff_result(
                before_label=diff.before_label,
                after_label=diff.after_label,
                changes=diff.changes,
            )
            return

        left_id = st.selectbox(
            "较早版本",
            options=list(revision_labels.keys()),
            format_func=lambda value: revision_labels[value],
            key=f"history_left_{presentation_id}",
        )
        right_options = [key for key in revision_labels if key != left_id]
        if not right_options:
            st.caption("需要至少两个不同版本。")
            return
        right_id = st.selectbox(
            "较晚版本",
            options=right_options,
            format_func=lambda value: revision_labels[value],
            key=f"history_right_{presentation_id}",
        )
        diff = history.diff_revisions(UUID(left_id), UUID(right_id))
        _render_diff_result(
            before_label=diff.before_label,
            after_label=diff.after_label,
            changes=diff.changes,
        )

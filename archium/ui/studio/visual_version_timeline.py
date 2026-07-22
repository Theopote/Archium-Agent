"""RenderScene version timeline for Presentation Studio."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.scene_revision_timeline_service import (
    SceneRevisionTimelineService,
    timeline_source_label,
)
from archium.config.settings import get_settings
from archium.domain.scene_revision_summary import SceneRevisionSummary
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.visual_service import SlideVisualSnapshot


def _compare_session_key(slide_id: UUID) -> str:
    return f"studio_scene_timeline_compare_{slide_id}"


def _selected_compare_ids(slide_id: UUID) -> tuple[UUID | None, UUID | None]:
    stored = st.session_state.get(_compare_session_key(slide_id))
    if not isinstance(stored, dict):
        return None, None
    left = stored.get("left")
    right = stored.get("right")
    return (
        UUID(str(left)) if left else None,
        UUID(str(right)) if right else None,
    )


def _set_compare_slot(slide_id: UUID, slot: str, revision_id: UUID) -> None:
    key = _compare_session_key(slide_id)
    current = st.session_state.get(key)
    if not isinstance(current, dict):
        current = {"left": None, "right": None}
    current[slot] = str(revision_id)
    st.session_state[key] = current


def _summary_row_label(item: SceneRevisionSummary) -> str:
    version_label = f"v{item.version}" if item.version > 0 else "提案"
    if item.is_current:
        version_label = f"{version_label} 当前正式版本"
    source = timeline_source_label(item.source)
    if item.accepted:
        status = "已接受"
    else:
        status = "已拒绝"
    created = item.created_at.strftime("%m-%d %H:%M")
    return f"{version_label} · {source} · {status} · {created}"


def render_scene_version_timeline_panel(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
    presentation_id: UUID,
) -> None:
    """Render RenderScene revision timeline with thumbnails, compare, and restore."""
    if slide_snapshot is None:
        return

    slide = slide_snapshot.slide
    settings = get_settings()
    with get_session() as session:
        service = SceneRevisionTimelineService(session, settings=settings)
        summaries = service.list_summaries(slide)

    if not summaries:
        st.caption("当前页尚无 RenderScene 版本记录。")
        return

    with st.expander("版本时间线", expanded=True):
        st.caption(
            "基于 RenderScene 的视觉版本轨。恢复旧版本会创建新 Revision，"
            "不会覆盖或删除既有历史。"
        )
        compare_left, compare_right = _selected_compare_ids(slide.id)
        if compare_left and compare_right:
            _render_compare_view(
                service_cls=SceneRevisionTimelineService,
                presentation_id=presentation_id,
                left_revision_id=compare_left,
                right_revision_id=compare_right,
                settings=settings,
            )

        for item in summaries[:12]:
            _render_timeline_row(
                item=item,
                slide_id=slide.id,
                presentation_id=presentation_id,
                settings=settings,
                can_restore=item.accepted and not item.is_current,
            )


def _render_timeline_row(
    *,
    item: SceneRevisionSummary,
    slide_id: UUID,
    presentation_id: UUID,
    settings,
    can_restore: bool,
) -> None:
    thumb_col, meta_col, action_col = st.columns([1.2, 3, 1.3])
    with thumb_col:
        with get_session() as session:
            service = SceneRevisionTimelineService(session, settings=settings)
            preview_path = service.preview_cache_path(presentation_id, item.revision_id)
        if preview_path is not None and preview_path.is_file():
            st.image(str(preview_path), use_container_width=True)
        else:
            st.caption("无缩略图")
            if item.accepted and st.button(
                "生成",
                key=f"studio_scene_thumb_{slide_id}_{item.revision_id}",
                use_container_width=True,
            ):
                with get_session() as session:
                    service = SceneRevisionTimelineService(session, settings=settings)
                    service.render_preview(presentation_id, item.revision_id)
                st.rerun()

    with meta_col:
        st.markdown(f"**{_summary_row_label(item)}**")
        st.write(item.summary)
        st.caption(
            f"QA：{item.qa_status} · 命令 {len(item.command_ids)} 条 · "
            f"ID {str(item.revision_id)[:8]}…"
            + (
                f" · 父版本 {str(item.parent_revision_id)[:8]}…"
                if item.parent_revision_id
                else ""
            )
        )

    with action_col:
        if can_restore and st.button(
            "恢复",
            key=f"studio_scene_restore_{slide_id}_{item.revision_id}",
            use_container_width=True,
        ):
            _restore_scene_revision(slide_id=slide_id, revision_id=item.revision_id)
        if item.accepted and st.button(
            "对比 A",
            key=f"studio_scene_compare_a_{slide_id}_{item.revision_id}",
            use_container_width=True,
        ):
            _set_compare_slot(slide_id, "left", item.revision_id)
            st.rerun()
        if item.accepted and st.button(
            "对比 B",
            key=f"studio_scene_compare_b_{slide_id}_{item.revision_id}",
            use_container_width=True,
        ):
            _set_compare_slot(slide_id, "right", item.revision_id)
            st.rerun()


def _render_compare_view(
    *,
    service_cls: type[SceneRevisionTimelineService],
    presentation_id: UUID,
    left_revision_id: UUID,
    right_revision_id: UUID,
    settings,
) -> None:
    st.markdown("**版本对比**")
    try:
        with get_session() as session:
            service = service_cls(session, settings=settings)
            left_scene, right_scene = service.compare_revisions(
                left_revision_id,
                right_revision_id,
            )
            left_path = service.render_preview(presentation_id, left_revision_id)
            right_path = service.render_preview(presentation_id, right_revision_id)
        left_col, right_col = st.columns(2)
        with left_col:
            st.caption(f"A · {str(left_revision_id)[:8]}… · {len(left_scene.nodes)} 节点")
            if left_path is not None and left_path.is_file():
                st.image(str(left_path), use_container_width=True)
        with right_col:
            st.caption(f"B · {str(right_revision_id)[:8]}… · {len(right_scene.nodes)} 节点")
            if right_path is not None and right_path.is_file():
                st.image(str(right_path), use_container_width=True)
    except WorkflowError as exc:
        st.error(format_user_error(exc))


def _restore_scene_revision(*, slide_id: UUID, revision_id: UUID) -> None:
    from archium.infrastructure.database.repositories import PresentationRepository

    try:
        settings = get_settings()
        with st.spinner("正在恢复 Scene 版本…"), get_session() as session:
            presentations = PresentationRepository(session)
            slide = presentations.get_slide(slide_id)
            if slide is None:
                raise WorkflowError("页面不存在。")
            result = SceneRevisionTimelineService(session, settings=settings).restore_revision(
                slide=slide,
                source_revision_id=revision_id,
            )
        st.success(
            f"已基于 v{result.source_version} 创建新版本 v{result.summary.version}；"
            "历史版本仍保留。"
        )
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))

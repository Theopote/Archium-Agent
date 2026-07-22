"""Sidebar current-project progress card (user-facing, not module diagnostics)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import streamlit as st

from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page


@dataclass(frozen=True)
class ProjectProgressSnapshot:
    project_id: UUID
    project_name: str
    presentation_id: UUID | None
    presentation_title: str | None
    document_count: int
    slide_count: int
    layout_ready_count: int
    has_brief: bool
    ready_for_export: bool
    updated_at: datetime

    @property
    def pending_count(self) -> int:
        return max(0, self.slide_count - self.layout_ready_count)

    @property
    def materials_label(self) -> str:
        return "已整理" if self.document_count > 0 else "未上传"

    @property
    def outline_label(self) -> str:
        if self.has_brief:
            return "已确认"
        if self.presentation_id is not None:
            return "进行中"
        return "未开始"

    @property
    def generate_label(self) -> str:
        if self.slide_count <= 0:
            return "未开始"
        return f"{self.layout_ready_count}/{self.slide_count} 页"

    @property
    def deliver_label(self) -> str:
        if self.ready_for_export:
            return "可交付"
        if self.slide_count <= 0:
            return "未开始"
        return "未通过"


def _format_relative_time(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    seconds = max(0, int((now - moment).total_seconds()))
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前"
    if seconds < 86400:
        return f"{seconds // 3600} 小时前"
    if seconds < 86400 * 7:
        return f"{seconds // 86400} 天前"
    return moment.astimezone().strftime("%Y-%m-%d")


def load_project_progress_snapshot() -> ProjectProgressSnapshot | None:
    """Load a lightweight progress snapshot for the sidebar."""
    from archium.infrastructure.database.repositories import (
        DocumentRepository,
        PresentationRepository,
        ProjectRepository,
    )
    from archium.ui.visual_service import presentation_has_visual_layout

    raw_project = st.session_state.get("selected_project_id")
    raw_presentation = st.session_state.get("selected_presentation_id")

    with get_session() as session:
        projects = ProjectRepository(session).list_all()
        if not projects:
            return None

        project = None
        if raw_project is not None:
            try:
                project = ProjectRepository(session).get_by_id(UUID(str(raw_project)))
            except ValueError:
                project = None
        if project is None:
            project = projects[0]

        documents = DocumentRepository(session).list_by_project(project.id)
        presentations = PresentationRepository(session).list_by_project(project.id)

        presentation = None
        if raw_presentation is not None and presentations:
            try:
                wanted = UUID(str(raw_presentation))
            except ValueError:
                wanted = None
            if wanted is not None:
                presentation = next((item for item in presentations if item.id == wanted), None)
        if presentation is None and presentations:
            presentation = presentations[0]

        slide_count = 0
        layout_ready_count = 0
        has_brief = False
        ready_for_export = False
        updated_at = project.updated_at

        if presentation is not None:
            slides = PresentationRepository(session).list_slides(presentation.id)
            slide_count = len(slides)
            layout_ready_count = sum(1 for slide in slides if slide.layout_plan_id is not None)
            briefs = PresentationRepository(session).list_briefs(presentation.id)
            has_brief = len(briefs) > 0
            ready_for_export = presentation_has_visual_layout(session, presentation.id)
            updated_at = max(project.updated_at, presentation.updated_at)

        # Keep sidebar selection aligned with the card we display.
        st.session_state.selected_project_id = str(project.id)
        if presentation is not None:
            st.session_state.selected_presentation_id = str(presentation.id)

        return ProjectProgressSnapshot(
            project_id=project.id,
            project_name=project.name,
            presentation_id=presentation.id if presentation is not None else None,
            presentation_title=presentation.title if presentation is not None else None,
            document_count=len(documents),
            slide_count=slide_count,
            layout_ready_count=layout_ready_count,
            has_brief=has_brief,
            ready_for_export=ready_for_export,
            updated_at=updated_at,
        )


def render_project_progress_card() -> None:
    """User-facing current project / progress summary for the sidebar."""
    st.markdown('<div class="section-label">当前项目</div>', unsafe_allow_html=True)
    try:
        snapshot = load_project_progress_snapshot()
    except Exception:
        st.caption("进度暂不可用。可到「项目」选择或创建项目。")
        st.page_link(get_app_page("project-management"), label="打开项目", icon="📁")
        return

    if snapshot is None:
        st.caption("还没有项目。")
        st.page_link(get_app_page("project-management"), label="创建项目", icon="📁")
        return

    st.markdown(f"**{snapshot.project_name}**")
    meta_bits = []
    if snapshot.presentation_title:
        meta_bits.append(snapshot.presentation_title)
    if snapshot.slide_count > 0:
        meta_bits.append(f"{snapshot.slide_count} 页")
    meta_bits.append(f"最近编辑 {_format_relative_time(snapshot.updated_at)}")
    st.caption(" · ".join(meta_bits))

    st.markdown('<div class="section-label">当前进度</div>', unsafe_allow_html=True)
    st.caption(f"资料：{snapshot.materials_label}")
    st.caption(f"大纲：{snapshot.outline_label}")
    st.caption(f"生成：{snapshot.generate_label}")
    st.caption(f"待处理：{snapshot.pending_count} 页")
    st.caption(f"交付：{snapshot.deliver_label}")

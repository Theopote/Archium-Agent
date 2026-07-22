"""Sidebar / home project progress snapshots (user-facing)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import streamlit as st

from archium.domain.enums import EvidenceAvailability
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page

_PRESENTATION_TYPE_LABELS = {
    "concept": "概念汇报",
    "schematic": "方案汇报",
    "design_development": "深化汇报",
    "client_review": "甲方汇报",
    "competition": "竞赛汇报",
    "internal": "内部汇报",
    "other": "汇报",
}


@dataclass(frozen=True)
class ProjectProgressSnapshot:
    project_id: UUID
    project_name: str
    presentation_id: UUID | None
    presentation_title: str | None
    presentation_type: str | None
    document_count: int
    slide_count: int
    layout_ready_count: int
    has_brief: bool
    ready_for_export: bool
    updated_at: datetime
    outline_approved: bool = False
    has_outline: bool = False
    outline_changes_pending: bool = False
    evidence_availability: EvidenceAvailability = EvidenceAvailability.MISSING
    export_blocker_count: int = 0
    pptx_ready: bool = False
    pdf_ready: bool = False

    @property
    def pending_count(self) -> int:
        return max(0, self.slide_count - self.layout_ready_count)

    @property
    def draft_export_ready(self) -> bool:
        """Layout is complete enough to draft-export (may still lack materials)."""
        return self.pptx_ready or self.ready_for_export

    @property
    def formal_delivery_ready(self) -> bool:
        """Ready for formal delivery — layout + verified materials + no blockers."""
        return (
            self.pptx_ready
            and self.pdf_ready
            and self.evidence_availability == EvidenceAvailability.AVAILABLE
            and self.document_count > 0
            and self.export_blocker_count <= 0
        )

    @property
    def materials_label(self) -> str:
        if self.evidence_availability == EvidenceAvailability.UNKNOWN:
            return "状态未知"
        return "已整理" if self.document_count > 0 else "未上传"

    @property
    def outline_label(self) -> str:
        if self.outline_approved:
            return "已确认"
        if self.outline_changes_pending:
            return "待重新确认"
        if self.has_outline:
            return "待确认"
        if self.has_brief:
            return "Brief 已有"
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
        if self.formal_delivery_ready:
            return "可交付"
        if self.draft_export_ready:
            if self.evidence_availability == EvidenceAvailability.MISSING:
                return "草稿"
            if self.evidence_availability == EvidenceAvailability.UNKNOWN:
                return "待验证"
            if self.export_blocker_count > 0:
                return "有阻塞"
            return "未通过"
        if self.slide_count <= 0:
            return "未开始"
        return "未通过"

    @property
    def presentation_type_label(self) -> str:
        if self.presentation_type is None:
            return "尚未创建汇报"
        return _PRESENTATION_TYPE_LABELS.get(self.presentation_type, "汇报")

    @property
    def current_stage_id(self) -> str:
        """Best next product-flow stage for「继续工作」."""
        if (
            self.evidence_availability == EvidenceAvailability.UNKNOWN
            or self.document_count <= 0
        ):
            return "materials"
        if not self.outline_approved:
            return "outline"
        if self.slide_count <= 0 or self.pending_count > 0:
            return "generate"
        if not self.ready_for_export:
            return "edit"
        return "deliver"
    @property
    def current_stage_label(self) -> str:
        labels = {
            "materials": "资料",
            "outline": "大纲",
            "generate": "生成",
            "edit": "工作室",
            "deliver": "交付",
        }
        return labels.get(self.current_stage_id, "资料")

    @property
    def completion_label(self) -> str:
        if self.slide_count <= 0:
            return "尚无页面"
        return f"{self.layout_ready_count}/{self.slide_count} 页完成"


@dataclass(frozen=True)
class CockpitTaskSummary:
    missing_asset_pages: int = 0
    drawing_qa_failed_pages: int = 0
    pending_proposals: int = 0
    pending_layout_pages: int = 0
    other_attention_pages: int = 0
    lines: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_tasks(self) -> bool:
        return bool(self.lines)


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


def _snapshot_for_project(
    session: object,
    project: object,
    *,
    preferred_presentation_id: UUID | None = None,
) -> ProjectProgressSnapshot:
    from archium.application.evidence_readiness_service import (
        ProjectEvidenceStatus,
        resolve_delivery_readiness,
        resolve_project_evidence,
    )
    from archium.domain.enums import ApprovalStatus
    from archium.infrastructure.database.repositories import PresentationRepository
    from archium.ui.visual_service import presentation_has_visual_layout

    try:
        evidence = resolve_project_evidence(session, project.id)
    except Exception:
        from archium.domain.enums import EvidenceAvailability as _EvidenceAvailability

        evidence = ProjectEvidenceStatus(
            availability=_EvidenceAvailability.UNKNOWN,
            document_count=0,
        )

    presentations = PresentationRepository(session).list_by_project(project.id)

    presentation = None
    if preferred_presentation_id is not None and presentations:
        presentation = next(
            (item for item in presentations if item.id == preferred_presentation_id),
            None,
        )
    if presentation is None and presentations:
        presentation = max(presentations, key=lambda item: item.updated_at)

    slide_count = 0
    layout_ready_count = 0
    has_brief = False
    has_outline = False
    outline_approved = False
    outline_changes_pending = False
    ready_for_export = False
    pptx_ready = False
    pdf_ready = False
    export_blocker_count = 0
    presentation_type: str | None = None
    updated_at = project.updated_at

    if presentation is not None:
        slides = PresentationRepository(session).list_slides(presentation.id)
        slide_count = len(slides)
        layout_ready_count = sum(1 for slide in slides if slide.layout_plan_id is not None)
        briefs = PresentationRepository(session).list_briefs(presentation.id)
        has_brief = len(briefs) > 0
        if briefs:
            presentation_type = briefs[0].presentation_type.value
        outline = None
        if presentation.current_outline_id is not None:
            outline = PresentationRepository(session).get_outline(presentation.current_outline_id)
        if outline is None:
            outlines = PresentationRepository(session).list_outlines(presentation.id)
            outline = outlines[0] if outlines else None
        if outline is not None:
            has_outline = True
            outline_approved = outline.approval_status == ApprovalStatus.APPROVED
            outline_changes_pending = (
                outline.approval_status == ApprovalStatus.CHANGES_PENDING
            )
        ready_for_export = presentation_has_visual_layout(session, presentation.id)
        readiness = resolve_delivery_readiness(
            session,
            project_id=project.id,
            presentation_id=presentation.id,
        )
        pptx_ready = readiness.pptx_ready
        pdf_ready = readiness.pdf_ready
        export_blocker_count = readiness.export_blocker_count
        updated_at = max(project.updated_at, presentation.updated_at)

    return ProjectProgressSnapshot(
        project_id=project.id,
        project_name=project.name,
        presentation_id=presentation.id if presentation is not None else None,
        presentation_title=presentation.title if presentation is not None else None,
        presentation_type=presentation_type,
        document_count=evidence.document_count,
        slide_count=slide_count,
        layout_ready_count=layout_ready_count,
        has_brief=has_brief,
        ready_for_export=ready_for_export,
        updated_at=updated_at,
        outline_approved=outline_approved,
        has_outline=has_outline,
        outline_changes_pending=outline_changes_pending,
        evidence_availability=evidence.availability,
        export_blocker_count=export_blocker_count,
        pptx_ready=pptx_ready,
        pdf_ready=pdf_ready,
    )


def load_project_progress_snapshot() -> ProjectProgressSnapshot | None:
    """Load a lightweight progress snapshot for the sidebar."""
    from archium.infrastructure.database.repositories import ProjectRepository

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
            project = max(projects, key=lambda item: item.updated_at)

        preferred = None
        if raw_presentation is not None:
            try:
                preferred = UUID(str(raw_presentation))
            except ValueError:
                preferred = None

        snapshot = _snapshot_for_project(
            session,
            project,
            preferred_presentation_id=preferred,
        )

        st.session_state.selected_project_id = str(snapshot.project_id)
        if snapshot.presentation_id is not None:
            st.session_state.selected_presentation_id = str(snapshot.presentation_id)

        return snapshot


def list_recent_project_snapshots(*, limit: int = 6) -> list[ProjectProgressSnapshot]:
    """Recent projects for the home cockpit, newest activity first."""
    from archium.infrastructure.database.repositories import ProjectRepository

    with get_session() as session:
        projects = ProjectRepository(session).list_all()
        if not projects:
            return []
        snapshots = [_snapshot_for_project(session, project) for project in projects]
    snapshots.sort(key=lambda item: item.updated_at, reverse=True)
    return snapshots[:limit]


def load_cockpit_task_summary(snapshot: ProjectProgressSnapshot) -> CockpitTaskSummary:
    """Aggregate actionable tasks for the selected / primary project."""
    from archium.application.page_status_board_service import PageStatusBoardService
    from archium.domain.page_pipeline_status import PagePipelinePhase

    pending_layout = snapshot.pending_count
    missing_assets = 0
    drawing_qa = 0
    other_attention = 0
    pending_proposals = _count_session_proposals()

    if snapshot.presentation_id is not None:
        try:
            with get_session() as session:
                board = PageStatusBoardService(session).build_board(snapshot.presentation_id)
                for row in board.rows:
                    if row.phase == PagePipelinePhase.ASSET_MISSING:
                        missing_assets += 1
                    elif row.phase == PagePipelinePhase.DRAWING_QA_FAILED:
                        drawing_qa += 1
                    elif row.severity in {"warn", "error"} and row.phase not in {
                        PagePipelinePhase.COMPLETE,
                        PagePipelinePhase.SKIPPED,
                    }:
                        other_attention += 1
        except Exception:
            pass

    lines: list[str] = []
    if snapshot.outline_changes_pending:
        lines.append("大纲已编辑，待重新确认")
    if missing_assets:
        lines.append(f"{missing_assets} 页缺少素材")
    if drawing_qa:
        lines.append(f"{drawing_qa} 页图纸可读性未通过")
    if pending_proposals:
        lines.append(f"{pending_proposals} 个 AI 提案待确认")
    if pending_layout:
        lines.append(f"{pending_layout} 页版式待完成")
    if other_attention and not lines:
        lines.append(f"{other_attention} 页需要关注")

    return CockpitTaskSummary(
        missing_asset_pages=missing_assets,
        drawing_qa_failed_pages=drawing_qa,
        pending_proposals=pending_proposals,
        pending_layout_pages=pending_layout,
        other_attention_pages=other_attention,
        lines=tuple(lines),
    )


def _count_session_proposals() -> int:
    return sum(
        1
        for key in st.session_state
        if str(key).startswith("studio_scene_proposal_")
        and st.session_state.get(key) is not None
    )


def greeting_for_now() -> str:
    hour = datetime.now().astimezone().hour
    if hour < 12:
        return "早上好"
    if hour < 18:
        return "下午好"
    return "晚上好"


def continue_work_page_key(snapshot: ProjectProgressSnapshot) -> str:
    return snapshot.current_stage_id


def render_project_progress_card() -> None:
    """User-facing current project / progress summary for the sidebar."""
    st.markdown('<div class="section-label">当前项目</div>', unsafe_allow_html=True)
    try:
        snapshot = load_project_progress_snapshot()
    except Exception:
        st.caption("进度暂不可用。可到「项目」选择或创建项目。")
        from archium.ui import icons

        st.page_link(
            get_app_page("project-management"), label="打开项目", icon=icons.PROJECT
        )
        return

    if snapshot is None:
        st.caption("还没有项目。")
        from archium.ui import icons

        st.page_link(
            get_app_page("project-management"), label="创建项目", icon=icons.PROJECT
        )
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

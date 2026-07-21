"""Before / After comparison UI for SceneChangeProposal."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import streamlit as st

from archium.application.visual.scene_proposal_service import (
    count_issues_by_severity,
    summarize_patch_action,
)
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.config.settings import Settings
from archium.domain.visual.page_quality import IssueSeverity
from archium.domain.visual.scene_change_proposal import (
    ProposalStatus,
    SceneChangeProposal,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.visual_service import SlideVisualSnapshot


def _proposal_session_key(slide_id: UUID) -> str:
    return f"studio_scene_proposal_{slide_id}"


def get_stored_proposal(slide_id: UUID) -> SceneChangeProposal | None:
    payload = st.session_state.get(_proposal_session_key(slide_id))
    if payload is None:
        return None
    try:
        return SceneChangeProposal.model_validate(payload)
    except Exception:
        return None


def store_proposal(proposal: SceneChangeProposal) -> None:
    st.session_state[_proposal_session_key(proposal.slide_id)] = proposal.model_dump(mode="json")


def clear_proposal(slide_id: UUID) -> None:
    st.session_state.pop(_proposal_session_key(slide_id), None)


def render_proposal_compare_panel(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
    presentation_id: UUID,
    settings: Settings,
) -> None:
    """Render proposal creation and before/after review controls."""
    st.markdown("**Scene 修改提案**")
    if slide_snapshot is None or slide_snapshot.render_scene is None:
        st.caption("当前页尚无 RenderScene，无法生成修改提案。")
        return

    slide = slide_snapshot.slide
    proposal = get_stored_proposal(slide.id)

    if proposal is None:
        st.caption("在上方 **AI 编辑** 中输入描述，点击「生成修改提案」后在此查看 Before/After。")
        return

    if proposal.status == ProposalStatus.SUPERSEDED:
        st.warning("该提案已过期（页面在提案生成后被修改）。")

    st.caption(f"提案状态：{proposal.status.value}")
    _render_before_after_previews(proposal, settings)
    _render_change_list(proposal)
    _render_qa_diff(proposal)
    _render_decision_buttons(proposal, slide_snapshot, settings)


def _render_before_after_previews(
    proposal: SceneChangeProposal,
    settings: Settings,
) -> None:
    with get_session() as session:
        studio_scene = StudioSceneService(session, settings=settings)
        before_path = _preview_path(
            studio_scene,
            proposal.presentation_id,
            proposal.base_scene,
        )
        after_path = _preview_path(
            studio_scene,
            proposal.presentation_id,
            proposal.proposed_scene,
        )

    left, right = st.columns(2)
    with left:
        st.markdown("**修改前**")
        if before_path.is_file():
            st.image(str(before_path), use_container_width=True)
        else:
            st.caption("预览不可用")
    with right:
        st.markdown("**修改后**")
        if after_path.is_file():
            st.image(str(after_path), use_container_width=True)
        else:
            st.caption("预览不可用")


def _preview_path(studio_scene: StudioSceneService, presentation_id: UUID, scene) -> Path:
    return studio_scene.render_scene_preview(presentation_id, scene)


def _render_change_list(proposal: SceneChangeProposal) -> None:
    st.markdown("**改动清单**")
    if not proposal.patch_actions:
        st.caption("无结构化 patch 记录。")
        return
    for action in proposal.patch_actions:
        st.markdown(f"- {summarize_patch_action(action)}")


def _render_qa_diff(proposal: SceneChangeProposal) -> None:
    from archium.application.visual.scene_proposal_qa import compare_proposal_qa

    diff = compare_proposal_qa(proposal.qa_before, proposal.qa_after)
    before_major = count_issues_by_severity(
        proposal.qa_before,
        IssueSeverity.MAJOR,
    ) + count_issues_by_severity(proposal.qa_before, IssueSeverity.BLOCKER)
    after_major = count_issues_by_severity(
        proposal.qa_after,
        IssueSeverity.MAJOR,
    ) + count_issues_by_severity(proposal.qa_after, IssueSeverity.BLOCKER)
    st.markdown("**QA 变化**")
    st.markdown(f"- 修改前：{before_major} 个 Major/Blocker")
    st.markdown(f"- 修改后：{after_major} 个 Major/Blocker")
    if diff.resolved:
        st.markdown(f"- 已解决：{len(diff.resolved)} 项")
    if diff.introduced:
        st.markdown(f"- 新增：{len(diff.introduced)} 项")


def _render_decision_buttons(
    proposal: SceneChangeProposal,
    slide_snapshot: SlideVisualSnapshot,
    settings: Settings,
) -> None:
    slide = slide_snapshot.slide
    accept_col, reject_col, clear_col = st.columns(3)
    if accept_col.button(
        "接受全部",
        type="primary",
        use_container_width=True,
        key=f"studio_accept_proposal_{proposal.proposal_id}",
    ):
        _accept_proposal(proposal, slide_snapshot, settings)
    if reject_col.button(
        "拒绝全部",
        use_container_width=True,
        key=f"studio_reject_proposal_{proposal.proposal_id}",
    ):
        store_proposal(proposal.model_copy(update={"status": ProposalStatus.REJECTED}))
        st.info("已拒绝该提案，正式 Scene 未改变。")
        st.rerun()
    if clear_col.button(
        "清除提案",
        use_container_width=True,
        key=f"studio_clear_proposal_{proposal.proposal_id}",
    ):
        clear_proposal(slide.id)
        st.rerun()


def _accept_proposal(
    proposal: SceneChangeProposal,
    slide_snapshot: SlideVisualSnapshot,
    settings: Settings,
) -> None:
    try:
        from archium.application.visual.scene_proposal_service import SceneProposalService

        slide = slide_snapshot.slide
        current_scene = slide_snapshot.render_scene
        with st.spinner("正在接受提案并创建 Scene Revision…"), get_session() as session:
            service = SceneProposalService(session, settings=settings)
            if current_scene is not None and service.is_stale(proposal, current_scene):
                store_proposal(proposal.model_copy(update={"status": ProposalStatus.SUPERSEDED}))
                raise WorkflowError("页面在提案生成后已被修改，请重新生成提案。")
            service.accept_proposal(
                proposal,
                slide,
                current_scene=current_scene,
            )
        clear_proposal(slide.id)
        st.success("提案已接受，Scene Revision 已保存。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))

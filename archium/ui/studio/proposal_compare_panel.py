"""Before / After comparison UI for SceneChangeProposal."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import streamlit as st

from archium.application.visual.scene_proposal_service import (
    count_issues_by_severity,
    summarize_command_result,
    summarize_patch_action,
)
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.config.settings import Settings, get_settings
from archium.domain.visual.page_quality import IssueSeverity
from archium.domain.visual.render_scene import RenderScene
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
    cached = st.session_state.get(_proposal_session_key(slide_id))
    if cached is not None:
        try:
            return SceneChangeProposal.model_validate(cached)
        except Exception:
            st.session_state.pop(_proposal_session_key(slide_id), None)

    with get_session() as session:
        from archium.application.visual.scene_proposal_service import SceneProposalService

        settings = get_settings()
        proposal = SceneProposalService(session, settings=settings).load_active_proposal(slide_id)
        if proposal is not None:
            st.session_state[_proposal_session_key(slide_id)] = proposal.model_dump(mode="json")
        return proposal


def store_proposal(proposal: SceneChangeProposal) -> None:
    with get_session() as session:
        from archium.application.visual.scene_proposal_service import SceneProposalService

        settings = get_settings()
        persisted = SceneProposalService(session, settings=settings).save_proposal(proposal)
    st.session_state[_proposal_session_key(proposal.slide_id)] = persisted.model_dump(mode="json")


def clear_proposal(slide_id: UUID) -> None:
    proposal = get_stored_proposal(slide_id)
    if proposal is not None and proposal.status in {
        ProposalStatus.READY,
        ProposalStatus.READY_WITH_WARNINGS,
        ProposalStatus.DRAFT,
    }:
        with get_session() as session:
            from archium.application.visual.scene_proposal_service import SceneProposalService

            settings = get_settings()
            SceneProposalService(session, settings=settings).mark_proposal_superseded(proposal)
    st.session_state.pop(_proposal_session_key(slide_id), None)


def _proposal_selection_key(proposal_id: UUID) -> str:
    return f"studio_proposal_selected_actions_{proposal_id}"


def _selected_action_ids(proposal: SceneChangeProposal) -> set[str]:
    stored = st.session_state.get(_proposal_selection_key(proposal.proposal_id))
    if stored is None:
        return {str(action.action_id) for action in proposal.patch_actions}
    return {str(item) for item in stored}


def _store_selected_action_ids(proposal: SceneChangeProposal, action_ids: set[str]) -> None:
    st.session_state[_proposal_selection_key(proposal.proposal_id)] = sorted(action_ids)


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
    elif proposal.status == ProposalStatus.READY_WITH_WARNINGS:
        st.warning("部分命令未能应用，请查看下方命令执行结果。")

    st.caption(f"提案状态：{proposal.status.value}")
    _render_command_results(proposal)
    _render_before_after_previews(proposal, settings)
    _render_change_list(proposal)
    _render_qa_diff(proposal)
    _render_decision_buttons(proposal, slide_snapshot, settings)


def _render_command_results(proposal: SceneChangeProposal) -> None:
    if not proposal.command_results:
        return
    st.markdown("**命令执行结果**")
    for result in proposal.command_results:
        summary = summarize_command_result(proposal, result)
        if result.status == "failed":
            st.error(summary)
        elif result.status == "skipped":
            st.caption(summary)
        else:
            st.markdown(f"- {summary}")


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


def _preview_path(
    studio_scene: StudioSceneService,
    presentation_id: UUID,
    scene: RenderScene,
) -> Path:
    return studio_scene.render_scene_preview(presentation_id, scene)


def _render_change_list(proposal: SceneChangeProposal) -> None:
    st.markdown("**改动清单**")
    if not proposal.patch_actions:
        st.caption("无结构化 patch 记录。")
        return
    selected_ids = _selected_action_ids(proposal)
    for action in proposal.patch_actions:
        action_key = str(action.action_id)
        checked = st.checkbox(
            summarize_patch_action(action),
            value=action_key in selected_ids,
            key=f"studio_proposal_action_{proposal.proposal_id}_{action_key}",
        )
        if checked:
            selected_ids.add(action_key)
        else:
            selected_ids.discard(action_key)
    _store_selected_action_ids(proposal, selected_ids)


def _render_qa_diff(proposal: SceneChangeProposal) -> None:
    from archium.application.visual.scene_deterministic_qa_service import summarize_layer_counts
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

    layer_labels = {
        "semantic": "Semantic QA",
        "geometry": "Geometry QA",
        "asset": "Asset QA",
        "drawing": "Drawing QA",
        "render": "Render QA",
        "post_render": "Post-render Visual QA",
    }
    if proposal.qa_after_by_layer:
        st.markdown("**分层 QA（修改后）**")
        after_counts = summarize_layer_counts(
            {layer: tuple(items) for layer, items in proposal.qa_after_by_layer.items()}
        )
        for layer, label in layer_labels.items():
            count = after_counts.get(layer, 0)
            if count:
                st.markdown(f"- {label}：{count} 个 Major/Blocker")
            else:
                st.caption(f"- {label}：通过")


def _render_decision_buttons(
    proposal: SceneChangeProposal,
    slide_snapshot: SlideVisualSnapshot,
    settings: Settings,
) -> None:
    slide = slide_snapshot.slide
    accept_col, partial_col, reject_col, clear_col = st.columns(4)
    if accept_col.button(
        "接受全部",
        type="primary",
        use_container_width=True,
        key=f"studio_accept_proposal_{proposal.proposal_id}",
    ):
        _accept_proposal(proposal, slide_snapshot, settings)
    if partial_col.button(
        "接受选中",
        use_container_width=True,
        key=f"studio_partial_accept_proposal_{proposal.proposal_id}",
    ):
        _accept_proposal(
            proposal,
            slide_snapshot,
            settings,
            partial=True,
        )
    if reject_col.button(
        "拒绝全部",
        use_container_width=True,
        key=f"studio_reject_proposal_{proposal.proposal_id}",
    ):
        with get_session() as session:
            from archium.application.visual.scene_proposal_service import SceneProposalService

            rejected = SceneProposalService(session, settings=settings).reject_proposal(proposal)
        clear_proposal(slide.id)
        st.info(f"已拒绝该提案（{rejected.status.value}），正式 Scene 未改变。")
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
    *,
    partial: bool = False,
) -> None:
    try:
        from archium.application.visual.scene_proposal_service import SceneProposalService
        from archium.domain.visual.scene_change_proposal import ProposalDecision

        slide = slide_snapshot.slide
        current_scene = slide_snapshot.render_scene
        with st.spinner("正在接受提案并创建 Scene Revision…"), get_session() as session:
            service = SceneProposalService(session, settings=settings)
            if current_scene is not None and service.is_stale(proposal, current_scene):
                service.mark_proposal_superseded(proposal)
                clear_proposal(slide.id)
                raise WorkflowError("页面在提案生成后已被修改，请重新生成提案。")
            decision = None
            if partial:
                selected_ids = _selected_action_ids(proposal)
                accepted_action_ids = [
                    action.action_id
                    for action in proposal.patch_actions
                    if str(action.action_id) in selected_ids
                ]
                if not accepted_action_ids:
                    raise WorkflowError("请至少勾选一项要接受的修改。")
                decision = ProposalDecision(
                    proposal_id=proposal.proposal_id,
                    accepted_action_ids=accepted_action_ids,
                )
            result = service.accept_proposal(
                proposal,
                slide,
                decision=decision,
                current_scene=current_scene,
            )
        clear_proposal(slide.id)
        status_label = result.proposal.status.value
        st.success(f"提案已接受（{status_label}），Scene Revision 已保存。")
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))

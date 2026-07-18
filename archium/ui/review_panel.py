"""Streamlit UI for Brief, Storyline, and SlideSpec human review."""

from __future__ import annotations

from uuid import UUID

import pandas as pd
import streamlit as st

from archium.application.review_models import (
    BriefUpdate,
    ChapterUpdate,
    SlideUpdate,
    StorylineUpdate,
    parse_multiline_items,
)
from archium.application.review_service import PresentationReviewService
from archium.config import get_settings
from archium.domain.enums import (
    ApprovalStatus,
    ReviewCategory,
    ReviewLayer,
    ReviewSeverity,
    ReviewStatus,
    SlideStatus,
    SlideType,
)
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import repair_strategy_for_rule
from archium.domain.slide import SlideSpec
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.artifact_history_panel import (
    render_brief_history_panel,
    render_storyline_history_panel,
)
from archium.ui.asset_board_panel import render_asset_board_panel
from archium.ui.error_handlers import format_user_error
from archium.ui.review_analytics_panel import REPAIR_STRATEGY_LABELS, render_rule_code_stats
from archium.ui.slide_history_panel import render_slide_history_panel
from archium.ui.workspace_service import (
    continue_workflow_after_review,
    regenerate_brief,
    regenerate_slide_plan,
    regenerate_storyline,
    resume_workflow,
)

FOCUS_SLIDE_SESSION_KEY = "review_focus_slide_id"

APPROVAL_LABELS = {
    ApprovalStatus.DRAFT: "草稿",
    ApprovalStatus.PENDING: "待审核",
    ApprovalStatus.APPROVED: "已通过",
    ApprovalStatus.REJECTED: "已驳回",
}

SLIDE_STATUS_LABELS = {
    SlideStatus.DRAFT: "草稿",
    SlideStatus.PLANNED: "待审核",
    SlideStatus.APPROVED: "已通过",
    SlideStatus.RENDERED: "已渲染",
    SlideStatus.NEEDS_REVISION: "需修改",
}

SLIDE_TYPE_OPTIONS = [item.value for item in SlideType]

SEVERITY_LABELS = {
    ReviewSeverity.CRITICAL: "严重",
    ReviewSeverity.HIGH: "高",
    ReviewSeverity.MEDIUM: "中",
    ReviewSeverity.SUGGESTION: "建议",
}

CATEGORY_LABELS = {
    ReviewCategory.CITATION: "引用",
    ReviewCategory.CONTENT: "内容",
    ReviewCategory.STRUCTURE: "结构",
    ReviewCategory.VISUAL: "视觉",
    ReviewCategory.CONSISTENCY: "一致性",
    ReviewCategory.COVERAGE: "覆盖度",
    ReviewCategory.LENGTH: "篇幅",
    ReviewCategory.OTHER: "其他",
}

LAYER_LABELS = {
    ReviewLayer.CONTENT: "内容层",
    ReviewLayer.EVIDENCE: "证据层",
    ReviewLayer.ARCHITECTURAL: "建筑专业层",
    ReviewLayer.LAYOUT: "版面层",
}

STATUS_LABELS = {
    ReviewStatus.OPEN: "待处理",
    ReviewStatus.ACKNOWLEDGED: "已知悉",
    ReviewStatus.RESOLVED: "已解决",
    ReviewStatus.DISMISSED: "已忽略",
}


def _approval_badge(status: ApprovalStatus) -> str:
    return APPROVAL_LABELS.get(status, status.value)


def _slide_status_badge(status: SlideStatus) -> str:
    return SLIDE_STATUS_LABELS.get(status, status.value)


def _slide_lookup(slides: list[SlideSpec]) -> dict[UUID, SlideSpec]:
    return {slide.id: slide for slide in slides}


def _slide_label(slide: SlideSpec | None) -> str:
    if slide is None:
        return "—"
    return f"p{slide.order + 1} · {slide.title}"


def _issue_slide_label(issue: ReviewIssue, slides_by_id: dict[UUID, SlideSpec]) -> str:
    if issue.slide_id is None:
        return "全局"
    return _slide_label(slides_by_id.get(issue.slide_id))


def _focus_slide(slide_id: UUID) -> None:
    st.session_state[FOCUS_SLIDE_SESSION_KEY] = str(slide_id)


def _render_critical_recovery_actions(
    *,
    presentation_id: UUID,
    workflow_run_id: UUID | None,
    open_critical: list[ReviewIssue],
) -> None:
    if not open_critical:
        return

    st.markdown("**严重问题修复**")
    has_coverage = any(issue.category == ReviewCategory.COVERAGE for issue in open_critical)
    has_structure = any(issue.category == ReviewCategory.STRUCTURE for issue in open_critical)
    has_slide_issues = any(issue.slide_id is not None for issue in open_critical)

    col1, col2, col3 = st.columns(3)
    if col1.button(
        "重新生成 Slide 计划",
        key=f"recover_regen_slides_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_slide_plan(presentation_id, workflow_run_id=workflow_run_id)
            st.success("Slide 计划已重新生成，请重新审核质量结果。")
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成失败：{exc}")

    if has_structure and col2.button(
        "重新生成 Storyline",
        key=f"recover_regen_storyline_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_storyline(presentation_id, workflow_run_id=workflow_run_id)
            st.success("Storyline 已重新生成。")
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成失败：{exc}")

    if has_coverage and col3.button(
        "重新生成 Brief",
        key=f"recover_regen_brief_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_brief(presentation_id, workflow_run_id=workflow_run_id)
            st.success("Brief 已重新生成。")
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成失败：{exc}")

    if workflow_run_id is not None and st.button(
        "重试工作流导出",
        key=f"recover_retry_export_{presentation_id}",
        use_container_width=True,
        help="在解决或忽略严重问题后，从 checkpoint 重试导出。",
    ):
        try:
            result = resume_workflow(workflow_run_id)
            st.session_state.last_workflow_result = result
            if result.succeeded:
                st.success("导出已完成。")
            else:
                st.error("工作流仍有错误，请继续处理质量审核问题。")
            st.rerun()
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        except Exception as exc:
            st.error(format_user_error(exc))

    if has_slide_issues:
        st.caption("页面级问题可使用下方「定位页面」跳转到 SlideSpec 标签页编辑。")


def _render_regenerate_actions(
    *,
    presentation_id: UUID,
    workflow_run_id: UUID | None,
    brief_status: ApprovalStatus | None,
    storyline_status: ApprovalStatus | None,
    slides_need_revision: bool,
) -> None:
    cols = st.columns(3)
    if brief_status == ApprovalStatus.REJECTED and cols[0].button(
        "重新生成 Brief",
        key=f"regen_brief_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_brief(presentation_id, workflow_run_id=workflow_run_id)
            st.success("Brief 已重新生成，请审核后继续。")
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成 Brief 失败：{exc}")

    if storyline_status == ApprovalStatus.REJECTED and cols[1].button(
        "重新生成 Storyline",
        key=f"regen_storyline_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_storyline(presentation_id, workflow_run_id=workflow_run_id)
            st.success("Storyline 已重新生成，请审核后继续。")
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成 Storyline 失败：{exc}")

    if slides_need_revision and cols[2].button(
        "重新生成 Slide 计划",
        key=f"regen_slides_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_slide_plan(presentation_id, workflow_run_id=workflow_run_id)
            st.success("Slide 计划已重新生成，请审核后继续。")
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成 Slide 计划失败：{exc}")


def _render_brief_editor(context_presentation_id: UUID, workflow_run_id: UUID | None) -> None:
    with get_session() as session:
        review_service = PresentationReviewService(session)
        context = review_service.get_review_context(
            context_presentation_id,
            workflow_run_id=workflow_run_id,
        )
    if context is None or context.brief is None:
        st.caption("当前没有可编辑的 Brief。")
        return

    brief = context.brief
    st.markdown(f"**Brief 审核** · 状态：{_approval_badge(brief.approval_status)}")

    with st.form(f"brief_review_{brief.id}"):
        title = st.text_input("标题", value=brief.title)
        audience = st.text_input("汇报对象", value=brief.audience)
        purpose = st.text_input("汇报目的", value=brief.purpose)
        core_message = st.text_area("核心信息", value=brief.core_message)
        duration_minutes = st.number_input("时长（分钟）", min_value=1, max_value=480, value=brief.duration_minutes)
        target_slide_count = st.number_input(
            "目标页数",
            min_value=1,
            max_value=200,
            value=brief.target_slide_count,
        )
        tone = st.text_input("语气风格", value=brief.tone)
        required_sections = st.text_area(
            "必要章节（每行一项）",
            value="\n".join(brief.required_sections),
        )
        decisions_required = st.text_area(
            "待决策事项（每行一项）",
            value="\n".join(brief.decisions_required),
        )
        audience_concerns = st.text_area(
            "对象顾虑（每行一项）",
            value="\n".join(brief.audience_concerns),
        )
        excluded_topics = st.text_area(
            "排除主题（每行一项）",
            value="\n".join(brief.excluded_topics),
        )

        col1, col2, col3 = st.columns(3)
        save_clicked = col1.form_submit_button("保存修改", use_container_width=True)
        approve_clicked = col2.form_submit_button("批准 Brief", use_container_width=True)
        reject_clicked = col3.form_submit_button("驳回 Brief", use_container_width=True)

    update = BriefUpdate(
        title=title,
        audience=audience,
        purpose=purpose,
        core_message=core_message,
        duration_minutes=int(duration_minutes),
        target_slide_count=int(target_slide_count),
        tone=tone,
        language=brief.language,
        required_sections=parse_multiline_items(required_sections),
        decisions_required=parse_multiline_items(decisions_required),
        audience_concerns=parse_multiline_items(audience_concerns),
        excluded_topics=parse_multiline_items(excluded_topics),
    )

    if save_clicked or approve_clicked or reject_clicked:
        with get_session() as session:
            review_service = PresentationReviewService(session)
            review_service.update_brief(brief.id, update)
            if approve_clicked:
                review_service.approve_brief(brief.id)
            elif reject_clicked:
                review_service.reject_brief(brief.id)
        st.success("Brief 已更新。")
        st.rerun()

    render_brief_history_panel(brief_id=brief.id)


def _render_storyline_editor(context_presentation_id: UUID, workflow_run_id: UUID | None) -> None:
    with get_session() as session:
        review_service = PresentationReviewService(session)
        context = review_service.get_review_context(
            context_presentation_id,
            workflow_run_id=workflow_run_id,
        )
    if context is None or context.storyline is None:
        st.caption("当前没有可编辑的 Storyline。")
        return

    storyline = context.storyline
    st.markdown(f"**Storyline 审核** · 状态：{_approval_badge(storyline.approval_status)}")

    with st.form(f"storyline_meta_{storyline.id}"):
        thesis = st.text_area("总体论点", value=storyline.thesis)
        narrative_pattern = st.text_input("叙事模式", value=storyline.narrative_pattern)
        meta_submit = st.form_submit_button("保存论点", use_container_width=True)

    chapter_rows = [
        {
            "id": chapter.id,
            "title": chapter.title,
            "purpose": chapter.purpose,
            "key_message": chapter.key_message,
            "order": chapter.order,
            "estimated_slide_count": chapter.estimated_slide_count,
        }
        for chapter in sorted(storyline.chapters, key=lambda item: item.order)
    ]
    edited = st.data_editor(
        pd.DataFrame(chapter_rows),
        num_rows="dynamic",
        use_container_width=True,
        key=f"storyline_chapters_{storyline.id}",
    )

    col1, col2, col3 = st.columns(3)
    save_clicked = col1.button("保存 Storyline", key=f"save_storyline_{storyline.id}", use_container_width=True)
    approve_clicked = col2.button("批准 Storyline", key=f"approve_storyline_{storyline.id}", use_container_width=True)
    reject_clicked = col3.button("驳回 Storyline", key=f"reject_storyline_{storyline.id}", use_container_width=True)

    if meta_submit or save_clicked or approve_clicked or reject_clicked:
        chapters = [
            ChapterUpdate(
                id=str(row["id"]),
                title=str(row["title"]),
                purpose=str(row["purpose"]),
                key_message=str(row["key_message"]),
                order=int(row["order"]),
                estimated_slide_count=int(row["estimated_slide_count"]),
            )
            for row in edited.to_dict(orient="records")
            if str(row.get("id", "")).strip()
        ]
        update = StorylineUpdate(
            thesis=thesis,
            narrative_pattern=narrative_pattern,
            chapters=chapters,
        )
        with get_session() as session:
            review_service = PresentationReviewService(session)
            review_service.update_storyline(storyline.id, update)
            if approve_clicked:
                review_service.approve_storyline(storyline.id)
            elif reject_clicked:
                review_service.reject_storyline(storyline.id)
        st.success("Storyline 已更新。")
        st.rerun()

    render_storyline_history_panel(storyline_id=storyline.id)


def _render_slides_editor(context_presentation_id: UUID, workflow_run_id: UUID | None) -> None:
    with get_session() as session:
        review_service = PresentationReviewService(session)
        context = review_service.get_review_context(
            context_presentation_id,
            workflow_run_id=workflow_run_id,
        )
    if context is None or not context.slides:
        st.caption("当前没有可编辑的 SlideSpec。")
        return

    approved_count = sum(1 for slide in context.slides if slide.status == SlideStatus.APPROVED)
    st.markdown(f"**SlideSpec 审核** · 已通过 {approved_count}/{len(context.slides)} 页")

    focus_id = st.session_state.get(FOCUS_SLIDE_SESSION_KEY)
    if focus_id:
        focused = next((slide for slide in context.slides if str(slide.id) == focus_id), None)
        if focused is not None:
            focus_cols = st.columns([5, 1])
            focus_cols[0].info(
                f"定位页面：第 {focused.order + 1} 页 · **{focused.title}**\n\n{focused.message}"
            )
            if focus_cols[1].button("清除", key=f"clear_focus_{context_presentation_id}"):
                del st.session_state[FOCUS_SLIDE_SESSION_KEY]
                st.rerun()

    slide_rows = [
        {
            "id": str(slide.id),
            "order": slide.order,
            "chapter_id": slide.chapter_id,
            "title": slide.title,
            "message": slide.message,
            "slide_type": slide.slide_type.value,
            "key_points": "\n".join(slide.key_points),
            "status": _slide_status_badge(slide.status),
        }
        for slide in sorted(context.slides, key=lambda item: item.order)
    ]
    edited = st.data_editor(
        pd.DataFrame(slide_rows),
        column_config={
            "id": st.column_config.TextColumn("ID", disabled=True),
            "status": st.column_config.TextColumn("状态", disabled=True),
            "slide_type": st.column_config.SelectboxColumn("类型", options=SLIDE_TYPE_OPTIONS),
        },
        num_rows="dynamic",
        use_container_width=True,
        key=f"slides_editor_{context_presentation_id}",
    )

    col1, col2, col3 = st.columns(3)
    save_clicked = col1.button("保存全部页面", key=f"save_slides_{context_presentation_id}", use_container_width=True)
    approve_all_clicked = col2.button(
        "批准全部页面",
        key=f"approve_slides_{context_presentation_id}",
        use_container_width=True,
    )
    regen_clicked = col3.button(
        "重新生成 Slide 计划",
        key=f"regen_slides_inline_{context_presentation_id}",
        use_container_width=True,
    )

    if save_clicked:
        with get_session() as session:
            review_service = PresentationReviewService(session)
            for row in edited.to_dict(orient="records"):
                slide_id = row.get("id")
                if not slide_id:
                    continue
                review_service.update_slide(
                    UUID(str(slide_id)),
                    SlideUpdate(
                        chapter_id=str(row["chapter_id"]),
                        order=int(row["order"]),
                        title=str(row["title"]),
                        message=str(row["message"]),
                        slide_type=str(row["slide_type"]),
                        key_points=parse_multiline_items(str(row.get("key_points", ""))),
                    ),
                )
        st.success("SlideSpec 已保存。")
        st.rerun()

    if approve_all_clicked:
        with get_session() as session:
            review_service = PresentationReviewService(session)
            review_service.approve_all_slides(context_presentation_id)
        st.success("全部页面已批准。")
        st.rerun()

    if regen_clicked:
        try:
            regenerate_slide_plan(context_presentation_id, workflow_run_id=workflow_run_id)
            st.success("Slide 计划已重新生成。")
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成失败：{exc}")

    render_slide_history_panel(presentation_id=context_presentation_id, slides=context.slides)


def _render_review_issues_panel(
    presentation_id: UUID,
    *,
    slides: list[SlideSpec],
    workflow_run_id: UUID | None,
) -> None:
    settings = get_settings()
    slides_by_id = _slide_lookup(slides)
    with get_session() as session:
        review_service = PresentationReviewService(session)
        all_issues = review_service.list_review_issues(presentation_id)

    if not all_issues:
        st.caption("暂无自动审核问题。运行完整工作流后将在此显示四层审核结果。")
        return

    with st.expander("规则命中统计（rule_code）", expanded=False):
        render_rule_code_stats(all_issues)
        st.caption("rule_code 亦可在下方问题列表中查看。")

    issues = all_issues
    layer_counts: dict[ReviewLayer, int] = {}
    for issue in issues:
        layer_counts[issue.reviewer_layer] = layer_counts.get(issue.reviewer_layer, 0) + 1
    if layer_counts:
        summary = " · ".join(
            f"{LAYER_LABELS.get(layer, layer.value)} {count}"
            for layer, count in sorted(layer_counts.items(), key=lambda item: item[0].value)
        )
        st.caption(f"审核分层统计：{summary}")

    layer_options = ["全部"] + [
        LAYER_LABELS[layer]
        for layer in (
            ReviewLayer.CONTENT,
            ReviewLayer.EVIDENCE,
            ReviewLayer.ARCHITECTURAL,
            ReviewLayer.LAYOUT,
        )
    ]
    selected_layer_label = st.selectbox(
        "按审核层级筛选",
        options=layer_options,
        key=f"review_layer_filter_{presentation_id}",
    )
    if selected_layer_label != "全部":
        selected_layer = next(
            layer
            for layer, label in LAYER_LABELS.items()
            if label == selected_layer_label
        )
        issues = [issue for issue in issues if issue.reviewer_layer == selected_layer]

    open_critical = [
        issue
        for issue in issues
        if issue.severity == ReviewSeverity.CRITICAL and issue.status == ReviewStatus.OPEN
    ]
    if open_critical and settings.block_export_on_critical_review:
        st.error(
            f"存在 {len(open_critical)} 个未处理的严重问题，已阻断 JSON/Marp 导出。"
            "请处理后重新运行或继续工作流。"
        )
        _render_critical_recovery_actions(
            presentation_id=presentation_id,
            workflow_run_id=workflow_run_id,
            open_critical=open_critical,
        )
    elif open_critical:
        st.warning(f"存在 {len(open_critical)} 个严重问题（当前未启用导出阻断）。")
        _render_critical_recovery_actions(
            presentation_id=presentation_id,
            workflow_run_id=workflow_run_id,
            open_critical=open_critical,
        )

    rows = [
        {
            "id": str(issue.id),
            "layer": LAYER_LABELS.get(issue.reviewer_layer, issue.reviewer_layer.value),
            "page": _issue_slide_label(issue, slides_by_id),
            "severity": SEVERITY_LABELS.get(issue.severity, issue.severity.value),
            "category": CATEGORY_LABELS.get(issue.category, issue.category.value),
            "rule_code": issue.rule_code,
            "title": issue.title,
            "description": issue.description,
            "suggestion": issue.suggestion or "",
            "status": STATUS_LABELS.get(issue.status, issue.status.value),
        }
        for issue in issues
    ]
    st.dataframe(
        pd.DataFrame(rows),
        column_config={"id": st.column_config.TextColumn("ID", disabled=True)},
        use_container_width=True,
        hide_index=True,
    )

    open_issues = [issue for issue in issues if issue.status == ReviewStatus.OPEN]
    if not open_issues:
        return

    st.caption("处理待办问题")
    for issue in open_issues[:12]:
        cols = st.columns([4, 1, 1, 1])
        page_hint = f"（{_issue_slide_label(issue, slides_by_id)}）"
        strategy = repair_strategy_for_rule(issue.rule_code)
        cols[0].markdown(
            f"**{LAYER_LABELS.get(issue.reviewer_layer, issue.reviewer_layer.value)}** · "
            f"**{SEVERITY_LABELS.get(issue.severity, issue.severity.value)}** · "
            f"{issue.title}{page_hint} — {issue.description}"
        )
        cols[0].caption(
            f"`{issue.rule_code}` · "
            f"{REPAIR_STRATEGY_LABELS.get(strategy, strategy)}"
        )
        if issue.slide_id is not None and cols[1].button(
            "定位页面",
            key=f"focus_issue_{issue.id}",
        ):
            _focus_slide(issue.slide_id)
            st.toast(f"已定位到 {_issue_slide_label(issue, slides_by_id)}，请切换到 SlideSpec 标签页。")
            st.rerun()
        if cols[2].button("标记已解决", key=f"resolve_issue_{issue.id}"):
            with get_session() as session:
                PresentationReviewService(session).resolve_review_issue(issue.id)
            st.rerun()
        if cols[3].button("忽略", key=f"dismiss_issue_{issue.id}"):
            with get_session() as session:
                PresentationReviewService(session).dismiss_review_issue(issue.id)
            st.rerun()


def render_review_panel(*, presentation_id: UUID | None, workflow_run_id: UUID | None) -> None:
    if presentation_id is None:
        return

    with get_session() as session:
        review_service = PresentationReviewService(session)
        context = review_service.get_review_context(
            presentation_id,
            workflow_run_id=workflow_run_id,
        )

    if context is None:
        st.warning("无法加载审核上下文。")
        return

    if context.awaiting_review:
        gate = context.review_gate or "unknown"
        st.info(f"工作流已暂停，等待 **{gate}** 人工审核。请编辑并批准后继续。")

    slides_need_revision = any(
        slide.status in {SlideStatus.NEEDS_REVISION, SlideStatus.DRAFT} for slide in context.slides
    )
    _render_regenerate_actions(
        presentation_id=presentation_id,
        workflow_run_id=workflow_run_id,
        brief_status=context.brief.approval_status if context.brief else None,
        storyline_status=context.storyline.approval_status if context.storyline else None,
        slides_need_revision=slides_need_revision
        or (context.slides_pending_review and context.review_gate == "slides"),
    )

    tab_brief, tab_storyline, tab_slides, tab_assets, tab_quality = st.tabs(
        ["Brief", "Storyline", "SlideSpec", "Asset Board", "质量审核"]
    )
    with tab_brief:
        _render_brief_editor(presentation_id, workflow_run_id)
    with tab_storyline:
        _render_storyline_editor(presentation_id, workflow_run_id)
    with tab_slides:
        _render_slides_editor(presentation_id, workflow_run_id)
    with tab_assets:
        render_asset_board_panel(
            project_id=context.presentation.project_id,
            presentation_id=presentation_id,
        )
    with tab_quality:
        _render_review_issues_panel(
            presentation_id,
            slides=context.slides,
            workflow_run_id=workflow_run_id,
        )

    if context.awaiting_review and workflow_run_id is not None and st.button(
        "继续运行工作流",
        type="primary",
        use_container_width=True,
    ):
        try:
            result = continue_workflow_after_review(workflow_run_id)
            st.session_state.last_workflow_result = result
            if result.awaiting_review:
                st.warning("工作流已进入下一审核节点，请继续审核。")
            elif result.succeeded:
                st.success(f"工作流已完成，共 {len(result.slides)} 页。")
            else:
                st.error("工作流继续执行时出现错误。")
            st.rerun()
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        except Exception as exc:
            st.error(format_user_error(exc))

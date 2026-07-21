"""Streamlit UI for Brief, Storyline, and SlideSpec human review."""

from __future__ import annotations

from uuid import UUID

import pandas as pd
import streamlit as st

from archium.application.automated_review_service import export_blocking_open_issues
from archium.application.outline_service import apply_audience_mode
from archium.application.review_models import (
    BriefUpdate,
    ChapterUpdate,
    NarrativeArcUpdate,
    NarrativePositionUpdate,
    OutlineSectionUpdate,
    OutlineUpdate,
    SlideAssetBindingUpdate,
    SlideIntentUpdate,
    SlideUpdate,
    StorylineUpdate,
    parse_multiline_items,
)
from archium.application.review_service import PresentationReviewService
from archium.config import get_settings
from archium.domain.enums import (
    ApprovalStatus,
    OutlineAudienceMode,
    ReviewCategory,
    ReviewLayer,
    ReviewSeverity,
    ReviewStatus,
    SlideAssetBindingRole,
    SlideStatus,
    SlideType,
)
from archium.domain.presentation_manuscript import ManuscriptStatus
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
from archium.ui.background_workflow_runner import (
    background_workflows_enabled,
    submit_continue_after_review,
)
from archium.ui.error_handlers import format_user_error
from archium.ui.label_map import (
    entity_label,
    regenerate_failure_label,
    regenerate_label,
    regenerate_success_label,
)
from archium.ui.page_status_board_panel import render_page_status_board
from archium.ui.review_analytics_panel import REPAIR_STRATEGY_LABELS, render_rule_code_stats
from archium.ui.slide_history_panel import render_slide_history_panel
from archium.ui.workflow_progress_panel import render_workflow_progress_panel, set_active_job_id
from archium.ui.workspace_service import (
    regenerate_brief,
    regenerate_outline_plan,
    regenerate_slide_plan,
    regenerate_storyline,
    resume_workflow,
)

FOCUS_SLIDE_SESSION_KEY = "review_focus_slide_id"

_BRIEF_LABEL = entity_label("PresentationBrief")
_MANUSCRIPT_LABEL = "研究手稿"
_STORYLINE_LABEL = entity_label("Storyline")
_OUTLINE_LABEL = entity_label("OutlinePlan")
_SLIDE_LABEL = entity_label("SlideSpec")
_ASSET_BOARD_LABEL = entity_label("AssetBoard")

AUDIENCE_MODE_LABELS = {
    OutlineAudienceMode.GOVERNMENT: "政府主管部门",
    OutlineAudienceMode.CLIENT: "建设单位/甲方",
    OutlineAudienceMode.EXPERT_REVIEW: "专家评审",
    OutlineAudienceMode.COMMUNITY: "社区居民",
    OutlineAudienceMode.INVESTOR: "投资人",
    OutlineAudienceMode.CULTURE_TOURISM: "文旅运营方",
    OutlineAudienceMode.INTERNAL_DESIGN: "设计团队内部评审",
}


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

# Reuse sidebar status-dot colors (dot-red / dot-yellow / dot-green).
SEVERITY_DOT_COLORS: dict[ReviewSeverity, str] = {
    ReviewSeverity.CRITICAL: "red",
    ReviewSeverity.HIGH: "red",
    ReviewSeverity.MEDIUM: "yellow",
    ReviewSeverity.SUGGESTION: "green",
}

SEVERITY_EMOJI: dict[ReviewSeverity, str] = {
    ReviewSeverity.CRITICAL: "🔴",
    ReviewSeverity.HIGH: "🟠",
    ReviewSeverity.MEDIUM: "🟡",
    ReviewSeverity.SUGGESTION: "🟢",
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
    ReviewLayer.SEMANTIC: "语义层",
}

STATUS_LABELS = {
    ReviewStatus.OPEN: "待处理",
    ReviewStatus.ACKNOWLEDGED: "已知悉",
    ReviewStatus.RESOLVED: "已解决",
    ReviewStatus.DISMISSED: "已忽略",
}


def _approval_badge(status: ApprovalStatus) -> str:
    return APPROVAL_LABELS.get(status, status.value)


def _severity_label(severity: ReviewSeverity) -> str:
    return SEVERITY_LABELS.get(severity, severity.value)


def _severity_badge_html(severity: ReviewSeverity) -> str:
    """Colored severity label using the shared status-dot CSS."""
    color = SEVERITY_DOT_COLORS.get(severity, "yellow")
    label = _severity_label(severity)
    return (
        f'<span class="status-dot dot-{color}" '
        f'style="vertical-align:middle;"></span>{label}'
    )


def _severity_table_label(severity: ReviewSeverity) -> str:
    """Severity for dataframe cells (emoji cue; HTML is not rendered there)."""
    emoji = SEVERITY_EMOJI.get(severity, "⚪")
    return f"{emoji} {_severity_label(severity)}"


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


def _export_block_summary(blockers: list[ReviewIssue]) -> str:
    critical_count = sum(1 for issue in blockers if issue.severity == ReviewSeverity.CRITICAL)
    asset_load_count = len(blockers) - critical_count
    parts: list[str] = []
    if critical_count:
        parts.append(f"{critical_count} 个严重")
    if asset_load_count:
        parts.append(f"{asset_load_count} 个必需素材无法读取")
    return "、".join(parts) if parts else f"{len(blockers)} 个"


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
        regenerate_label("SlideSpec"),
        key=f"recover_regen_slides_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_slide_plan(presentation_id, workflow_run_id=workflow_run_id)
            st.success(
                f"{regenerate_success_label('SlideSpec')}请重新审核质量结果。"
            )
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成失败：{exc}")

    if has_structure and col2.button(
        regenerate_label("Storyline"),
        key=f"recover_regen_storyline_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_storyline(presentation_id, workflow_run_id=workflow_run_id)
            st.success(regenerate_success_label("Storyline"))
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成失败：{exc}")

    if has_coverage and col3.button(
        regenerate_label("PresentationBrief"),
        key=f"recover_regen_brief_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_brief(presentation_id, workflow_run_id=workflow_run_id)
            st.success(regenerate_success_label("PresentationBrief"))
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
        st.caption(f"页面级问题可使用下方「定位页面」跳转到 {_SLIDE_LABEL} 标签页编辑。")


def _render_regenerate_actions(
    *,
    presentation_id: UUID,
    workflow_run_id: UUID | None,
    brief_status: ApprovalStatus | None,
    storyline_status: ApprovalStatus | None,
    outline_status: ApprovalStatus | None,
    slides_need_revision: bool,
) -> None:
    cols = st.columns(4)
    if brief_status == ApprovalStatus.REJECTED and cols[0].button(
        regenerate_label("PresentationBrief"),
        key=f"regen_brief_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_brief(presentation_id, workflow_run_id=workflow_run_id)
            st.success(f"{regenerate_success_label('PresentationBrief')}请审核后继续。")
            st.rerun()
        except Exception as exc:
            st.error(regenerate_failure_label("PresentationBrief").format(error=exc))

    if storyline_status == ApprovalStatus.REJECTED and cols[1].button(
        regenerate_label("Storyline"),
        key=f"regen_storyline_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_storyline(presentation_id, workflow_run_id=workflow_run_id)
            st.success(f"{regenerate_success_label('Storyline')}请审核后继续。")
            st.rerun()
        except Exception as exc:
            st.error(regenerate_failure_label("Storyline").format(error=exc))

    if outline_status == ApprovalStatus.REJECTED and cols[2].button(
        regenerate_label("OutlinePlan"),
        key=f"regen_outline_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_outline_plan(presentation_id, workflow_run_id=workflow_run_id)
            st.success(f"{regenerate_success_label('OutlinePlan')}请审核后继续。")
            st.rerun()
        except Exception as exc:
            st.error(regenerate_failure_label("OutlinePlan").format(error=exc))

    if slides_need_revision and cols[3].button(
        regenerate_label("SlideSpec"),
        key=f"regen_slides_{presentation_id}",
        use_container_width=True,
    ):
        try:
            regenerate_slide_plan(presentation_id, workflow_run_id=workflow_run_id)
            st.success(f"{regenerate_success_label('SlideSpec')}请审核后继续。")
            st.rerun()
        except Exception as exc:
            st.error(regenerate_failure_label("SlideSpec").format(error=exc))


def _render_brief_editor(context_presentation_id: UUID, workflow_run_id: UUID | None) -> None:
    with get_session() as session:
        review_service = PresentationReviewService(session)
        context = review_service.get_review_context(
            context_presentation_id,
            workflow_run_id=workflow_run_id,
        )
    if context is None or context.brief is None:
        st.caption(f"当前没有可编辑的 {_BRIEF_LABEL}。")
        return

    brief = context.brief
    st.markdown(f"**{_BRIEF_LABEL} 审核** · 状态：{_approval_badge(brief.approval_status)}")

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
        approve_clicked = col2.form_submit_button(f"批准 {_BRIEF_LABEL}", use_container_width=True)
        reject_clicked = col3.form_submit_button(f"驳回 {_BRIEF_LABEL}", use_container_width=True)

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
        st.success(f"{_BRIEF_LABEL} 已更新。")
        st.rerun()

    render_brief_history_panel(brief_id=brief.id)


def _manuscript_status_badge(status: ManuscriptStatus) -> str:
    if status == ManuscriptStatus.READY:
        return "✅ 已批准"
    if status == ManuscriptStatus.SUPERSEDED:
        return "⏭ 已替代"
    return "⏳ 待审核"


def _render_manuscript_editor(context_presentation_id: UUID, workflow_run_id: UUID | None) -> None:
    with get_session() as session:
        review_service = PresentationReviewService(session)
        context = review_service.get_review_context(
            context_presentation_id,
            workflow_run_id=workflow_run_id,
        )

    if context is None or context.manuscript is None:
        st.caption(f"当前没有可审核的 {_MANUSCRIPT_LABEL}。")
        return

    manuscript = context.manuscript
    st.markdown(
        f"**{_MANUSCRIPT_LABEL} 审核** · 状态：{_manuscript_status_badge(manuscript.status)}"
    )
    st.text_input("标题", value=manuscript.title, disabled=True)
    st.text_area("项目摘要", value=manuscript.project_summary, disabled=True)
    st.text_area("叙事论点", value=manuscript.narrative_thesis, disabled=True)
    st.caption(
        f"已验证事实 {len(manuscript.verified_facts)} 条 · "
        f"证据 {len(manuscript.evidence_catalog)} 项 · "
        f"章节 {len(manuscript.sections)} 个"
    )
    if manuscript.missing_information:
        with st.expander("缺失信息", expanded=False):
            for item in manuscript.missing_information[:20]:
                st.write(f"- {item}")
    if manuscript.unsupported_claims:
        with st.expander("未支持主张", expanded=False):
            for item in manuscript.unsupported_claims[:20]:
                st.write(f"- {item}")

    if manuscript.status == ManuscriptStatus.READY:
        st.success(f"{_MANUSCRIPT_LABEL} 已批准，设计阶段将只读取手稿内容。")
        return

    col1, col2 = st.columns(2)
    approve_clicked = col1.button(
        f"批准 {_MANUSCRIPT_LABEL}",
        key=f"approve_manuscript_{manuscript.id}",
        use_container_width=True,
    )
    if approve_clicked:
        with get_session() as session:
            PresentationReviewService(session).approve_manuscript(manuscript.id)
            session.commit()
        st.success(f"{_MANUSCRIPT_LABEL} 已批准。")
        st.rerun()


def _render_storyline_editor(context_presentation_id: UUID, workflow_run_id: UUID | None) -> None:
    with get_session() as session:
        review_service = PresentationReviewService(session)
        context = review_service.get_review_context(
            context_presentation_id,
            workflow_run_id=workflow_run_id,
        )
    if context is None or context.storyline is None:
        st.caption(f"当前没有可编辑的 {_STORYLINE_LABEL}。")
        return

    storyline = context.storyline
    st.markdown(f"**{_STORYLINE_LABEL} 审核** · 状态：{_approval_badge(storyline.approval_status)}")

    arc = storyline.narrative_arc
    with st.form(f"storyline_meta_{storyline.id}"):
        thesis = st.text_area("总体论点", value=storyline.thesis)
        narrative_pattern = st.text_input("叙事模式", value=storyline.narrative_pattern)
        st.caption("叙事弧线（先定论证骨架，再排章节）")
        opening_context = st.text_area(
            "开场背景",
            value=arc.opening_context if arc else "",
            height=68,
        )
        central_problem = st.text_area(
            "核心问题",
            value=arc.central_problem if arc else "",
            height=68,
        )
        tension_building = st.text_area(
            "矛盾升级（每行一条）",
            value="\n".join(arc.tension_building) if arc else "",
            height=68,
        )
        turning_point = st.text_area(
            "转折点",
            value=arc.turning_point if arc else "",
            height=68,
        )
        proposed_resolution = st.text_area(
            "解决方案",
            value=arc.proposed_resolution if arc else "",
            height=68,
        )
        final_decision = st.text_area(
            "最终决策（可选）",
            value=arc.final_decision if arc and arc.final_decision else "",
            height=68,
        )
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
    save_clicked = col1.button(
        f"保存 {_STORYLINE_LABEL}",
        key=f"save_storyline_{storyline.id}",
        use_container_width=True,
    )
    approve_clicked = col2.button(
        f"批准 {_STORYLINE_LABEL}",
        key=f"approve_storyline_{storyline.id}",
        use_container_width=True,
    )
    reject_clicked = col3.button(
        f"驳回 {_STORYLINE_LABEL}",
        key=f"reject_storyline_{storyline.id}",
        use_container_width=True,
    )

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
            narrative_arc=_narrative_arc_update_from_form(
                opening_context=opening_context,
                central_problem=central_problem,
                tension_building=tension_building,
                turning_point=turning_point,
                proposed_resolution=proposed_resolution,
                final_decision=final_decision,
            ),
        )
        with get_session() as session:
            review_service = PresentationReviewService(session)
            review_service.update_storyline(storyline.id, update)
            if approve_clicked:
                review_service.approve_storyline(storyline.id)
            elif reject_clicked:
                review_service.reject_storyline(storyline.id)
        st.success(f"{_STORYLINE_LABEL} 已更新。")
        st.rerun()

    render_storyline_history_panel(storyline_id=storyline.id)


def _render_outline_editor(context_presentation_id: UUID, workflow_run_id: UUID | None) -> None:
    with get_session() as session:
        review_service = PresentationReviewService(session)
        context = review_service.get_review_context(
            context_presentation_id,
            workflow_run_id=workflow_run_id,
        )
    if context is None or context.outline is None:
        st.caption(f"当前没有可编辑的 {_OUTLINE_LABEL}。")
        return

    outline = context.outline
    st.markdown(
        f"**{_OUTLINE_LABEL} 审核** · 状态：{_approval_badge(outline.approval_status)} · "
        f"预计 {outline.estimated_slide_total} 页"
    )

    with st.form(f"outline_meta_{outline.id}"):
        thesis = st.text_area("总体论点", value=outline.thesis)
        audience_mode = st.selectbox(
            "受众模式",
            options=list(AUDIENCE_MODE_LABELS.keys()),
            format_func=lambda m: AUDIENCE_MODE_LABELS[m],
            index=list(AUDIENCE_MODE_LABELS.keys()).index(outline.audience_mode),
        )
        meta_submit = st.form_submit_button("保存大纲元信息", use_container_width=True)

    section_rows = [
        {
            "id": section.id,
            "title": section.title,
            "purpose": section.purpose,
            "key_message": section.key_message,
            "order": section.order,
            "estimated_slide_count": section.estimated_slide_count,
            "required": section.required,
            "expanded": section.expanded,
            "category": section.category,
        }
        for section in sorted(outline.sections, key=lambda item: item.order)
    ]
    edited = st.data_editor(
        pd.DataFrame(section_rows),
        num_rows="dynamic",
        use_container_width=True,
        key=f"outline_sections_{outline.id}",
    )

    st.markdown("**逐页意图卡（Slide Intent Card）**")
    st.caption("为每一页单独设定任务、中心结论、必用证据/素材、禁止内容与期望版式。")
    intent_rows = _outline_intent_rows(outline)
    edited_intents = st.data_editor(
        pd.DataFrame(intent_rows),
        num_rows="dynamic",
        use_container_width=True,
        key=f"outline_page_intents_{outline.id}",
        column_config={
            "order": st.column_config.NumberColumn("页序", min_value=0, step=1),
            "page_task": st.column_config.TextColumn("页面任务", width="medium"),
            "central_conclusion": st.column_config.TextColumn("中心结论", width="large"),
            "required_evidence": st.column_config.TextColumn("必须证据", width="medium"),
            "required_assets": st.column_config.TextColumn("指定素材", width="medium"),
            "forbidden_content": st.column_config.TextColumn("禁止内容", width="medium"),
            "expected_layout": st.column_config.TextColumn("期望版式", width="small"),
            "notes": st.column_config.TextColumn("备注", width="medium"),
            "chapter_id": st.column_config.TextColumn("章节ID", width="small"),
        },
    )

    col1, col2, col3, col4 = st.columns(4)
    save_clicked = col1.button(f"保存 {_OUTLINE_LABEL}", key=f"save_outline_{outline.id}", use_container_width=True)
    approve_clicked = col2.button(f"批准 {_OUTLINE_LABEL}", key=f"approve_outline_{outline.id}", use_container_width=True)
    reject_clicked = col3.button(f"驳回 {_OUTLINE_LABEL}", key=f"reject_outline_{outline.id}", use_container_width=True)
    reorder_clicked = col4.button("按受众重排", key=f"reorder_outline_{outline.id}", use_container_width=True)

    if meta_submit or save_clicked or approve_clicked or reject_clicked or reorder_clicked:
        existing_by_id = {section.id: section for section in outline.sections}
        sections = [
            OutlineSectionUpdate(
                id=str(row["id"]),
                title=str(row["title"]),
                purpose=str(row["purpose"]),
                key_message=str(row["key_message"]),
                order=int(row["order"]),
                estimated_slide_count=int(row["estimated_slide_count"]),
                required=bool(row.get("required", True)),
                expanded=bool(row.get("expanded", True)),
                category=str(row.get("category", "general")),
                evidence_requirements=list(
                    existing_by_id[str(row["id"])].evidence_requirements
                )
                if str(row["id"]) in existing_by_id
                else [],
                required_assets=list(existing_by_id[str(row["id"])].required_assets)
                if str(row["id"]) in existing_by_id
                else [],
                narrative_position=_narrative_position_update_from_section(
                    existing_by_id.get(str(row["id"]))
                ),
            )
            for row in edited.to_dict(orient="records")
            if str(row.get("id", "")).strip()
        ]
        page_intents = _slide_intent_updates_from_editor(edited_intents)
        page_asset_bindings = _slide_asset_binding_updates_from_outline(outline)
        update = OutlineUpdate(
            title=outline.title,
            thesis=thesis,
            audience=outline.audience,
            purpose=outline.purpose,
            target_slide_count=outline.target_slide_count,
            audience_mode=audience_mode.value,
            sections=sections,
            page_intents=page_intents,
            page_asset_bindings=page_asset_bindings,
        )
        with get_session() as session:
            review_service = PresentationReviewService(session)
            saved = review_service.update_outline(outline.id, update)
            if reorder_clicked:
                saved = apply_audience_mode(saved, audience_mode)
                review_service.update_outline(
                    saved.id,
                    OutlineUpdate(
                        title=saved.title,
                        thesis=saved.thesis,
                        audience=saved.audience,
                        purpose=saved.purpose,
                        target_slide_count=saved.target_slide_count,
                        audience_mode=saved.audience_mode.value,
                        sections=[
                            OutlineSectionUpdate(
                                id=s.id,
                                title=s.title,
                                purpose=s.purpose,
                                key_message=s.key_message,
                                order=s.order,
                                estimated_slide_count=s.estimated_slide_count,
                                evidence_requirements=list(s.evidence_requirements),
                                required_assets=list(s.required_assets),
                                required=s.required,
                                expanded=s.expanded,
                                category=s.category,
                                narrative_position=_narrative_position_update_from_section(s),
                            )
                            for s in saved.sections
                        ],
                        page_intents=[
                            SlideIntentUpdate(
                                order=intent.order,
                                chapter_id=intent.chapter_id,
                                page_task=intent.page_task,
                                central_conclusion=intent.central_conclusion,
                                required_evidence=list(intent.required_evidence),
                                required_assets=list(intent.required_assets),
                                forbidden_content=list(intent.forbidden_content),
                                expected_layout=intent.expected_layout,
                                notes=intent.notes,
                            )
                            for intent in saved.page_intents
                        ],
                        page_asset_bindings=_slide_asset_binding_updates_from_outline(saved),
                    ),
                )
            if approve_clicked:
                review_service.approve_outline(outline.id)
            elif reject_clicked:
                review_service.reject_outline(outline.id)
        st.success(f"{_OUTLINE_LABEL} 已更新。")
        st.rerun()

    _render_page_asset_binding_editor(
        outline=outline,
        project_id=context.presentation.project_id,
    )


def _render_slides_editor(context_presentation_id: UUID, workflow_run_id: UUID | None) -> None:
    with get_session() as session:
        review_service = PresentationReviewService(session)
        context = review_service.get_review_context(
            context_presentation_id,
            workflow_run_id=workflow_run_id,
        )
    if context is None or not context.slides:
        st.caption(f"当前没有可编辑的 {_SLIDE_LABEL}。")
        return

    approved_count = sum(1 for slide in context.slides if slide.status == SlideStatus.APPROVED)
    st.markdown(f"**{_SLIDE_LABEL} 审核** · 已通过 {approved_count}/{len(context.slides)} 页")

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
        regenerate_label("SlideSpec"),
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
        st.success(f"{_SLIDE_LABEL} 已保存。")
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
            st.success(regenerate_success_label("SlideSpec"))
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
            ReviewLayer.SEMANTIC,
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

    open_export_blockers = export_blocking_open_issues(all_issues)
    if open_export_blockers and settings.block_export_on_critical_review:
        st.error(
            f"存在 {_export_block_summary(open_export_blockers)}未处理的阻断问题，"
            "已阻断 JSON/Marp 导出。请处理后重新运行或继续工作流。"
        )
        _render_critical_recovery_actions(
            presentation_id=presentation_id,
            workflow_run_id=workflow_run_id,
            open_critical=open_export_blockers,
        )
    elif open_export_blockers:
        st.warning(
            f"存在 {_export_block_summary(open_export_blockers)}阻断问题（当前未启用导出阻断）。"
        )
        _render_critical_recovery_actions(
            presentation_id=presentation_id,
            workflow_run_id=workflow_run_id,
            open_critical=open_export_blockers,
        )

    rows = [
        {
            "id": str(issue.id),
            "layer": LAYER_LABELS.get(issue.reviewer_layer, issue.reviewer_layer.value),
            "page": _issue_slide_label(issue, slides_by_id),
            "severity": _severity_table_label(issue.severity),
            "category": CATEGORY_LABELS.get(issue.category, issue.category.value),
            "rule_code": issue.rule_code,
            "title": issue.title,
            "confidence": issue.confidence,
            "requires_confirmation": issue.requires_confirmation,
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
            f"{_severity_badge_html(issue.severity)} · "
            f"{issue.title}{page_hint} — {issue.description}",
            unsafe_allow_html=True,
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
            st.toast(f"已定位到 {_issue_slide_label(issue, slides_by_id)}，请切换到 {_SLIDE_LABEL} 标签页。")
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
        outline_status=context.outline.approval_status if context.outline else None,
        slides_need_revision=slides_need_revision
        or (context.slides_pending_review and context.review_gate == "slides"),
    )

    if context.slides:
        step = None
        if context.workflow_run is not None:
            step = (context.workflow_run.state or {}).get("current_step")
        render_page_status_board(
            presentation_id=presentation_id,
            project_id=context.presentation.project_id,
            workflow_run_id=workflow_run_id,
            workflow_step=str(step) if step else None,
            key_prefix=f"review_page_status_{presentation_id}",
        )

    tab_labels = [_BRIEF_LABEL, _STORYLINE_LABEL, _OUTLINE_LABEL, _SLIDE_LABEL, _ASSET_BOARD_LABEL, "质量审核"]
    if context.manuscript is not None:
        tab_labels.insert(1, _MANUSCRIPT_LABEL)
    tabs = st.tabs(tab_labels)
    tab_index = 0
    with tabs[tab_index]:
        _render_brief_editor(presentation_id, workflow_run_id)
    tab_index += 1
    if context.manuscript is not None:
        with tabs[tab_index]:
            _render_manuscript_editor(presentation_id, workflow_run_id)
        tab_index += 1
    with tabs[tab_index]:
        _render_storyline_editor(presentation_id, workflow_run_id)
    tab_index += 1
    with tabs[tab_index]:
        _render_outline_editor(presentation_id, workflow_run_id)
    tab_index += 1
    with tabs[tab_index]:
        _render_slides_editor(presentation_id, workflow_run_id)
    tab_index += 1
    with tabs[tab_index]:
        render_asset_board_panel(
            project_id=context.presentation.project_id,
            presentation_id=presentation_id,
        )
    tab_index += 1
    with tabs[tab_index]:
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
        project_id = context.presentation.project_id
        settings = get_settings()
        if background_workflows_enabled(settings):
            job = submit_continue_after_review(
                project_id,
                workflow_run_id,
                settings=settings,
            )
            set_active_job_id(project_id, job.job_id)
            st.info("已在后台继续运行工作流，请查看进度。")
            render_workflow_progress_panel(project_id, job_id=job.job_id)
            return
        try:
            from archium.ui.workspace_service import continue_workflow_after_review

            result = continue_workflow_after_review(workflow_run_id, settings=settings)
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

def _narrative_arc_update_from_form(
    *,
    opening_context: str,
    central_problem: str,
    tension_building: str,
    turning_point: str,
    proposed_resolution: str,
    final_decision: str,
) -> NarrativeArcUpdate | None:
    opening = opening_context.strip()
    problem = central_problem.strip()
    turning = turning_point.strip()
    resolution = proposed_resolution.strip()
    if not (opening and problem and turning and resolution):
        return None
    decision = final_decision.strip()
    return NarrativeArcUpdate(
        opening_context=opening,
        central_problem=problem,
        tension_building=parse_multiline_items(tension_building),
        turning_point=turning,
        proposed_resolution=resolution,
        final_decision=decision or None,
    )


def _narrative_position_update_from_section(section: object | None) -> NarrativePositionUpdate | None:
    if section is None:
        return None
    position = getattr(section, 'narrative_position', None)
    if position is None:
        return None
    return NarrativePositionUpdate(
        stage=position.stage.value,
        advances_from_previous=position.advances_from_previous,
        prepares_for_next=position.prepares_for_next,
    )


def _join_list_items(items: list[str]) -> str:
    return "、".join(item for item in items if item.strip())


def _outline_intent_rows(outline: object) -> list[dict[str, object]]:
    intents = list(getattr(outline, "page_intents", []) or [])
    if intents:
        return [
            {
                "order": intent.order,
                "chapter_id": intent.chapter_id,
                "page_task": intent.page_task,
                "central_conclusion": intent.central_conclusion,
                "required_evidence": _join_list_items(list(intent.required_evidence)),
                "required_assets": _join_list_items(list(intent.required_assets)),
                "forbidden_content": _join_list_items(list(intent.forbidden_content)),
                "expected_layout": intent.expected_layout,
                "notes": intent.notes,
            }
            for intent in sorted(intents, key=lambda item: item.order)
        ]
    target = int(getattr(outline, "target_slide_count", 0) or 0)
    return [
        {
            "order": index,
            "chapter_id": "",
            "page_task": "",
            "central_conclusion": "",
            "required_evidence": "",
            "required_assets": "",
            "forbidden_content": "",
            "expected_layout": "",
            "notes": "",
        }
        for index in range(target)
    ]


def _slide_intent_updates_from_editor(edited_intents: pd.DataFrame) -> list[SlideIntentUpdate]:
    updates: list[SlideIntentUpdate] = []
    for row in edited_intents.to_dict(orient="records"):
        page_task = str(row.get("page_task", "") or "").strip()
        central = str(row.get("central_conclusion", "") or "").strip()
        notes = str(row.get("notes", "") or "").strip()
        if not (page_task or central or notes):
            continue
        updates.append(
            SlideIntentUpdate(
                order=int(row.get("order", 0) or 0),
                chapter_id=str(row.get("chapter_id", "") or "").strip(),
                page_task=page_task or central or notes,
                central_conclusion=central,
                required_evidence=parse_multiline_items(str(row.get("required_evidence", "") or "")),
                required_assets=parse_multiline_items(str(row.get("required_assets", "") or "")),
                forbidden_content=parse_multiline_items(str(row.get("forbidden_content", "") or "")),
                expected_layout=str(row.get("expected_layout", "") or "").strip(),
                notes=notes,
            )
        )
    return updates


_BINDING_ROLE_LABELS = {
    SlideAssetBindingRole.PRIMARY_DRAWING: "主图纸",
    SlideAssetBindingRole.PROJECT_PHOTO: "项目照片",
    SlideAssetBindingRole.SUPPORTING_PHOTO: "辅助照片",
    SlideAssetBindingRole.REFERENCE_CASE: "参考案例",
    SlideAssetBindingRole.METRIC_SOURCE: "指标数据源",
    SlideAssetBindingRole.BACKGROUND: "背景",
    SlideAssetBindingRole.LOGO: "Logo",
}


def _slide_asset_binding_updates_from_outline(outline: object) -> list[SlideAssetBindingUpdate]:
    return [
        SlideAssetBindingUpdate(
            page_order=binding.page_order,
            asset_id=str(binding.asset_id),
            binding_role=binding.binding_role.value,
            user_description=binding.user_description,
            required=binding.required,
            slide_id=str(binding.slide_id) if binding.slide_id else None,
        )
        for binding in list(getattr(outline, "page_asset_bindings", []) or [])
    ]


def _render_page_asset_binding_editor(*, outline: object, project_id: UUID) -> None:
    from archium.application.asset_provenance import format_asset_option_label
    from archium.infrastructure.database.repositories import AssetRepository

    st.markdown("**页面素材绑定（page_materials）**")
    st.caption("把项目素材显式绑到某一页；生成与匹配时优先尊重这些绑定，而不是让 AI 猜测。")

    with get_session() as session:
        assets = AssetRepository(session).list_by_project(project_id)
    assets_by_id = {asset.id: asset for asset in assets}

    bindings = list(getattr(outline, "page_asset_bindings", []) or [])
    if bindings:
        rows = []
        for index, binding in enumerate(
            sorted(bindings, key=lambda item: (item.page_order, item.binding_role.value))
        ):
            asset = assets_by_id.get(binding.asset_id)
            rows.append(
                {
                    "index": index,
                    "页序": binding.page_order,
                    "角色": _BINDING_ROLE_LABELS.get(binding.binding_role, binding.binding_role.value),
                    "素材": asset.filename if asset is not None else str(binding.asset_id),
                    "说明": binding.user_description or "—",
                    "必用": "是" if binding.required else "否",
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)

        remove_options = {
            str(index): (
                f"p{row['页序'] + 1} · {row['角色']} · {row['素材']}"
            )
            for index, row in enumerate(rows)
        }
        remove_key = st.selectbox(
            "移除绑定",
            options=[""] + list(remove_options.keys()),
            format_func=lambda value: "— 选择 —" if value == "" else remove_options[value],
            key=f"remove_binding_{getattr(outline, 'id', 'outline')}",
        )
        if st.button("删除所选绑定", key=f"delete_binding_{getattr(outline, 'id', 'outline')}"):
            if remove_key:
                remaining = [
                    binding
                    for index, binding in enumerate(
                        sorted(bindings, key=lambda item: (item.page_order, item.binding_role.value))
                    )
                    if str(index) != remove_key
                ]
                with get_session() as session:
                    PresentationReviewService(session).update_page_asset_bindings(
                        getattr(outline, "id"),
                        [
                            SlideAssetBindingUpdate(
                                page_order=item.page_order,
                                asset_id=str(item.asset_id),
                                binding_role=item.binding_role.value,
                                user_description=item.user_description,
                                required=item.required,
                                slide_id=str(item.slide_id) if item.slide_id else None,
                            )
                            for item in remaining
                        ],
                    )
                st.success("已删除素材绑定。")
                st.rerun()
    else:
        st.info("尚未绑定页面素材。从下方把素材挂到指定页序。")

    if not assets:
        st.warning("当前项目还没有可绑定的素材，请先上传图纸/照片/图表。")
        return

    st.markdown("添加绑定")
    asset_options = {str(asset.id): format_asset_option_label(asset) for asset in assets}
    col1, col2 = st.columns(2)
    page_order = col1.number_input(
        "页序（从 0 起）",
        min_value=0,
        max_value=max(int(getattr(outline, "target_slide_count", 1)) - 1, 0),
        value=0,
        step=1,
        key=f"bind_page_order_{getattr(outline, 'id', 'outline')}",
    )
    role = col2.selectbox(
        "绑定角色",
        options=list(SlideAssetBindingRole),
        format_func=lambda value: _BINDING_ROLE_LABELS.get(value, value.value),
        key=f"bind_role_{getattr(outline, 'id', 'outline')}",
    )
    asset_id = st.selectbox(
        "项目素材",
        options=list(asset_options.keys()),
        format_func=lambda value: asset_options[value],
        key=f"bind_asset_{getattr(outline, 'id', 'outline')}",
    )
    description = st.text_input(
        "素材说明（给生成模型）",
        value="",
        key=f"bind_desc_{getattr(outline, 'id', 'outline')}",
    )
    required = st.checkbox(
        "必用（禁止自动匹配覆盖）",
        value=True,
        key=f"bind_required_{getattr(outline, 'id', 'outline')}",
    )
    if st.button("绑定到该页", key=f"add_binding_{getattr(outline, 'id', 'outline')}", use_container_width=True):
        updates = _slide_asset_binding_updates_from_outline(outline)
        updates.append(
            SlideAssetBindingUpdate(
                page_order=int(page_order),
                asset_id=str(asset_id),
                binding_role=role.value,
                user_description=description.strip(),
                required=bool(required),
            )
        )
        with get_session() as session:
            PresentationReviewService(session).update_page_asset_bindings(
                getattr(outline, "id"),
                updates,
            )
        st.success(f"已将素材绑定到第 {int(page_order) + 1} 页。")
        st.rerun()


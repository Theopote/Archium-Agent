"""Streamlit UI for manual architectural slide benchmark reviews."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from archium.application.architectural_benchmark_review_store import (
    BenchmarkCaseSummary,
    CaseReviewStatus,
    benchmark_report_paths,
    list_benchmark_cases,
    list_case_review_statuses,
    load_case_review,
    regenerate_benchmark_report,
    review_progress,
    review_progress_by_category,
    save_case_review,
)
from archium.domain.visual.benchmark import (
    HUMAN_REVIEW_MAX_SCORE,
    HUMAN_REVIEW_MIN_SCORE,
    HUMAN_REVIEW_PASS_THRESHOLD,
    HUMAN_REVIEW_PENDING_LABEL,
    HumanVisualReview,
    HumanVisualReviewSource,
)
from archium.ui.studio.human_review_panel import REVIEW_DIMENSION_LABELS

_SESSION_REVIEWER_KEY = "benchmark_default_reviewer"
_SESSION_AUTO_REGEN_KEY = "benchmark_auto_regen_report"
_SESSION_SELECTED_CASE_KEY = "benchmark_review_selected_case"


def render_benchmark_review_panel() -> None:
    st.markdown("### 建筑幻灯片基准 · 人工视觉评审")
    st.caption(
        "逐项查看 `preview.png` 并填写 9 维评分。保存后写入各 case 的 `human_review.json`（`source=manual`）。"
        "占位评审在报告中显示为「待人工评审」，不会计入可交付统计。"
    )

    progress = review_progress()
    _render_progress_header(progress)
    _render_report_links()

    statuses = list_case_review_statuses()
    with st.expander("评审总览（30 页）", expanded=False):
        _render_overview_table(statuses)
        _render_category_breakdown()

    cases = list_benchmark_cases()
    if not cases:
        st.warning("未找到 benchmark case 目录。")
        return

    filter_cols = st.columns([1.2, 1, 1])
    filter_mode = filter_cols[0].radio(
        "筛选",
        options=["待评审", "已评审（未接受）", "已接受", "全部"],
        horizontal=True,
        key="benchmark_review_filter",
    )
    categories = sorted({case.category for case in cases})
    category_filter = filter_cols[1].selectbox(
        "分类",
        options=["全部", *categories],
        key="benchmark_review_category_filter",
    )
    if filter_cols[2].button("从第一个待评审开始", use_container_width=True):
        pending_ids = [status.case_id for status in statuses if status.pending]
        if pending_ids:
            st.session_state[_SESSION_SELECTED_CASE_KEY] = pending_ids[0]
            st.rerun()
        st.info("当前没有待评审 case。")

    filtered = _filter_cases(cases, statuses, filter_mode, category_filter)
    if not filtered:
        st.info(f"「{filter_mode}」+「{category_filter}」筛选下暂无 case。")
        return

    case_ids = [case.case_id for case in filtered]
    labels = {case.case_id: f"{case.case_id} · {case.title}" for case in filtered}
    selected_id = st.selectbox(
        "选择 Case",
        options=case_ids,
        format_func=lambda value: labels[value],
        key=_SESSION_SELECTED_CASE_KEY,
    )
    selected = next(case for case in filtered if case.case_id == selected_id)
    existing = load_case_review(selected_id)
    selected_index = case_ids.index(selected_id)

    nav_cols = st.columns([1, 2, 1])
    if nav_cols[0].button(
        "← 上一页",
        disabled=selected_index <= 0,
        use_container_width=True,
        key="benchmark_review_prev_case",
    ):
        st.session_state[_SESSION_SELECTED_CASE_KEY] = case_ids[selected_index - 1]
        st.rerun()
    nav_cols[1].caption(
        f"当前 {selected_index + 1} / {len(case_ids)} · "
        f"全局 {progress['manual_review_count']} 页已评审 · "
        f"{progress['manual_accepted_count']} 页可交付"
    )
    if nav_cols[2].button(
        "下一页 →",
        disabled=selected_index >= len(case_ids) - 1,
        use_container_width=True,
        key="benchmark_review_next_case",
    ):
        st.session_state[_SESSION_SELECTED_CASE_KEY] = case_ids[selected_index + 1]
        st.rerun()

    preview_col, form_col = st.columns([1.1, 1])
    _render_case_preview(preview_col, selected, existing)
    _handle_review_form(form_col, selected, existing, case_ids, selected_index)


def _render_progress_header(progress: dict[str, int]) -> None:
    case_count = max(progress["case_count"], 1)
    review_ratio = progress["manual_review_count"] / case_count
    accepted_ratio = progress["manual_accepted_count"] / case_count

    metric_cols = st.columns(5)
    metric_cols[0].metric("Case 总数", progress["case_count"])
    metric_cols[1].metric("已人工评审", progress["manual_review_count"])
    metric_cols[2].metric("可交付（人工）", progress["manual_accepted_count"])
    metric_cols[3].metric("待评审", progress["placeholder_count"])
    gate_passed = (
        progress["case_count"] > 0
        and progress["manual_accepted_count"] == progress["case_count"]
    )
    metric_cols[4].metric(
        "人工质量门禁",
        "通过" if gate_passed and progress["case_count"] > 0 else "未通过",
    )

    st.caption(f"评审进度 {progress['manual_review_count']} / {progress['case_count']}")
    st.progress(min(1.0, review_ratio))
    st.caption(f"可交付进度 {progress['manual_accepted_count']} / {progress['case_count']}")
    st.progress(min(1.0, accepted_ratio))

    if progress["manual_accepted_count"] == 0:
        st.info(
            "当前尚无真实人工评审通过页。"
            "在 `manual_human_accepted_count > 0` 之前，不能宣称 Benchmark 人工质量全面通过。"
        )


def _render_report_links() -> None:
    html_path, json_path = benchmark_report_paths()
    link_cols = st.columns([1, 1, 2])
    if html_path.is_file():
        link_cols[0].markdown(f"[打开 HTML 报告]({html_path.as_uri()})")
    else:
        link_cols[0].caption("HTML 报告尚未生成")
    if json_path.is_file():
        link_cols[1].caption(f"Summary：`{json_path.name}`")
    st.checkbox(
        "保存后自动更新 benchmark 报告",
        value=bool(st.session_state.get(_SESSION_AUTO_REGEN_KEY, True)),
        key=_SESSION_AUTO_REGEN_KEY,
    )


def _render_overview_table(statuses: list[CaseReviewStatus]) -> None:
    rows = [
        {
            "Case": status.case_id,
            "标题": status.title,
            "分类": status.category,
            "状态": _status_label(status),
            "综合分": status.human_score_label,
            "达阈值": (
                "是"
                if status.passes_threshold
                else "否"
                if status.passes_threshold is not None
                else "—"
            ),
            "可交付": "是" if status.accepted_for_delivery else "否",
            "评审人": status.reviewer or "—",
        }
        for status in statuses
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_category_breakdown() -> None:
    breakdown = review_progress_by_category()
    if not breakdown:
        return
    st.markdown("**分类进度**")
    for category, stats in sorted(breakdown.items()):
        case_count = max(stats["case_count"], 1)
        st.caption(
            f"{category}：评审 {stats['manual_review_count']}/{case_count} · "
            f"可交付 {stats['manual_accepted_count']}/{case_count}"
        )


def _status_label(status: CaseReviewStatus) -> str:
    if status.pending:
        return HUMAN_REVIEW_PENDING_LABEL
    if status.accepted_for_delivery:
        return "可交付"
    return "已评审"


def _filter_cases(
    cases: list[BenchmarkCaseSummary],
    statuses: list[CaseReviewStatus],
    filter_mode: str,
    category_filter: str,
) -> list[BenchmarkCaseSummary]:
    status_by_id = {status.case_id: status for status in statuses}
    filtered: list[BenchmarkCaseSummary] = []
    for case in cases:
        if category_filter != "全部" and case.category != category_filter:
            continue
        status = status_by_id[case.case_id]
        if filter_mode == "全部":
            filtered.append(case)
            continue
        if filter_mode == "待评审" and status.pending or filter_mode == "已接受" and status.accepted_for_delivery or (
            filter_mode == "已评审（未接受）"
            and not status.pending
            and not status.accepted_for_delivery
        ):
            filtered.append(case)
    return filtered


def _render_case_preview(
    column: st.delta_generator.DeltaGenerator,
    case: BenchmarkCaseSummary,
    review: HumanVisualReview | None,
) -> None:
    with column:
        if case.preview_path.is_file():
            column.image(str(case.preview_path), caption=case.title, use_container_width=True)
        else:
            column.warning(f"缺少预览图：{case.preview_path}")

        column.markdown(f"**页面类型：** {case.page_type}")
        column.markdown(f"**分类：** {case.category}")
        column.markdown(
            f"**版式：** `{case.layout_family}` / `{case.layout_variant}`"
        )
        if case.layout_score is not None:
            rule_label = "通过" if case.rule_passed else "未通过"
            column.caption(
                f"Layout 规则分 {case.layout_score:.3f} · {rule_label}"
            )
        if review is None:
            column.markdown(f"**人工评分：** {HUMAN_REVIEW_PENDING_LABEL}")
            return
        if review.is_scaffold_review():
            column.markdown(f"**人工评分：** {HUMAN_REVIEW_PENDING_LABEL}")
            column.caption(f"当前来源：{review.source.value}（占位/派生，不可用于验收）")
            return
        column.markdown(f"**人工评分：** {review.human_score_label()} / 5")
        if review.reviewer:
            column.caption(f"评审人：{review.reviewer}")
        if review.reviewed_at is not None:
            column.caption(f"评审时间：{review.reviewed_at.isoformat()}")


def _handle_review_form(
    column: st.delta_generator.DeltaGenerator,
    case: BenchmarkCaseSummary,
    existing: HumanVisualReview | None,
    case_ids: list[str],
    selected_index: int,
) -> None:
    with column:
        is_manual = existing is not None and existing.is_manual_review()
        if existing is not None and existing.is_scaffold_review():
            st.warning("当前为占位评审。请填写下方表单并保存，以替换为真实 manual 评审。")

        defaults = {
            field: getattr(existing, field, 4)
            for field in REVIEW_DIMENSION_LABELS
        }
        scores: dict[str, int] = {}
        for field, label in REVIEW_DIMENSION_LABELS.items():
            scores[field] = st.slider(
                label,
                min_value=HUMAN_REVIEW_MIN_SCORE,
                max_value=HUMAN_REVIEW_MAX_SCORE,
                value=int(defaults[field]),
                key=f"benchmark_human_review_{case.case_id}_{field}",
            )

        default_reviewer = ""
        if is_manual and existing is not None:
            default_reviewer = existing.reviewer
        elif st.session_state.get(_SESSION_REVIEWER_KEY):
            default_reviewer = str(st.session_state[_SESSION_REVIEWER_KEY])

        reviewer = st.text_input(
            "评审人",
            value=default_reviewer,
            placeholder="真实姓名或工号（保存后会记住，供后续 case 复用）",
            key=f"benchmark_human_reviewer_{case.case_id}",
        )
        major = st.text_area(
            "主要问题（每行一条）",
            value="\n".join(existing.major_problems if existing else []),
            height=72,
            key=f"benchmark_human_major_{case.case_id}",
        )
        minor = st.text_area(
            "次要问题（每行一条）",
            value="\n".join(existing.minor_problems if existing else []),
            height=72,
            key=f"benchmark_human_minor_{case.case_id}",
        )
        accepted_default = bool(existing.accepted) if is_manual and existing is not None else False
        accepted = st.checkbox(
            "本页可接受交付",
            value=accepted_default,
            key=f"benchmark_human_accept_{case.case_id}",
        )
        notes = st.text_input(
            "评审备注",
            value=existing.reviewer_notes if is_manual and existing is not None else "",
            key=f"benchmark_human_notes_{case.case_id}",
        )

        preview = HumanVisualReview(
            case_id=case.case_id,
            source=HumanVisualReviewSource.MANUAL,
            information_hierarchy=scores["information_hierarchy"],
            visual_focus=scores["visual_focus"],
            reading_order=scores["reading_order"],
            image_text_relationship=scores["image_text_relationship"],
            whitespace_density=scores["whitespace_density"],
            architectural_expression=scores["architectural_expression"],
            aesthetic_finish=scores["aesthetic_finish"],
            editability=scores["editability"],
            major_problems=[line.strip() for line in major.splitlines() if line.strip()],
            minor_problems=[line.strip() for line in minor.splitlines() if line.strip()],
            accepted=accepted,
            reviewer=reviewer.strip(),
            reviewed_at=datetime.now(UTC),
            reviewer_notes=notes.strip(),
        )
        st.caption(
            f"综合评分 {preview.weighted_score():.2f} / 5 · "
            f"{'通过' if preview.passes_threshold() else '未达'} "
            f"交付阈值 {HUMAN_REVIEW_PASS_THRESHOLD}"
        )

        save_cols = st.columns(2)
        save_clicked = save_cols[0].button(
            "保存人工评审",
            type="primary",
            use_container_width=True,
            key=f"benchmark_save_human_review_{case.case_id}",
        )
        save_next_clicked = save_cols[1].button(
            "保存并下一页",
            use_container_width=True,
            key=f"benchmark_save_next_human_review_{case.case_id}",
        )
        if save_clicked or save_next_clicked:
            _persist_review(
                preview,
                advance=save_next_clicked,
                case_ids=case_ids,
                selected_index=selected_index,
            )


def _persist_review(
    review: HumanVisualReview,
    *,
    advance: bool,
    case_ids: list[str],
    selected_index: int,
) -> None:
    saved_path = save_case_review(review)
    if review.reviewer:
        st.session_state[_SESSION_REVIEWER_KEY] = review.reviewer
    if st.session_state.get(_SESSION_AUTO_REGEN_KEY, True):
        with st.spinner("正在更新 benchmark 报告 …"):
            regenerate_benchmark_report()
    st.success(f"已保存至 `{saved_path.relative_to(saved_path.parents[2])}`")
    if advance and selected_index < len(case_ids) - 1:
        st.session_state[_SESSION_SELECTED_CASE_KEY] = case_ids[selected_index + 1]
    st.rerun()

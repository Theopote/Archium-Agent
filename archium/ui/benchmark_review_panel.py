"""Streamlit UI for manual architectural slide benchmark reviews."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from archium.application.architectural_benchmark_review_store import (
    BenchmarkCaseSummary,
    list_benchmark_cases,
    load_case_review,
    regenerate_benchmark_report,
    review_progress,
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


def render_benchmark_review_panel() -> None:
    st.markdown("### 建筑幻灯片基准 · 人工视觉评审")
    st.caption(
        "逐项查看 `preview.png` 并填写 9 维评分。保存后写入各 case 的 `human_review.json`（`source=manual`）。"
        "占位评审在报告中显示为「待人工评审」，不会计入可交付统计。"
    )

    progress = review_progress()
    st.progress(
        min(1.0, progress["manual_accepted_count"] / max(progress["case_count"], 1))
    )
    metric_cols = st.columns(4)
    metric_cols[0].metric("Case 总数", progress["case_count"])
    metric_cols[1].metric("已人工评审", progress["manual_review_count"])
    metric_cols[2].metric("可交付（人工）", progress["manual_accepted_count"])
    metric_cols[3].metric("待评审", progress["placeholder_count"])

    if progress["manual_accepted_count"] == 0:
        st.info(
            "当前尚无真实人工评审通过页。"
            "在 `manual_human_accepted_count > 0` 之前，不能宣称 Benchmark 人工质量全面通过。"
        )

    cases = list_benchmark_cases()
    if not cases:
        st.warning("未找到 benchmark case 目录。")
        return

    filter_mode = st.radio(
        "筛选",
        options=["待评审", "已接受", "全部"],
        horizontal=True,
        key="benchmark_review_filter",
    )
    filtered = _filter_cases(cases, filter_mode)
    if not filtered:
        st.info(f"「{filter_mode}」筛选下暂无 case。")
        return

    case_ids = [case.case_id for case in filtered]
    labels = {case.case_id: f"{case.case_id} · {case.title}" for case in filtered}
    selected_id = st.selectbox(
        "选择 Case",
        options=case_ids,
        format_func=lambda value: labels[value],
        key="benchmark_review_selected_case",
    )
    selected = next(case for case in filtered if case.case_id == selected_id)
    existing = load_case_review(selected_id)

    preview_col, form_col = st.columns([1.1, 1])
    _render_case_preview(preview_col, selected, existing)
    saved_path = _render_review_form(form_col, selected, existing)

    action_cols = st.columns([1, 1, 2])
    if action_cols[0].button("重新生成基准报告", use_container_width=True):
        with st.spinner("正在写入 benchmark-summary.json / benchmark-report.html …"):
            html_path, json_path = regenerate_benchmark_report()
        st.success(f"报告已更新：{json_path.name}、{html_path.name}")
    if saved_path is not None:
        action_cols[1].caption(f"上次保存：{saved_path.name}")


def _filter_cases(
    cases: list[BenchmarkCaseSummary],
    filter_mode: str,
) -> list[BenchmarkCaseSummary]:
    if filter_mode == "全部":
        return cases
    filtered: list[BenchmarkCaseSummary] = []
    for case in cases:
        review = load_case_review(case.case_id)
        is_manual = review is not None and review.is_manual_review()
        is_accepted = bool(review and review.accepted and is_manual)
        if (filter_mode == "待评审" and not is_manual) or (
            filter_mode == "已接受" and is_accepted
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


def _render_review_form(
    column: st.delta_generator.DeltaGenerator,
    case: BenchmarkCaseSummary,
    existing: HumanVisualReview | None,
) -> Path | None:
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

        reviewer = st.text_input(
            "评审人",
            value=existing.reviewer if is_manual else "",
            placeholder="真实姓名或工号",
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
        accepted_default = bool(existing.accepted if is_manual else False)
        accepted = st.checkbox(
            "本页可接受交付",
            value=accepted_default,
            key=f"benchmark_human_accept_{case.case_id}",
        )
        notes = st.text_input(
            "评审备注",
            value=existing.reviewer_notes if is_manual else "",
            key=f"benchmark_human_notes_{case.case_id}",
        )

        preview = HumanVisualReview(
            case_id=case.case_id,
            source=HumanVisualReviewSource.MANUAL,
            **scores,
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

        saved_path: Path | None = None
        if st.button(
            "保存人工评审",
            type="primary",
            use_container_width=True,
            key=f"benchmark_save_human_review_{case.case_id}",
        ):
            saved_path = save_case_review(preview)
            st.success(f"已保存至 `{saved_path.relative_to(saved_path.parents[2])}`")
            st.rerun()
        return saved_path

"""Streamlit UI for manual architectural slide benchmark reviews."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from archium.application.architectural_benchmark_review_store import (
    BenchmarkCaseSummary,
    CaseReviewStatus,
    build_human_review_export,
    benchmark_report_paths,
    default_human_review_export_path,
    export_human_review_bundle,
    import_human_review_bundle,
    list_benchmark_cases,
    list_case_review_statuses,
    load_case_editability_review,
    load_case_layout_review,
    load_case_review,
    regenerate_benchmark_report,
    review_progress,
    review_progress_by_category,
    save_case_editability_review,
    save_case_layout_review,
    save_case_review,
)
from archium.domain.visual.benchmark import (
    BENCHMARK_VISUAL_REVIEW_REQUIRES_FINAL_RENDER,
    HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD,
    HUMAN_REVIEW_FORMAL_MIN_ACCEPTED,
    HUMAN_REVIEW_INVALIDATED_LABEL,
    HUMAN_REVIEW_MAX_SCORE,
    HUMAN_REVIEW_MIN_SCORE,
    HUMAN_REVIEW_PASS_THRESHOLD,
    HUMAN_REVIEW_PENDING_LABEL,
    LAYOUT_REVIEW_PASS_THRESHOLD,
    EditabilityReview,
    HumanLayoutReview,
    HumanVisualReview,
    HumanVisualReviewSource,
)
from archium.ui.studio.human_review_panel import REVIEW_DIMENSION_LABELS

_SESSION_REVIEWER_KEY = "benchmark_default_reviewer"
_SESSION_AUTO_REGEN_KEY = "benchmark_auto_regen_report"
_SESSION_SELECTED_CASE_KEY = "benchmark_review_selected_case"

LAYOUT_REVIEW_DIMENSION_LABELS: dict[str, str] = {
    "information_hierarchy": "信息层级（几何）",
    "reading_order": "阅读顺序",
    "whitespace_density": "留白与密度",
    "spatial_balance": "空间平衡",
    "layout_clarity": "版式清晰度",
}

VISUAL_REVIEW_DIMENSION_LABELS: dict[str, str] = {
    key: label
    for key, label in REVIEW_DIMENSION_LABELS.items()
    if key != "editability"
}

EDITABILITY_REVIEW_DIMENSION_LABELS: dict[str, str] = {
    "text_editable": "文字可编辑",
    "image_replaceable": "图片可替换",
    "layer_independence": "图层独立",
    "chart_editable": "图表可编辑",
    "font_usability": "字体可用",
    "not_flattened": "非整页扁平",
    "selection_ease": "元素易选中",
    "modification_ease": "修改容易",
}


def render_benchmark_review_panel() -> None:
    st.markdown("### 建筑幻灯片基准 · 双层人工评审")
    st.caption(
        "Layout Geometry Benchmark：基于 `wireframe.png` 评价几何、留白与阅读顺序。"
        "Rendered Visual Benchmark：基于 `scene_preview.png` / `pptx_render.png` 评价真实视觉质量。"
        "PPTX 可编辑性单独在 `editability_review.json` 记录。"
    )
    st.warning(
        "此前基于线框 `preview.png` / `wireframe.png` 的视觉评分已作废（validity=invalid_render_artifact），"
        "不得计入交付统计。须在 `render_valid=true` 且存在真实渲染产物后重新评审。"
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
    existing_layout = load_case_layout_review(selected_id)
    existing_editability = load_case_editability_review(selected_id)
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
    _render_case_preview(preview_col, selected, existing, existing_layout)
    _handle_review_form(
        form_col,
        selected,
        existing,
        existing_layout,
        existing_editability,
        case_ids,
        selected_index,
    )


def _render_progress_header(progress: dict[str, int]) -> None:
    case_count = max(progress["case_count"], 1)
    review_ratio = progress["manual_review_count"] / case_count
    accepted_ratio = progress["manual_accepted_count"] / case_count
    export_bundle = build_human_review_export()

    metric_cols = st.columns(5)
    metric_cols[0].metric("Case 总数", progress["case_count"])
    metric_cols[1].metric("已人工评审", progress["manual_review_count"])
    metric_cols[2].metric("可交付（人工）", progress["manual_accepted_count"])
    metric_cols[3].metric("待评审", progress["placeholder_count"])
    gate_label = "通过" if export_bundle.human_quality_gate_passed else "未通过"
    avg = export_bundle.human_average_weighted_score
    metric_cols[4].metric(
        "正式人工门禁",
        gate_label,
        delta=f"均分 {avg:.2f}" if avg is not None else None,
    )

    st.caption(
        f"正式门槛：≥{HUMAN_REVIEW_FORMAL_MIN_ACCEPTED}/30 页 accepted · "
        f"均分 ≥ {HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD}"
    )
    if export_bundle.human_quality_gate_reasons:
        st.caption("；".join(export_bundle.human_quality_gate_reasons))

    st.caption(f"评审进度 {progress['manual_review_count']} / {progress['case_count']}")
    st.progress(min(1.0, review_ratio))
    st.caption(f"可交付进度 {progress['manual_accepted_count']} / {progress['case_count']}")
    st.progress(min(1.0, accepted_ratio))

    if progress["manual_review_count"] == 0:
        st.info(
            "当前尚无真实人工评审。"
            "保存 `source=manual` 评审后可导出集中 JSON，或从离线评审文件导入。"
        )


def _render_report_links() -> None:
    html_path, json_path = benchmark_report_paths()
    export_path = default_human_review_export_path()
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
    _render_export_import_panel(export_path)


def _render_export_import_panel(default_export_path: Path) -> None:
    import json

    with st.expander("导出 / 导入人工评审", expanded=False):
        bundle = build_human_review_export()
        payload = json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2)
        st.download_button(
            "下载集中评审 JSON",
            data=payload,
            file_name=default_export_path.name,
            mime="application/json",
            use_container_width=True,
        )
        if st.button("写入 reports/human_reviews_export.json", use_container_width=True):
            path = export_human_review_bundle(default_export_path)
            st.success(f"已写入 `{path}`")
        st.caption(
            f"含 {bundle.manual_review_count} 条 manual 评审 · "
            f"{bundle.pending_count} 个待评审 case 元数据"
        )

        uploaded = st.file_uploader(
            "导入评审 JSON（bundle 或 reviews 数组）",
            type=["json"],
            key="benchmark_human_review_import",
        )
        skip_existing = st.checkbox(
            "跳过已有 manual 评审的 case",
            value=False,
            key="benchmark_import_skip_existing",
        )
        if uploaded is not None and st.button("执行导入", key="benchmark_run_import"):
            import tempfile

            with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = Path(tmp.name)
            try:
                result = import_human_review_bundle(
                    tmp_path,
                    skip_existing_manual=skip_existing,
                )
            finally:
                tmp_path.unlink(missing_ok=True)
            if result.imported_count == 0:
                st.warning(
                    f"未导入任何评审（跳过 {result.skipped_count}，拒绝 {result.rejected_count}）。"
                )
            else:
                if st.session_state.get(_SESSION_AUTO_REGEN_KEY, True):
                    regenerate_benchmark_report()
                st.success(
                    f"已导入 {result.imported_count} 条评审"
                    f"（跳过 {result.skipped_count}，拒绝 {result.rejected_count}）。"
                )
                st.rerun()


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
    layout_review: HumanLayoutReview | None,
) -> None:
    from tests.benchmark.architectural_slides.render_manifest import (
        load_render_manifest,
        visual_review_eligibility,
        visual_review_image_path,
    )

    with column:
        case_dir = case.preview_path.parent
        eligible, _, blockers = visual_review_eligibility(case_dir)
        wireframe_tab, scene_tab, pptx_render_tab, pptx_tab = column.tabs(
            [
                "Layout 线框 (wireframe)",
                "Scene 预览 (scene_preview)",
                "PPTX 截图 (pptx_render)",
                "PPTX 文件",
            ]
        )
        with wireframe_tab:
            if case.wireframe_path.is_file():
                wireframe_tab.image(
                    str(case.wireframe_path),
                    caption=f"{case.title} · 几何线框（Layout Geometry Benchmark）",
                    use_container_width=True,
                )
            else:
                wireframe_tab.warning(f"缺少线框图：{case.wireframe_path}")
        with scene_tab:
            if case.scene_preview_path.is_file():
                scene_tab.image(
                    str(case.scene_preview_path),
                    caption=f"{case.title} · RenderScene 真实预览",
                    use_container_width=True,
                )
            else:
                scene_tab.info("尚无 `scene_preview.png`。请先运行 RenderScene 渲染管线。")
        with pptx_render_tab:
            review_image = visual_review_image_path(case_dir)
            if review_image is not None and review_image.name == "pptx_render.png":
                pptx_render_tab.image(
                    str(review_image),
                    caption=f"{case.title} · PPTX 截图",
                    use_container_width=True,
                )
            elif review_image is not None:
                pptx_render_tab.image(
                    str(review_image),
                    caption=f"{case.title} · 渲染预览（{review_image.name}）",
                    use_container_width=True,
                )
            else:
                pptx_render_tab.info(
                    "尚无 `pptx_render.png`。"
                    "若已导出 PPTX，可安装 LibreOffice + pdftoppm 生成截图，"
                    "或直接打开 output.pptx 进行视觉检查。"
                )
        pptx_path = case_dir / "output.pptx"
        with pptx_tab:
            if pptx_path.is_file():
                pptx_tab.caption(
                    f"RenderScene 驱动的可编辑 PPTX：`{pptx_path.name}`"
                )
                pptx_tab.markdown(f"[在本机打开 PPTX]({pptx_path.as_uri()})")
            else:
                pptx_tab.warning(
                    "尚未生成 `output.pptx`。运行 benchmark 渲染管线或 "
                    "`python scripts/render_architectural_benchmark_visuals.py`。"
                )

        manifest = load_render_manifest(case_dir)
        if manifest is not None:
            column.caption(
                f"render_valid={manifest.render_valid} · "
                f"renderer={manifest.renderer or '—'} · "
                f"placeholder_assets={manifest.placeholder_asset_count} · "
                f"missing_assets={len(manifest.missing_assets)}"
            )
        if not eligible:
            column.error(
                BENCHMARK_VISUAL_REVIEW_REQUIRES_FINAL_RENDER
                + "（" + "；".join(blockers) + "）"
            )

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
        if layout_review is not None and layout_review.is_manual_review():
            column.markdown(
                f"**几何评审：** {layout_review.human_score_label()} / 5"
                f"{' · 通过' if layout_review.accepted_for_geometry else ''}"
            )
        if review is None:
            column.markdown(f"**人工评分：** {HUMAN_REVIEW_PENDING_LABEL}")
            return
        if review.is_invalidated():
            column.markdown(f"**人工评分：** {HUMAN_REVIEW_INVALIDATED_LABEL}")
            if review.invalidation_reason:
                column.caption(review.invalidation_reason)
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
    existing_layout: HumanLayoutReview | None,
    existing_editability: EditabilityReview | None,
    case_ids: list[str],
    selected_index: int,
) -> None:
    with column:
        with st.expander("Layout Geometry 评审（wireframe）", expanded=True):
            _render_layout_review_form(case, existing_layout, case_ids, selected_index)
        with st.expander("Rendered Visual 评审（scene / pptx 截图）", expanded=False):
            _render_visual_review_form(case, existing, case_ids, selected_index)
        with st.expander("PPTX 可编辑性评审（output.pptx）", expanded=False):
            _render_editability_review_form(case, existing_editability, case_ids, selected_index)


def _render_layout_review_form(
    case: BenchmarkCaseSummary,
    existing: HumanLayoutReview | None,
    case_ids: list[str],
    selected_index: int,
) -> None:
    is_manual = existing is not None and existing.is_manual_review()
    defaults = {field: getattr(existing, field, 4) for field in LAYOUT_REVIEW_DIMENSION_LABELS}
    scores: dict[str, int] = {}
    for field, label in LAYOUT_REVIEW_DIMENSION_LABELS.items():
        scores[field] = st.slider(
            label,
            min_value=HUMAN_REVIEW_MIN_SCORE,
            max_value=HUMAN_REVIEW_MAX_SCORE,
            value=int(defaults[field]),
            key=f"benchmark_layout_review_{case.case_id}_{field}",
        )
    default_reviewer = ""
    if is_manual and existing is not None:
        default_reviewer = existing.reviewer
    elif st.session_state.get(_SESSION_REVIEWER_KEY):
        default_reviewer = str(st.session_state[_SESSION_REVIEWER_KEY])
    reviewer = st.text_input(
        "评审人",
        value=default_reviewer,
        key=f"benchmark_layout_reviewer_{case.case_id}",
    )
    major = st.text_area(
        "主要问题（每行一条）",
        value="\n".join(existing.major_problems if existing else []),
        height=60,
        key=f"benchmark_layout_major_{case.case_id}",
    )
    accepted_default = (
        bool(existing.accepted_for_geometry) if is_manual and existing is not None else False
    )
    accepted = st.checkbox(
        "几何版式通过",
        value=accepted_default,
        key=f"benchmark_layout_accept_{case.case_id}",
    )
    notes = st.text_input(
        "评审备注",
        value=existing.reviewer_notes if is_manual and existing is not None else "",
        key=f"benchmark_layout_notes_{case.case_id}",
    )
    preview = HumanLayoutReview(
        case_id=case.case_id,
        source=HumanVisualReviewSource.MANUAL,
        information_hierarchy=scores["information_hierarchy"],
        reading_order=scores["reading_order"],
        whitespace_density=scores["whitespace_density"],
        spatial_balance=scores["spatial_balance"],
        layout_clarity=scores["layout_clarity"],
        major_problems=[line.strip() for line in major.splitlines() if line.strip()],
        accepted_for_geometry=accepted,
        reviewer=reviewer.strip(),
        reviewed_at=datetime.now(UTC),
        reviewer_notes=notes.strip(),
    )
    st.caption(
        f"几何综合 {preview.weighted_score():.2f} / 5 · "
        f"{'通过' if preview.passes_threshold() else '未达'} 阈值 {LAYOUT_REVIEW_PASS_THRESHOLD}"
    )
    if st.button(
        "保存几何评审",
        type="secondary",
        use_container_width=True,
        key=f"benchmark_save_layout_review_{case.case_id}",
    ):
        saved_path = save_case_layout_review(preview)
        if preview.reviewer:
            st.session_state[_SESSION_REVIEWER_KEY] = preview.reviewer
        st.success(f"已保存至 `{saved_path.name}`")
        st.rerun()


def _render_visual_review_form(
    case: BenchmarkCaseSummary,
    existing: HumanVisualReview | None,
    case_ids: list[str],
    selected_index: int,
) -> None:
    from tests.benchmark.architectural_slides.render_manifest import visual_review_eligibility

    eligible, _, blockers = visual_review_eligibility(case.preview_path.parent)
    is_manual = existing is not None and existing.is_manual_review()
    if existing is not None and existing.is_invalidated():
        st.info(
            "本条视觉评分已作废（基于线框预览，validity=invalid_render_artifact）。"
            "待 `render_valid=true` 且真实渲染产物就绪后可重新保存。"
        )
    elif existing is not None and existing.is_scaffold_review():
        st.warning("当前为占位视觉评审。")
    if not eligible:
        st.error(
            BENCHMARK_VISUAL_REVIEW_REQUIRES_FINAL_RENDER
            + "（" + "；".join(blockers) + "）"
        )
        st.caption("视觉评审保存已禁用；可先完成上方几何评审。")

    defaults = {
        field: getattr(existing, field, 4)
        for field in VISUAL_REVIEW_DIMENSION_LABELS
    }
    scores: dict[str, int] = {}
    for field, label in VISUAL_REVIEW_DIMENSION_LABELS.items():
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
    accepted_default = (
        bool(existing.accepted_for_delivery) if is_manual and existing is not None else False
    )
    accepted_for_delivery = st.checkbox(
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
        editability=existing.editability if existing is not None else 4,
        major_problems=[line.strip() for line in major.splitlines() if line.strip()],
        minor_problems=[line.strip() for line in minor.splitlines() if line.strip()],
        review_completed=True,
        accepted_for_delivery=accepted_for_delivery,
        accepted=accepted_for_delivery,
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
        "保存视觉评审",
        type="primary",
        use_container_width=True,
        disabled=not eligible,
        key=f"benchmark_save_human_review_{case.case_id}",
    )
    save_next_clicked = save_cols[1].button(
        "保存并下一页",
        use_container_width=True,
        disabled=not eligible,
        key=f"benchmark_save_next_human_review_{case.case_id}",
    )
    if save_clicked or save_next_clicked:
        _persist_review(
            preview,
            advance=save_next_clicked,
            case_ids=case_ids,
            selected_index=selected_index,
        )


def _render_editability_review_form(
    case: BenchmarkCaseSummary,
    existing: EditabilityReview | None,
    case_ids: list[str],
    selected_index: int,
) -> None:
    from tests.benchmark.architectural_slides.render_manifest import editability_review_eligibility

    eligible, blockers = editability_review_eligibility(case.preview_path.parent)
    is_manual = existing is not None and existing.is_manual_review()
    if not eligible:
        st.error("可编辑性评审须基于 RenderScene 导出的 output.pptx。（" + "；".join(blockers) + "）")

    defaults = {
        field: getattr(existing, field, 4)
        for field in EDITABILITY_REVIEW_DIMENSION_LABELS
    }
    scores: dict[str, int] = {}
    for field, label in EDITABILITY_REVIEW_DIMENSION_LABELS.items():
        scores[field] = st.slider(
            label,
            min_value=HUMAN_REVIEW_MIN_SCORE,
            max_value=HUMAN_REVIEW_MAX_SCORE,
            value=int(defaults[field]),
            key=f"benchmark_editability_{case.case_id}_{field}",
        )
    default_reviewer = ""
    if is_manual and existing is not None:
        default_reviewer = existing.reviewer
    elif st.session_state.get(_SESSION_REVIEWER_KEY):
        default_reviewer = str(st.session_state[_SESSION_REVIEWER_KEY])
    reviewer = st.text_input(
        "评审人",
        value=default_reviewer,
        key=f"benchmark_editability_reviewer_{case.case_id}",
    )
    major = st.text_area(
        "主要问题（每行一条）",
        value="\n".join(existing.major_problems if existing else []),
        height=60,
        key=f"benchmark_editability_major_{case.case_id}",
    )
    passed_default = bool(existing.passed) if is_manual and existing is not None else False
    passed = st.checkbox(
        "PPTX 可编辑性通过",
        value=passed_default,
        key=f"benchmark_editability_pass_{case.case_id}",
    )
    notes = st.text_input(
        "评审备注",
        value=existing.reviewer_notes if is_manual and existing is not None else "",
        key=f"benchmark_editability_notes_{case.case_id}",
    )
    preview = EditabilityReview(
        case_id=case.case_id,
        source=HumanVisualReviewSource.MANUAL,
        text_editable=scores["text_editable"],
        image_replaceable=scores["image_replaceable"],
        layer_independence=scores["layer_independence"],
        chart_editable=scores["chart_editable"],
        font_usability=scores["font_usability"],
        not_flattened=scores["not_flattened"],
        selection_ease=scores["selection_ease"],
        modification_ease=scores["modification_ease"],
        major_problems=[line.strip() for line in major.splitlines() if line.strip()],
        review_completed=True,
        passed=passed,
        reviewer=reviewer.strip(),
        reviewed_at=datetime.now(UTC),
        reviewer_notes=notes.strip(),
    )
    st.caption(
        f"可编辑性综合 {preview.weighted_score():.2f} / 5 · "
        f"{'通过' if preview.passes_threshold() else '未达'} 阈值 {HUMAN_REVIEW_PASS_THRESHOLD}"
    )
    if st.button(
        "保存可编辑性评审",
        type="secondary",
        use_container_width=True,
        disabled=not eligible,
        key=f"benchmark_save_editability_{case.case_id}",
    ):
        saved_path = save_case_editability_review(preview)
        if preview.reviewer:
            st.session_state[_SESSION_REVIEWER_KEY] = preview.reviewer
        st.success(f"已保存至 `{saved_path.name}`")
        st.rerun()


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

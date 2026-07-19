"""Streamlit UI for Visual QA calibration corpus management."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import streamlit as st

from archium.application.visual_qa_corpus_service import (
    LABEL_KEYS,
    VALID_CATEGORIES,
    VisualQACorpusService,
)

_CATEGORY_LABELS = {
    "site_plan": "总平面图",
    "floor_plan": "平面图",
    "section": "剖面图",
    "elevation": "立面图",
    "diagram": "分析图",
    "photo": "效果图/照片",
}

_BOOL_LABELS = {
    "has_north_arrow": "含指北针",
    "has_legend": "含图例",
    "is_low_resolution": "低分辨率",
    "is_clipped": "内容裁切",
    "excessive_margins": "留白过大",
    "high_text_density": "文字过密",
    "low_contrast": "对比度低",
}


def render_visual_qa_corpus_panel() -> None:
    st.markdown("### 视觉 QA 标定语料库")
    st.caption(
        "维护带人工标签的校准语料，运行 precision/recall 评估，并决定哪些启发式规则可发出正式审核问题。"
        "合成 bootstrap 语料可用于验证流程；正式标定建议逐步替换为真实项目图纸。"
    )

    service = VisualQACorpusService()
    progress = service.progress()
    _render_progress(progress)

    action_col1, action_col2, action_col3 = st.columns(3)
    if action_col1.button("生成合成 bootstrap 语料（260 张）", use_container_width=True):
        with st.spinner("正在生成合成样本…"):
            result = service.seed_synthetic_corpus(replace_manifest=True, overwrite_images=True)
        st.success(f"已生成 {result['generated_count']} 条样本。")
        st.rerun()

    if action_col2.button("运行校准并写报告", use_container_width=True):
        if progress["total_current"] == 0:
            st.error("语料为空，请先生成或导入样本。")
        else:
            with st.spinner("正在分析语料并计算指标…"):
                report = service.calibrate()
            st.success(f"校准报告已写入 `{service.report_path}`")
            _render_calibration_summary(report)

    report_path = service.report_path
    if report_path.is_file() and action_col3.button("查看上次校准摘要", use_container_width=True):
        import json

        report = json.loads(report_path.read_text(encoding="utf-8"))
        _render_calibration_summary(report)

    st.divider()
    _render_import_panel(service)
    st.divider()
    _render_sample_editor(service)


def _render_progress(progress: dict[str, object]) -> None:
    current = cast(dict[str, int], progress["current"])
    targets = cast(dict[str, int], progress["targets"])
    total_current = cast(int, progress["total_current"])
    total_target = cast(int, progress["total_target"])

    st.progress(min(1.0, total_current / max(total_target, 1)))
    st.markdown(f"**总进度：{total_current} / {total_target}**")

    cols = st.columns(3)
    for index, (category, target) in enumerate(targets.items()):
        count = current.get(category, 0)
        label = _CATEGORY_LABELS.get(category, category)
        cols[index % 3].metric(label, f"{count}/{target}")


def _render_calibration_summary(report: dict[str, object]) -> None:
    checks = report.get("checks", {})
    if not isinstance(checks, dict):
        return

    rows: list[dict[str, object]] = []
    for rule_code, payload in sorted(checks.items()):
        if not isinstance(payload, dict):
            continue
        score = payload.get("precision") or payload.get("drawing_type_accuracy")
        rows.append(
            {
                "规则": rule_code,
                "检查项": payload.get("check_name"),
                "得分": f"{score:.1%}" if isinstance(score, (int, float)) else "n/a",
                "目标": (
                    f"{payload.get('target_precision'):.0%}"
                    if isinstance(payload.get("target_precision"), (int, float))
                    else "n/a"
                ),
                "状态": "PASS" if payload.get("meets_target") else ("FAIL" if payload.get("meets_target") is False else "N/A"),
                "样本数": payload.get("evaluated", payload.get("drawing_type_total", 0)),
            }
        )
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)

    eligible = report.get("formal_emit_eligible_rule_codes", [])
    if isinstance(eligible, list) and eligible:
        st.markdown("**可发正式问题的规则：** " + ", ".join(str(code) for code in eligible))


def _render_import_panel(service: VisualQACorpusService) -> None:
    st.markdown("#### 导入样本")
    uploaded = st.file_uploader(
        "上传图片并标注",
        type=["png", "jpg", "jpeg", "webp"],
        key="visual_qa_corpus_upload",
    )
    category = st.selectbox(
        "类别",
        options=sorted(VALID_CATEGORIES),
        format_func=lambda value: _CATEGORY_LABELS.get(value, value),
        key="visual_qa_corpus_import_category",
    )
    notes = st.text_input("备注", key="visual_qa_corpus_import_notes")

    label_cols = st.columns(2)
    label_values: dict[str, object] = {"drawing_type": category}
    bool_keys = [key for key in LABEL_KEYS if key != "drawing_type"]
    for index, key in enumerate(bool_keys):
        if category == "photo" and key in {"has_north_arrow", "has_legend"}:
            label_values[key] = None
            continue
        choice = label_cols[index % 2].selectbox(
            _BOOL_LABELS[key],
            options=["跳过", "是", "否"],
            key=f"visual_qa_import_{key}",
        )
        if choice == "跳过":
            label_values[key] = None
        else:
            label_values[key] = choice == "是"

    if st.button("导入到语料库", type="secondary") and uploaded is not None:
        temp_dir = Path(st.session_state.setdefault("visual_qa_upload_dir", str(Path.cwd() / ".tmp_visual_qa")))
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / uploaded.name
        temp_path.write_bytes(uploaded.getbuffer())
        try:
            sample = service.import_image(
                source_path=temp_path,
                category=category,
                labels=label_values,
                notes=notes,
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"已导入样本 `{sample['id']}`")
            st.rerun()


def _render_sample_editor(service: VisualQACorpusService) -> None:
    samples = service.list_samples()
    st.markdown("#### 语料样本")
    if not samples:
        st.info("尚无样本。可生成合成 bootstrap 语料，或导入真实项目图纸。")
        return

    sample_ids = [str(sample["id"]) for sample in samples]
    selected_id = st.selectbox(
        "选择样本",
        options=sample_ids,
        format_func=lambda value: value,
        key="visual_qa_selected_sample",
    )
    sample = service.get_sample(selected_id)
    if sample is None:
        return

    image_path = service.corpus_root / str(sample["path"])
    preview_col, meta_col = st.columns([1, 1])
    if image_path.is_file():
        preview_col.image(str(image_path), caption=sample.get("notes") or selected_id, use_container_width=True)
    else:
        preview_col.warning(f"图片缺失：{sample['path']}")

    labels = dict(sample.get("labels", {}))
    meta_col.markdown(f"**类别：** {_CATEGORY_LABELS.get(sample.get('category', ''), sample.get('category', ''))}")
    meta_col.markdown(f"**来源：** {sample.get('source', 'unknown')}")
    meta_col.markdown(f"**路径：** `{sample.get('path')}`")

    edited_notes = meta_col.text_area("备注", value=str(sample.get("notes", "")), key="visual_qa_sample_notes")
    edited_labels: dict[str, object] = {"drawing_type": labels.get("drawing_type", sample.get("category"))}
    for key in LABEL_KEYS:
        if key == "drawing_type":
            continue
        current = labels.get(key)
        if sample.get("category") == "photo" and key in {"has_north_arrow", "has_legend"}:
            edited_labels[key] = None
            continue
        choice = meta_col.selectbox(
            _BOOL_LABELS[key],
            options=["跳过", "是", "否"],
            index=0 if current is None else (1 if current else 2),
            key=f"visual_qa_edit_{selected_id}_{key}",
        )
        edited_labels[key] = None if choice == "跳过" else choice == "是"

    save_col, delete_col = meta_col.columns(2)
    if save_col.button("保存标注", use_container_width=True):
        try:
            service.upsert_sample(
                {
                    **sample,
                    "notes": edited_notes,
                    "labels": edited_labels,
                }
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success("样本已更新")
            st.rerun()

    if delete_col.button("删除样本", use_container_width=True):
        service.delete_sample(selected_id)
        st.warning(f"已删除样本 `{selected_id}`")
        st.rerun()

    with st.expander("查看 analyzer 预测（调试）"):
        if image_path.is_file():
            from archium.application.visual_qa_calibration import analyze_sample_image

            report = analyze_sample_image(image_path)
            rows = [
                {
                    "检查项": check.check_name,
                    "通过": check.passed,
                    "置信度": round(check.confidence, 3),
                    "摘要": check.summary,
                }
                for check in report.checks
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
            st.caption(
                f"分类：{report.drawing_type} ({report.drawing_type_confidence}) · "
                f"analyzer {report.analyzer_version}"
            )
        else:
            st.info("图片缺失，无法运行 analyzer。")

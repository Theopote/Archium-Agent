"""Showcase Case 001 rehearsal — page claims + local PPTX (no new Agent)."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from archium.application.visual.showcase_case_001 import (
    CASE_001_DEFAULT_PRESET,
    DEMO_TOUR_TITLES,
    build_case_001_render_bundle,
    case_001_outputs_dir,
    export_case_001_pptx,
    showcase_case_001_dir,
    write_case_001_dry_run,
)


def render_showcase_case_001_panel() -> None:
    """Local rehearsal for hospital Case 001 (Grammar + VisualConcept)."""
    with st.expander("Showcase 排练：Case 001 医院更新（本地）", expanded=False):
        st.caption(
            "虚构项目：市级综合医院老院区更新。跑 outline → 页主张 → VisualConcept → "
            "LayoutSolver → PPTX。大文件写在 outputs/（不进 git）。"
        )
        preset = st.selectbox(
            "气质 Preset",
            options=[
                "architecture_technical",
                "architecture_minimal",
                "architecture_urban",
                "architecture_luxury",
            ],
            index=0,
            key="showcase_case_001_preset",
            help=f"默认 {CASE_001_DEFAULT_PRESET}",
        )
        c1, c2 = st.columns(2)
        dry = c1.button("生成页主张（dry-run）", key="showcase_case_001_dry")
        full = c2.button("导出 PPTX", key="showcase_case_001_pptx")

        out = case_001_outputs_dir()
        summary: dict[str, Any] | None = None
        if dry or full:
            with st.spinner("正在编排 Case 001…"):
                try:
                    bundle = build_case_001_render_bundle(style_preset_id=preset)
                    if dry:
                        summary = write_case_001_dry_run(bundle, output_dir=out)
                    else:
                        summary = export_case_001_pptx(bundle, output_dir=out)
                    st.session_state["showcase_case_001_summary"] = summary
                    st.success(
                        f"完成：{summary.get('slide_count')} 页 · "
                        f"{summary.get('mode')} · "
                        f"导演命中 {summary.get('page_direction_hits')}"
                    )
                except Exception as exc:  # noqa: BLE001 — surface rehearsal errors in UI
                    st.error(f"Case 001 排练失败：{exc}")
                    return

        if summary is None:
            stored_summary = st.session_state.get("showcase_case_001_summary")
            if isinstance(stored_summary, dict):
                summary = stored_summary
        claims_path = out / "page_claims.json"
        if claims_path.is_file():
            payload = json.loads(claims_path.read_text(encoding="utf-8"))
            st.markdown("**Demo 导览 · 页主张**")
            pages = {p["title"]: p for p in payload.get("pages") or []}
            tour = list(DEMO_TOUR_TITLES) + ["现状问题总览", "流线冲突"]
            seen: set[str] = set()
            for title in tour:
                if title in seen:
                    continue
                seen.add(title)
                page = pages.get(title)
                if page is None:
                    continue
                vc = page.get("visual_concept") or {}
                metaphor = vc.get("visual_metaphor") or "—"
                st.markdown(
                    f"- **{title}** · {page.get('emotion')} · "
                    f"`{metaphor}`  \n"
                    f"  {page.get('claim', '')}"
                )
            overview = pages.get("现状问题总览") or {}
            conflict = pages.get("流线冲突") or {}
            ov_meta = (overview.get("visual_concept") or {}).get("visual_metaphor")
            cf_meta = (conflict.get("visual_concept") or {}).get("visual_metaphor")
            if cf_meta == "fragment_to_network" and ov_meta != "fragment_to_network":
                st.info(
                    "Grammar 校验通过：仅「流线冲突」挂 `fragment_to_network`；"
                    "「现状问题总览」保持证据板主张。"
                )
            elif cf_meta == "fragment_to_network" and ov_meta == "fragment_to_network":
                st.warning(
                    "Grammar 误伤：现状问题总览也被标成 fragment_to_network，请检查识别规则。"
                )

        pptx = out / "presentation.pptx"
        if pptx.is_file():
            st.caption(f"PPTX：`{pptx}`")
            try:
                st.download_button(
                    "下载 presentation.pptx",
                    data=pptx.read_bytes(),
                    file_name="case_001_hospital.pptx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "presentationml.presentation"
                    ),
                    key="showcase_case_001_download",
                )
            except OSError:
                st.warning("无法读取 PPTX 文件。")

        readme = showcase_case_001_dir() / "README.md"
        if readme.is_file():
            st.caption(f"说明见 `{readme.as_posix()}`")

        if isinstance(summary, dict) and summary.get("note"):
            st.warning(str(summary["note"]))

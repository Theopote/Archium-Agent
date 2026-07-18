"""Streamlit UI for verified plan overlay metadata on project assets."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.asset_metadata_service import AssetMetadataService
from archium.domain.plan_overlay import PlanLegendItem, PlanOverlayMetadata, plan_overlay_from_asset
from archium.infrastructure.database.session import get_session

_PLAN_VISUAL_TYPES = {"site_plan", "map", "floor_plan"}


def _parse_legend_lines(text: str) -> list[PlanLegendItem]:
    items: list[PlanLegendItem] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "|" in line:
            label, color = [part.strip() for part in line.split("|", 1)]
            items.append(PlanLegendItem(label=label, color=color or None))
        else:
            items.append(PlanLegendItem(label=line))
    return items


def _format_legend_lines(overlay: PlanOverlayMetadata) -> str:
    lines: list[str] = []
    for item in overlay.legend_items:
        if item.color:
            lines.append(f"{item.label}|{item.color}")
        else:
            lines.append(item.label)
    return "\n".join(lines)


def _overlay_status_label(overlay: PlanOverlayMetadata | None) -> str:
    if overlay is None or not overlay.has_any_overlay:
        return "未标注"
    parts: list[str] = []
    if overlay.show_north_arrow:
        parts.append("指北针")
    if overlay.scale_label:
        parts.append(f"比例尺 {overlay.scale_label}")
    elif overlay.scale_pending:
        parts.append("比例尺待核实")
    if overlay.legend_items:
        parts.append(f"图例 {len(overlay.legend_items)} 项")
    return " · ".join(parts)


def render_asset_metadata_panel(project_id: UUID) -> None:
    st.markdown("#### 图纸标注")
    st.caption(
        "为总图/平面图素材标注已核实的指北针、比例尺与图例。"
        "未标注时导出 PPTX 不会自动添加这些元素，避免错误信息。"
    )

    with get_session() as session:
        assets = AssetMetadataService(session).list_project_assets(project_id)

    if not assets:
        st.info("导入资料并提取素材后，可在此标注图纸元数据。")
        return

    asset_labels = {
        str(asset.id): f"{asset.filename} · {_overlay_status_label(plan_overlay_from_asset(asset))}"
        for asset in assets
    }
    selected_id = st.selectbox(
        "选择素材",
        options=list(asset_labels.keys()),
        format_func=lambda value: asset_labels[value],
        key=f"asset_metadata_select_{project_id}",
    )
    asset = next(item for item in assets if str(item.id) == selected_id)

    with get_session() as session:
        overlay = AssetMetadataService(session).get_plan_overlay(asset.id)

    show_north = st.checkbox(
        "显示指北针（已核实）",
        value=overlay.show_north_arrow,
        key=f"plan_north_{asset.id}",
        help="仅在您确认图纸北向无误时勾选。",
    )
    scale_col1, scale_col2 = st.columns(2)
    scale_label = scale_col1.text_input(
        "比例尺标注",
        value=overlay.scale_label or "",
        placeholder="例如：0 — 100m",
        key=f"plan_scale_{asset.id}",
    )
    scale_pending = scale_col2.checkbox(
        "比例尺待核实",
        value=overlay.scale_pending,
        key=f"plan_scale_pending_{asset.id}",
        help="勾选后导出时显示「比例尺待核实」，不会编造具体数值。",
    )
    legend_text = st.text_area(
        "图例项（每行一项，可选颜色：标签|#336699）",
        value=_format_legend_lines(overlay),
        height=120,
        key=f"plan_legend_{asset.id}",
        placeholder="人行|#336699\n车行|#993333",
    )

    st.caption(f"当前状态：{_overlay_status_label(overlay)}")

    save_col, clear_col = st.columns(2)
    if save_col.button("保存图纸标注", key=f"save_plan_overlay_{asset.id}", use_container_width=True):
        draft = PlanOverlayMetadata(
            show_north_arrow=show_north,
            scale_label=scale_label.strip() or None,
            scale_pending=scale_pending and not scale_label.strip(),
            legend_items=_parse_legend_lines(legend_text),
        )
        with get_session() as session:
            AssetMetadataService(session).save_plan_overlay(asset.id, draft)
        st.success("图纸标注已保存。导出 PPTX 时将按核实内容渲染。")
        st.rerun()

    if clear_col.button("清除标注", key=f"clear_plan_overlay_{asset.id}", use_container_width=True):
        with get_session() as session:
            AssetMetadataService(session).clear_plan_overlay(asset.id)
        st.warning("已清除该素材的图纸标注。")
        st.rerun()


def render_plan_overlay_editor_for_asset(
    *,
    asset_id: UUID,
    visual_type: str,
    key_prefix: str,
) -> None:
    """Inline overlay editor for Asset Board when the requirement is plan-like."""
    if visual_type not in _PLAN_VISUAL_TYPES:
        return

    with get_session() as session:
        service = AssetMetadataService(session)
        overlay = service.get_plan_overlay(asset_id)

    st.markdown("**图纸标注（导出 PPTX 时使用）**")
    show_north = st.checkbox(
        "显示指北针",
        value=overlay.show_north_arrow,
        key=f"{key_prefix}_north",
    )
    scale_label = st.text_input(
        "比例尺",
        value=overlay.scale_label or "",
        placeholder="0 — 100m",
        key=f"{key_prefix}_scale",
    )
    scale_pending = st.checkbox(
        "比例尺待核实",
        value=overlay.scale_pending,
        key=f"{key_prefix}_scale_pending",
    )
    legend_text = st.text_area(
        "图例（每行一项）",
        value=_format_legend_lines(overlay),
        height=80,
        key=f"{key_prefix}_legend",
    )

    if st.button("保存图纸标注", key=f"{key_prefix}_save_overlay", use_container_width=True):
        draft = PlanOverlayMetadata(
            show_north_arrow=show_north,
            scale_label=scale_label.strip() or None,
            scale_pending=scale_pending and not scale_label.strip(),
            legend_items=_parse_legend_lines(legend_text),
        )
        with get_session() as session:
            AssetMetadataService(session).save_plan_overlay(asset_id, draft)
        st.success("图纸标注已保存。")
        st.rerun()

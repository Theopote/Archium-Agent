"""Streamlit UI for the presentation Asset Board."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import streamlit as st

from archium.application.asset_board_service import AssetBoardRow, AssetBoardService
from archium.application.asset_provenance import (
    format_asset_option_label,
    format_asset_vision_summary,
)
from archium.config.settings import get_settings
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.asset_metadata_panel import render_plan_overlay_editor_for_asset
from archium.ui.web_image_preview_panel import render_web_image_preview_panel


def render_asset_board_panel(*, project_id: UUID, presentation_id: UUID) -> None:
    st.markdown("#### Asset Board")
    st.caption("逐页视觉需求 · 候选素材匹配 · 人工确认")

    with get_session() as session:
        service = AssetBoardService(session)
        board = service.build_board(project_id, presentation_id)
        assets = service.list_project_assets(project_id)

    summary = st.columns(4)
    summary[0].metric("项目素材", board.asset_count)
    summary[1].metric("已匹配", board.matched_count)
    summary[2].metric("已确认", board.confirmed_count)
    summary[3].metric("待确认", board.pending_count)

    if st.button("重新匹配素材", key=f"rematch_assets_{presentation_id}", use_container_width=True):
        with get_session() as session:
            AssetBoardService(session).rematch(project_id, presentation_id)
        st.success("素材匹配已更新（已确认项保持不变）。")
        st.rerun()

    if not board.rows:
        st.info("当前汇报暂无视觉需求。生成 SlideSpec 并运行工作流后会在此显示匹配结果。")
        return

    table_rows = [
        {
            "页码": f"p{row.slide_order + 1}",
            "页面": row.slide_title,
            "视觉类型": row.visual_type,
            "需求描述": row.description,
            "候选素材": row.asset_filename or "—",
            "推荐分": f"{row.match_score:.2f}" if row.match_score is not None else "—",
            "来源": row.asset_source or ("可网络搜图" if row.web_search_eligible else "—"),
            "页": row.asset_page or "—",
            "分辨率": row.resolution or "—",
            "宽高比": f"{row.aspect_ratio:.2f}" if row.aspect_ratio else "—",
            "需裁切": "是" if row.needs_crop else "否",
            "需标注": "是" if row.needs_highlight else "否",
            "低清": "⚠️" if row.low_resolution else "",
            "已确认": "✅" if row.confirmed else "—",
        }
        for row in board.rows
    ]
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    st.markdown("**编辑匹配**")
    row_labels = {
        _row_key(row): f"p{row.slide_order + 1} · {row.slide_title} · {row.visual_type}"
        for row in board.rows
    }
    selected_key = st.selectbox(
        "选择视觉需求",
        options=list(row_labels.keys()),
        format_func=lambda value: row_labels[value],
        key=f"asset_board_select_{presentation_id}",
    )
    selected = next(row for row in board.rows if _row_key(row) == selected_key)

    asset_options = {"": "— 未选择 —"}
    for asset in assets:
        asset_options[str(asset.id)] = format_asset_option_label(asset)
    current_asset = str(selected.candidate_asset_id) if selected.candidate_asset_id else ""
    picked_asset = st.selectbox(
        "候选素材",
        options=list(asset_options.keys()),
        index=list(asset_options.keys()).index(current_asset)
        if current_asset in asset_options
        else 0,
        format_func=lambda value: asset_options[value],
        key=f"asset_pick_{selected_key}",
    )

    flag_col1, flag_col2 = st.columns(2)
    needs_crop = flag_col1.checkbox(
        "需要裁切",
        value=selected.needs_crop,
        key=f"needs_crop_{selected_key}",
    )
    needs_highlight = flag_col2.checkbox(
        "需要标注/高亮",
        value=selected.needs_highlight,
        key=f"needs_highlight_{selected_key}",
    )

    btn1, btn2, btn3 = st.columns(3)
    if btn1.button("保存素材", key=f"save_asset_{selected_key}", use_container_width=True):
        if not picked_asset:
            st.error("请先选择素材。")
        else:
            try:
                with get_session() as session:
                    AssetBoardService(session).assign_asset(
                        selected.slide_id,
                        selected.requirement_index,
                        UUID(picked_asset),
                    )
                st.success("素材已更新。")
                st.rerun()
            except WorkflowError as exc:
                st.error(str(exc))

    if btn2.button("确认匹配", key=f"confirm_asset_{selected_key}", use_container_width=True):
        try:
            with get_session() as session:
                board_service = AssetBoardService(session)
                if picked_asset and picked_asset != current_asset:
                    board_service.assign_asset(
                        selected.slide_id,
                        selected.requirement_index,
                        UUID(picked_asset),
                    )
                board_service.confirm_assignment(selected.slide_id, selected.requirement_index)
                board_service.update_assignment_flags(
                    selected.slide_id,
                    selected.requirement_index,
                    needs_crop=needs_crop,
                    needs_highlight=needs_highlight,
                )
            st.success("视觉匹配已确认。")
            st.rerun()
        except WorkflowError as exc:
            st.error(str(exc))

    if btn3.button("保存处理标记", key=f"save_flags_{selected_key}", use_container_width=True):
        try:
            with get_session() as session:
                AssetBoardService(session).update_assignment_flags(
                    selected.slide_id,
                    selected.requirement_index,
                    needs_crop=needs_crop,
                    needs_highlight=needs_highlight,
                )
            st.success("处理标记已保存。")
            st.rerun()
        except WorkflowError as exc:
            st.error(str(exc))

    _render_asset_preview(project_id, selected, assets)
    render_web_image_preview_panel(
        project_id=project_id,
        presentation_id=presentation_id,
        slide=_load_slide(selected.slide_id),
        requirement=_load_requirement(selected),
        requirement_index=selected.requirement_index,
        web_search_eligible=selected.web_search_eligible,
    )
    if picked_asset:
        render_plan_overlay_editor_for_asset(
            asset_id=UUID(picked_asset),
            visual_type=selected.visual_type,
            key_prefix=f"asset_board_overlay_{selected_key}",
        )


def _row_key(row: AssetBoardRow) -> str:
    return f"{row.slide_id}:{row.requirement_index}"


def _load_slide(slide_id: UUID) -> SlideSpec:
    with get_session() as session:
        from archium.infrastructure.database.repositories import PresentationRepository

        slide = PresentationRepository(session).get_slide(slide_id)
        if slide is None:
            raise WorkflowError(f"Slide {slide_id} not found")
        return slide


def _load_requirement(row: AssetBoardRow) -> VisualRequirement:
    slide = _load_slide(row.slide_id)
    return slide.visual_requirements[row.requirement_index]


def _render_asset_preview(project_id: UUID, selected: AssetBoardRow, assets: list) -> None:
    if selected.candidate_asset_id is None:
        return
    asset = next((item for item in assets if item.id == selected.candidate_asset_id), None)
    if asset is None:
        return
    settings = get_settings()
    path = Path(asset.path)
    if not path.is_absolute():
        path = settings.project_storage_path / str(project_id) / path
    if not path.exists():
        st.caption(f"预览不可用：{path}")
        return
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        st.image(str(path), caption=asset.filename, use_container_width=True)
    vision_summary = format_asset_vision_summary(asset)
    if vision_summary:
        source = asset.metadata.get("vision_source", "caption")
        st.markdown("**图档理解**")
        st.caption(f"来源：{source}")
        st.write(vision_summary)
        elements = []
        vision = asset.metadata.get("vision_caption")
        if isinstance(vision, dict):
            spatial = vision.get("spatial_elements") or []
            if isinstance(spatial, list) and spatial:
                elements.append("空间要素：" + "、".join(str(item) for item in spatial[:6]))
            metrics = vision.get("metrics_visible") or []
            if isinstance(metrics, list) and metrics:
                elements.append("可见指标：" + "、".join(str(item) for item in metrics[:6]))
        for line in elements:
            st.caption(line)

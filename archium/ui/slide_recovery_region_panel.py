"""Slide Recovery region editor — drag bbox, merge/split, and recompute."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import streamlit as st

from archium.application.slide_recovery_delivery_service import SlideRecoveryDeliveryService
from archium.application.slide_recovery_region_canvas import (
    apply_canvas_move,
    apply_canvas_resize,
    layout_plan_from_regions,
    merge_regions,
    region_index_for_element_id,
    replace_region,
    split_region,
)
from archium.application.slide_recovery_region_edit_service import (
    SlideRecoveryRegionEditService,
    extract_regions,
    new_region,
    sanitize_region,
)
from archium.application.slide_recovery_workflow_service import SlideRecoveryWorkflowResult
from archium.config.settings import Settings
from archium.domain.enums import WorkflowStatus
from archium.domain.slide_recovery import (
    REGION_TYPE_LABELS_ZH,
    REGION_TYPE_OPTIONS,
    NormalizedBox,
    RecoveredPageRegion,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.infrastructure.slide_recovery.region_overlay_renderer import render_region_overlay
from archium.ui.error_handlers import format_user_error
from archium.ui.studio.slide_canvas_enhanced import parse_canvas_editor_event


def _draft_session_key(workflow_run_id: UUID) -> str:
    return f"slide_recovery_region_draft_{workflow_run_id}"


def _selected_session_key(workflow_run_id: UUID) -> str:
    return f"slide_recovery_region_selected_{workflow_run_id}"


def _merge_selection_session_key(workflow_run_id: UUID) -> str:
    return f"slide_recovery_region_merge_{workflow_run_id}"


def _load_draft_regions(
    result: SlideRecoveryWorkflowResult,
) -> list[RecoveredPageRegion]:
    key = _draft_session_key(result.workflow_run.id)
    stored = st.session_state.get(key)
    if isinstance(stored, list) and stored:
        return [RecoveredPageRegion.model_validate(item) for item in stored]
    regions = extract_regions(result)
    st.session_state[key] = [region.model_dump(mode="json") for region in regions]
    return regions


def _save_draft_regions(
    workflow_run_id: UUID,
    regions: list[RecoveredPageRegion],
) -> None:
    st.session_state[_draft_session_key(workflow_run_id)] = [
        region.model_dump(mode="json") for region in regions
    ]


def _region_option_label(index: int, region: RecoveredPageRegion) -> str:
    kind = REGION_TYPE_LABELS_ZH.get(region.region_type, region.region_type)
    role = region.semantic_role or "—"
    if region.region_type == "text" and region.recovered_text:
        snippet = region.recovered_text.strip().replace("\n", " ")
        if len(snippet) > 16:
            snippet = snippet[:16] + "…"
        return f"#{index + 1} {kind} · {snippet}"
    return f"#{index + 1} {kind} · {role}"


def render_slide_recovery_region_editor(
    result: SlideRecoveryWorkflowResult,
    *,
    project_id: UUID,
    settings: Settings,
    key_prefix: str = "slide_recovery_region",
) -> SlideRecoveryWorkflowResult | None:
    """Render region bbox editor; return updated workflow result when applied."""
    run = result.workflow_run
    if run.status not in {WorkflowStatus.COMPLETED, WorkflowStatus.AWAITING_REVIEW}:
        return None

    regions = _load_draft_regions(result)
    if not regions:
        return None

    with get_session() as session:
        delivery = SlideRecoveryDeliveryService(session, settings=settings)
        source_path = delivery.resolve_source_preview_path(result)

    st.markdown("#### 区域校正")
    st.caption("拖拽或缩放边界框，支持区域合并/拆分；应用后将重新计算 Hybrid Scene。")

    selected_key = _selected_session_key(run.id)
    option_labels = [_region_option_label(index, region) for index, region in enumerate(regions)]
    default_index = int(st.session_state.get(selected_key, 0))
    default_index = max(0, min(default_index, len(regions) - 1))
    selected_label = st.selectbox(
        "选择区域",
        options=option_labels,
        index=default_index,
        key=f"{key_prefix}_select",
    )
    selected_index = option_labels.index(selected_label)
    st.session_state[selected_key] = selected_index
    selected_region = regions[selected_index]

    if source_path is not None and source_path.is_file():
        interactive = _render_interactive_region_canvas(
            source_path=source_path,
            regions=regions,
            selected_index=selected_index,
            selected_key=selected_key,
            run_id=run.id,
            key_prefix=key_prefix,
        )
        if not interactive:
            _render_static_region_overlay(
                source_path=source_path,
                regions=regions,
                selected_region=selected_region,
                run_id=run.id,
                settings=settings,
            )
    else:
        st.info("暂无源页面图片，无法显示区域叠加预览。")

    _render_merge_split_controls(
        regions=regions,
        selected_region=selected_region,
        selected_index=selected_index,
        option_labels=option_labels,
        run_id=run.id,
        selected_key=selected_key,
        key_prefix=key_prefix,
    )

    updated_region = _render_region_form(
        selected_region,
        key_prefix=f"{key_prefix}_{selected_index}",
    )
    regions[selected_index] = updated_region
    _save_draft_regions(run.id, regions)

    col_apply, col_reset, col_add, col_delete = st.columns(4)
    with col_apply:
        apply_clicked = st.button(
            "应用区域修正",
            type="primary",
            key=f"{key_prefix}_apply",
        )
    with col_reset:
        reset_clicked = st.button("重置为检测结果", key=f"{key_prefix}_reset")
    with col_add:
        add_clicked = st.button("新增区域", key=f"{key_prefix}_add")
    with col_delete:
        delete_clicked = st.button(
            "删除当前区域",
            key=f"{key_prefix}_delete",
            disabled=len(regions) <= 1,
        )

    if reset_clicked:
        fresh = extract_regions(result)
        _save_draft_regions(run.id, fresh)
        st.session_state[selected_key] = 0
        st.session_state[_merge_selection_session_key(run.id)] = []
        st.rerun()

    if add_clicked:
        regions.append(new_region())
        _save_draft_regions(run.id, regions)
        st.session_state[selected_key] = len(regions) - 1
        st.rerun()

    if delete_clicked:
        regions.pop(selected_index)
        _save_draft_regions(run.id, regions)
        st.session_state[selected_key] = max(0, selected_index - 1)
        st.rerun()

    if apply_clicked:
        try:
            with get_session() as session:
                service = SlideRecoveryRegionEditService(session)
                updated = service.apply_region_edits(run.id, regions)
                session.commit()
        except WorkflowError as exc:
            st.error(format_user_error(exc))
            return None
        except Exception as exc:
            st.error(format_user_error(exc))
            return None

        _save_draft_regions(run.id, extract_regions(updated))
        st.session_state[_merge_selection_session_key(run.id)] = []
        st.success("已根据区域修正重新计算恢复结果，请复核指标与预览。")
        return updated

    return None


def _render_interactive_region_canvas(
    *,
    source_path: Path | str,
    regions: list[RecoveredPageRegion],
    selected_index: int,
    selected_key: str,
    run_id: UUID,
    key_prefix: str,
) -> bool:
    from archium.ui.components.canvas_editor import (
        CanvasEditorUnavailableError,
        canvas_editor,
        canvas_editor_available,
        canvas_editor_unavailable_reason,
    )

    if not canvas_editor_available():
        return False

    layout_plan = layout_plan_from_regions(regions)
    selected_region = regions[selected_index]

    try:
        canvas_event = canvas_editor(
            image_url=str(source_path),
            layout_plan=layout_plan,
            selected_element_id=str(selected_region.id),
            show_labels=True,
            show_all_borders=True,
            key=f"{key_prefix}_canvas_{run_id}",
        )
    except CanvasEditorUnavailableError as exc:
        st.caption(canvas_editor_unavailable_reason() or str(exc))
        return False
    except Exception as exc:
        st.caption(f"交互画布不可用：{format_user_error(exc)}")
        return False

    event_kind, element_id, x_percent, y_percent, width_percent, height_percent, _preserve = (
        parse_canvas_editor_event(canvas_event)
    )

    if event_kind == "select" and element_id:
        index = region_index_for_element_id(regions, element_id)
        if index is not None and index != selected_index:
            st.session_state[selected_key] = index
            st.rerun()

    if event_kind == "move" and element_id and x_percent is not None and y_percent is not None:
        index = region_index_for_element_id(regions, element_id)
        if index is not None:
            regions[index] = apply_canvas_move(
                regions[index],
                layout_plan,
                x_percent=x_percent,
                y_percent=y_percent,
            )
            _save_draft_regions(run_id, regions)
            st.session_state[selected_key] = index
            st.rerun()

    if (
        event_kind == "resize"
        and element_id
        and x_percent is not None
        and y_percent is not None
        and width_percent is not None
        and height_percent is not None
    ):
        index = region_index_for_element_id(regions, element_id)
        if index is not None:
            regions[index] = apply_canvas_resize(
                regions[index],
                layout_plan,
                x_percent=x_percent,
                y_percent=y_percent,
                width_percent=width_percent,
                height_percent=height_percent,
            )
            _save_draft_regions(run_id, regions)
            st.session_state[selected_key] = index
            st.rerun()

    st.caption("拖拽移动区域，拖拽边角缩放；点击区域可切换选中。")
    return True


def _render_static_region_overlay(
    *,
    source_path: Path | str,
    regions: list[RecoveredPageRegion],
    selected_region: RecoveredPageRegion,
    run_id: UUID,
    settings: Settings,
) -> None:
    overlay_path = (
        settings.output_path
        / "slide-recovery"
        / "region-overlays"
        / f"{run_id}_{selected_region.id}.png"
    )
    overlay_source = source_path if isinstance(source_path, Path) else Path(source_path)
    try:
        render_region_overlay(
            overlay_source,
            regions,
            overlay_path,
            highlight_region_id=selected_region.id,
        )
        st.image(
            str(overlay_path),
            caption="静态预览（交互画布不可用，请使用下方数值编辑）",
            use_container_width=True,
        )
    except Exception as exc:
        st.warning(f"区域叠加预览失败：{format_user_error(exc)}")
        st.image(str(source_path), caption="源页面", use_container_width=True)


def _render_merge_split_controls(
    *,
    regions: list[RecoveredPageRegion],
    selected_region: RecoveredPageRegion,
    selected_index: int,
    option_labels: list[str],
    run_id: UUID,
    selected_key: str,
    key_prefix: str,
) -> None:
    st.markdown("##### 合并 / 拆分")
    merge_key = _merge_selection_session_key(run_id)
    stored_merge = st.session_state.get(merge_key)
    default_merge = stored_merge if isinstance(stored_merge, list) else []
    default_merge = [label for label in default_merge if label in option_labels]

    merge_labels = st.multiselect(
        "合并区域（多选）",
        options=option_labels,
        default=default_merge,
        key=f"{key_prefix}_merge_select",
    )
    st.session_state[merge_key] = merge_labels

    col_merge, col_split_axis, col_split_ratio = st.columns([1.2, 1, 1])
    with col_merge:
        merge_clicked = st.button(
            "合并选中区域",
            key=f"{key_prefix}_merge",
            disabled=len(merge_labels) < 2,
        )
    with col_split_axis:
        split_axis = st.radio(
            "拆分方向",
            options=["vertical", "horizontal"],
            format_func=lambda value: "左右拆分" if value == "vertical" else "上下拆分",
            horizontal=True,
            key=f"{key_prefix}_split_axis",
        )
    with col_split_ratio:
        split_ratio = st.slider(
            "拆分比例",
            min_value=0.1,
            max_value=0.9,
            value=0.5,
            step=0.05,
            key=f"{key_prefix}_split_ratio",
        )

    split_clicked = st.button(
        "拆分当前区域",
        key=f"{key_prefix}_split",
        disabled=len(regions) >= 40,
    )

    if merge_clicked:
        try:
            selected_ids = [regions[option_labels.index(label)].id for label in merge_labels]
            merged_regions = merge_regions(regions, selected_ids)
            _save_draft_regions(run_id, merged_regions)
            st.session_state[selected_key] = len(merged_regions) - 1
            st.session_state[merge_key] = []
            st.rerun()
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        except Exception as exc:
            st.error(format_user_error(exc))

    if split_clicked:
        try:
            first, second = split_region(
                selected_region,
                axis=split_axis,
                ratio=split_ratio,
            )
            split_regions = replace_region(regions, selected_region.id, [first, second])
            _save_draft_regions(run_id, split_regions)
            st.session_state[selected_key] = selected_index + 1
            st.session_state[merge_key] = []
            st.rerun()
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        except Exception as exc:
            st.error(format_user_error(exc))


def _render_region_form(
    region: RecoveredPageRegion,
    *,
    key_prefix: str,
) -> RecoveredPageRegion:
    st.markdown("##### 区域属性")
    col_x, col_y, col_w, col_h = st.columns(4)
    with col_x:
        x = st.number_input("X", min_value=0.0, max_value=1.0, value=float(region.bbox.x), step=0.01, key=f"{key_prefix}_x")
    with col_y:
        y = st.number_input("Y", min_value=0.0, max_value=1.0, value=float(region.bbox.y), step=0.01, key=f"{key_prefix}_y")
    with col_w:
        width = st.number_input("宽", min_value=0.01, max_value=1.0, value=float(region.bbox.width), step=0.01, key=f"{key_prefix}_w")
    with col_h:
        height = st.number_input("高", min_value=0.01, max_value=1.0, value=float(region.bbox.height), step=0.01, key=f"{key_prefix}_h")

    region_type = st.selectbox(
        "区域类型",
        options=list(REGION_TYPE_OPTIONS),
        index=list(REGION_TYPE_OPTIONS).index(region.region_type),
        format_func=lambda value: REGION_TYPE_LABELS_ZH.get(value, value),
        key=f"{key_prefix}_type",
    )
    semantic_role = st.text_input(
        "语义角色",
        value=region.semantic_role or "",
        key=f"{key_prefix}_role",
    )
    recovered_text = region.recovered_text or ""
    if region_type == "text":
        recovered_text = st.text_area(
            "识别文字",
            value=recovered_text,
            height=80,
            key=f"{key_prefix}_text",
        )

    col_bitmap, col_whole = st.columns(2)
    with col_bitmap:
        bitmap_fallback = st.checkbox(
            "Bitmap 降级",
            value=region.bitmap_fallback,
            key=f"{key_prefix}_bitmap",
        )
    with col_whole:
        keep_whole_drawing = st.checkbox(
            "保持整图图纸",
            value=region.keep_whole_drawing,
            key=f"{key_prefix}_whole",
        )

    source_asset_uri = st.text_input(
        "素材 URI（可选）",
        value=region.source_asset_uri or "",
        key=f"{key_prefix}_asset",
    )

    updated = region.model_copy(
        update={
            "region_type": region_type,
            "semantic_role": semantic_role or None,
            "recovered_text": recovered_text or None,
            "bitmap_fallback": bitmap_fallback,
            "keep_whole_drawing": keep_whole_drawing,
            "source_asset_uri": source_asset_uri or None,
        }
    )
    return sanitize_region(
        updated.model_copy(
            update={
                "bbox": normalize_bbox_values(x=x, y=y, width=width, height=height),
            }
        )
    )


def normalize_bbox_values(*, x: float, y: float, width: float, height: float) -> NormalizedBox:
    from archium.application.slide_recovery_region_edit_service import normalize_bbox

    return normalize_bbox(x=x, y=y, width=width, height=height)

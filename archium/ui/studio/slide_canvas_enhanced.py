"""Center canvas preview for Presentation Studio with interactive editing."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from archium.domain.visual.enums import LayoutIssueSeverity
from archium.domain.visual.layout import LayoutPlan
from archium.ui.label_map import entity_label, field_label
from archium.ui.layout_family_ui import format_layout_family_label
from archium.ui.studio.element_labels import format_element_label
from archium.ui.visual_service import SlideVisualSnapshot


def parse_canvas_editor_event(value: object) -> tuple[str, str | None, float | None, float | None, float | None, float | None, bool]:
    """Return event kind, element id, geometry in percent, and preserve-aspect flag.

    Legacy flat tuple for move/resize/select/editText. Prefer typed events from
    ``archium.ui.components.canvas_editor.parse_canvas_editor_event`` for new kinds.
    """
    from archium.ui.components.canvas_editor import parse_canvas_editor_event as _parse

    event = _parse(value)
    if event is None:
        return "none", None, None, None, None, None, False
    if isinstance(event, str):
        return "select", event, None, None, None, None, False
    if event["type"] == "move":
        return "move", str(event["elementId"]), float(event["x"]), float(event["y"]), None, None, False
    if event["type"] == "resize":
        return (
            "resize",
            str(event["elementId"]),
            float(event["x"]),
            float(event["y"]),
            float(event["width"]),
            float(event["height"]),
            bool(event.get("preserveAspectRatio", False)),
        )
    if event["type"] == "editText":
        return "editText", str(event["elementId"]), None, None, None, None, False
    if event["type"] == "commitText":
        return "commitText", str(event["elementId"]), None, None, None, None, False
    if event["type"] == "commitReplaceAsset":
        return "commitReplaceAsset", str(event["elementId"]), None, None, None, None, False
    if event["type"] == "requestReplaceAsset":
        return "requestReplaceAsset", str(event["elementId"]), None, None, None, None, False
    if event["type"] == "moveMany":
        return "moveMany", None, None, None, None, None, False
    return "select", event.get("elementId"), None, None, None, None, False

_SEVERITY_COLORS = {
    LayoutIssueSeverity.CRITICAL: "#b42318",
    LayoutIssueSeverity.ERROR: "#d92d20",
    LayoutIssueSeverity.WARNING: "#b54708",
    LayoutIssueSeverity.INFO: "#175cd3",
}


def preview_file_exists(preview_path: str | None) -> bool:
    return bool(preview_path and Path(preview_path).is_file())


def can_render_interactive_canvas(
    *,
    use_interactive_canvas: bool,
    plan: LayoutPlan | None,
    preview_path: str | None,
) -> bool:
    return bool(use_interactive_canvas and plan is not None and preview_file_exists(preview_path))


def _preview_caption(kind: str | None) -> str:
    if kind == "scene":
        return "RenderScene 真实预览（Studio Canvas 视觉真相源）"
    if kind == "screenshot":
        return "PPTX 截图预览（来自最近一次视觉编排导出）"
    if kind == "wireframe":
        return "版式线框预览（由 LayoutPlan 几何自动生成；无 RenderScene 时的降级）"
    return "暂无预览。生成版式后将编译 RenderScene；必要时可降级为线框。"


def _render_empty_preview_placeholder(*, has_layout_plan: bool = False) -> None:
    hint = (
        "版式已生成，暂无预览图。运行带 PPTX 导出的视觉编排后可显示截图。"
        if has_layout_plan
        else "请先生成版式，或运行带 PPTX 导出的视觉编排"
    )
    st.markdown(
        '<div style="border:1px dashed #d8d6d0;border-radius:8px;'
        'padding:3rem 1rem;text-align:center;color:#8a8780;background:#faf9f7;">'
        "暂无页面预览<br>"
        f"<span style='font-size:0.85rem;'>{hint}</span>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_plan_wireframe(plan: LayoutPlan, *, selected_element_id: str | None) -> None:
    """Render element geometry when no raster preview is available."""
    width = float(plan.page_width or 10)
    height = float(plan.page_height or 5.625)
    boxes: list[str] = []
    for element in plan.elements:
        left = max(0.0, element.x / width * 100)
        top = max(0.0, element.y / height * 100)
        box_width = max(1.0, element.width / width * 100)
        box_height = max(1.0, element.height / height * 100)
        if element.id == selected_element_id:
            border = "2px solid #175cd3"
            background = "rgba(23, 92, 211, 0.08)"
        else:
            border = "1px solid #98a2b3"
            background = "rgba(152, 162, 179, 0.12)"
        boxes.append(
            "<div style="
            f"'position:absolute;left:{left:.2f}%;top:{top:.2f}%;"
            f"width:{box_width:.2f}%;height:{box_height:.2f}%;"
            f"border:{border};background:{background};border-radius:4px;'></div>"
        )
    st.caption("版式线框预览（由 LayoutPlan 几何自动生成）")
    st.markdown(
        "<div style='position:relative;width:100%;aspect-ratio:16/9;"
        "background:#faf9f7;border:1px solid #eceae4;border-radius:8px;'>"
        + "".join(boxes)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_validation_overlay(
    *,
    slide_snapshot: SlideVisualSnapshot,
    selected_element_id: str | None,
) -> None:
    validation = slide_snapshot.validation
    plan = slide_snapshot.layout_plan
    if validation is None or not validation.issues:
        return

    issue_element_ids: set[str] = set()
    for issue in validation.issues:
        issue_element_ids.update(issue.element_ids)

    st.markdown("**版式问题标注**")
    for issue in validation.issues[:8]:
        color = _SEVERITY_COLORS.get(issue.severity, "#667085")
        element_hint = ""
        if issue.element_ids:
            element_hint = f" · 元素 {', '.join(issue.element_ids[:3])}"
        st.markdown(
            f"<span style='color:{color};font-weight:600;'>{issue.severity.value}</span>"
            f" · {issue.message}{element_hint}",
            unsafe_allow_html=True,
        )

    if plan is None or not issue_element_ids:
        return

    width = float(plan.page_width or 10)
    height = float(plan.page_height or 5.625)
    boxes: list[str] = []
    for element in plan.elements:
        if element.id not in issue_element_ids and element.id != selected_element_id:
            continue
        left = max(0.0, element.x / width * 100)
        top = max(0.0, element.y / height * 100)
        box_width = max(1.0, element.width / width * 100)
        box_height = max(1.0, element.height / height * 100)
        if element.id == selected_element_id:
            border = "2px solid #175cd3"
            background = "rgba(23, 92, 211, 0.08)"
        else:
            border = "2px solid #d92d20"
            background = "rgba(217, 45, 32, 0.10)"
        boxes.append(
            "<div style="
            f"'position:absolute;left:{left:.2f}%;top:{top:.2f}%;"
            f"width:{box_width:.2f}%;height:{box_height:.2f}%;"
            f"border:{border};background:{background};border-radius:4px;'></div>"
        )
    if boxes:
        st.caption("线框标注：蓝框为当前元素，红框为问题元素")
        st.markdown(
            "<div style='position:relative;width:100%;aspect-ratio:16/9;"
            "background:#faf9f7;border:1px solid #eceae4;border-radius:8px;'>"
            + "".join(boxes)
            + "</div>",
            unsafe_allow_html=True,
        )


def _render_static_or_empty_state(
    *,
    slide_snapshot: SlideVisualSnapshot,
    selected_element_id: str | None,
) -> None:
    preview_path = slide_snapshot.preview_image
    plan = slide_snapshot.layout_plan
    if preview_file_exists(preview_path):
        st.image(preview_path, use_container_width=True)
        st.caption(_preview_caption(slide_snapshot.preview_kind))
    elif plan is not None and plan.elements:
        _render_plan_wireframe(plan, selected_element_id=selected_element_id)
    else:
        _render_empty_preview_placeholder(has_layout_plan=plan is not None)

    _render_validation_overlay(
        slide_snapshot=slide_snapshot,
        selected_element_id=selected_element_id,
    )


def _handle_canvas_move(
    *,
    slide_id: object,
    plan: LayoutPlan,
    element_id: str,
    x_percent: float,
    y_percent: float,
) -> None:
    from archium.ui.studio.canvas_command_bridge import apply_canvas_move_event

    apply_canvas_move_event(
        slide_id=slide_id,  # type: ignore[arg-type]
        plan=plan,
        element_id=element_id,
        x_percent=x_percent,
        y_percent=y_percent,
    )


def _handle_canvas_resize(
    *,
    slide_id: object,
    plan: LayoutPlan,
    element_id: str,
    x_percent: float,
    y_percent: float,
    width_percent: float,
    height_percent: float,
    preserve_aspect_ratio: bool = False,
) -> None:
    from archium.ui.studio.canvas_command_bridge import apply_canvas_resize_event

    apply_canvas_resize_event(
        slide_id=slide_id,  # type: ignore[arg-type]
        plan=plan,
        element_id=element_id,
        x_percent=x_percent,
        y_percent=y_percent,
        width_percent=width_percent,
        height_percent=height_percent,
        preserve_aspect_ratio=preserve_aspect_ratio,
    )


def _load_comment_anchors(
    slide_snapshot: SlideVisualSnapshot,
    plan: LayoutPlan,
) -> list[dict]:
    """Active ElementComment overlays for the interactive canvas."""
    from uuid import UUID

    from archium.infrastructure.database.session import get_session
    from archium.ui.studio.comment_canvas_anchors import build_comment_canvas_anchors

    focused_id = st.session_state.get("studio_focused_comment_id")
    focused_uuid: UUID | None = None
    if isinstance(focused_id, str) and focused_id:
        try:
            focused_uuid = UUID(focused_id)
        except ValueError:
            focused_uuid = None
    focused_region = st.session_state.get("studio_comment_region_bbox")
    if not isinstance(focused_region, dict):
        focused_region = None

    try:
        with get_session() as session:
            from archium.application.visual.element_comment_service import (
                ElementCommentService,
            )

            comments = ElementCommentService(session).list_for_slide(slide_snapshot.slide.id)
    except Exception:
        comments = []

    return build_comment_canvas_anchors(
        comments,
        page_width=float(plan.page_width or 10.0),
        page_height=float(plan.page_height or 5.625),
        scene=slide_snapshot.render_scene,
        focused_comment_id=focused_uuid,
        focused_region_bbox=focused_region,
    )


def _render_interactive_canvas(
    *,
    slide_snapshot: SlideVisualSnapshot,
    plan: LayoutPlan,
    preview_path: str,
    selected_element_id: str | None,
    project_id: object | None = None,
) -> bool:
    from archium.ui.components.canvas_editor import (
        CanvasEditorUnavailableError,
        canvas_editor,
        canvas_editor_unavailable_reason,
    )
    from archium.ui.components.canvas_editor import (
        parse_canvas_editor_event as parse_typed_event,
    )
    from archium.ui.studio.canvas_command_bridge import (
        apply_canvas_commit_replace_asset_event,
        apply_canvas_commit_text_event,
        apply_canvas_move_event,
        apply_canvas_move_many_event,
        apply_canvas_resize_event,
        canvas_component_key,
        set_studio_selection,
    )

    selected_ids = list(st.session_state.get("studio_selected_element_ids") or [])
    if not selected_ids and selected_element_id:
        selected_ids = [selected_element_id]

    assets: list[dict[str, str]] = []
    if project_id is not None:
        try:
            from uuid import UUID

            from archium.application.asset_board_service import AssetBoardService
            from archium.infrastructure.database.session import get_session

            with get_session() as session:
                for asset in AssetBoardService(session).list_project_assets(UUID(str(project_id))):
                    assets.append(
                        {
                            "id": str(asset.id),
                            "label": asset.filename,
                            "storageUri": str(getattr(asset, "storage_uri", "") or asset.id),
                        }
                    )
        except Exception:
            assets = []

    comment_anchors = _load_comment_anchors(slide_snapshot, plan)

    try:
        canvas_event = canvas_editor(
            image_url=preview_path,
            layout_plan=plan,
            render_scene=slide_snapshot.render_scene,
            selected_element_id=selected_element_id,
            selected_element_ids=selected_ids,
            assets=assets,
            comment_anchors=comment_anchors,
            show_labels=True,
            show_all_borders=True,
            key=canvas_component_key(slide_snapshot.slide.id),
        )
    except CanvasEditorUnavailableError as exc:
        reason = canvas_editor_unavailable_reason() or str(exc)
        st.warning(f"交互式画布不可用，已切换为静态预览。{reason}")
        return False
    except Exception as exc:
        st.warning(f"交互式画布加载失败，已切换为静态预览：{exc}")
        return False

    typed = parse_typed_event(canvas_event)
    slide_id = slide_snapshot.slide.id

    if typed is not None and not isinstance(typed, str):
        if typed["type"] == "moveMany":
            moves = [
                (str(item["elementId"]), float(item["x"]), float(item["y"]))
                for item in typed["moves"]
            ]
            apply_canvas_move_many_event(slide_id=slide_id, plan=plan, moves=moves)
            return True

        elif typed["type"] == "commitText":
            apply_canvas_commit_text_event(
                slide_id=slide_id,
                element_id=str(typed["elementId"]),
                text=str(typed["text"]),
            )
            return True

        elif typed["type"] == "commitReplaceAsset":
            apply_canvas_commit_replace_asset_event(
                slide_id=slide_id,
                element_id=str(typed["elementId"]),
                asset_id=str(typed["assetId"]),
            )
            return True

        elif typed["type"] == "requestReplaceAsset":
            set_studio_selection([str(typed["elementId"])])
            st.session_state["studio_focus_asset_replace"] = str(typed["elementId"])
            st.rerun()
            return True

        elif typed["type"] == "select":
            ids = list(typed.get("elementIds") or [])
            if not ids and typed.get("elementId"):
                ids = [str(typed["elementId"])]
            current = list(st.session_state.get("studio_selected_element_ids") or [])
            if not current and selected_element_id:
                current = [selected_element_id]
            if ids != current:
                set_studio_selection(ids)
                st.rerun()
            st.caption(_preview_caption(slide_snapshot.preview_kind))
            return True

    (
        event_kind,
        element_id,
        x_percent,
        y_percent,
        width_percent,
        height_percent,
        preserve_aspect_ratio,
    ) = parse_canvas_editor_event(canvas_event)
    if event_kind == "move" and element_id and x_percent is not None and y_percent is not None:
        apply_canvas_move_event(
            slide_id=slide_id,
            plan=plan,
            element_id=element_id,
            x_percent=x_percent,
            y_percent=y_percent,
        )
        return True

    if (
        event_kind == "resize"
        and element_id
        and x_percent is not None
        and y_percent is not None
        and width_percent is not None
        and height_percent is not None
    ):
        apply_canvas_resize_event(
            slide_id=slide_id,
            plan=plan,
            element_id=element_id,
            x_percent=x_percent,
            y_percent=y_percent,
            width_percent=width_percent,
            height_percent=height_percent,
            preserve_aspect_ratio=preserve_aspect_ratio,
        )
        return True

    if event_kind == "editText" and element_id:
        set_studio_selection([element_id])
        st.session_state["studio_focus_text_edit"] = element_id
        st.rerun()

    st.caption(_preview_caption(slide_snapshot.preview_kind))
    return True


def render_slide_canvas(
    *,
    slide_snapshot: SlideVisualSnapshot | None,
    advanced: bool,
    use_interactive_canvas: bool = True,
    project_id: object | None = None,
) -> None:
    """Render the selected slide preview area."""
    st.markdown("**页面预览**")
    if slide_snapshot is None:
        st.info("请选择左侧页面。")
        return

    slide = slide_snapshot.slide
    plan = slide_snapshot.layout_plan
    selected_element_id = st.session_state.get("studio_selected_element_id")
    selected_element_id_str = str(selected_element_id) if selected_element_id else None

    header_cols = st.columns([3, 1])
    with header_cols[0]:
        st.markdown(f"#### P{slide.order + 1} · {slide.title}")
        st.caption(slide.message or "（无核心信息）")
    with header_cols[1]:
        if slide_snapshot.validation is not None:
            valid = slide_snapshot.validation.valid
            st.metric(
                "版式质量",
                f"{slide_snapshot.validation.score:.2f}",
                delta="通过" if valid else "需修复",
                delta_color="normal" if valid else "inverse",
            )

    preview_path = slide_snapshot.preview_image
    interactive_ready = can_render_interactive_canvas(
        use_interactive_canvas=use_interactive_canvas,
        plan=plan,
        preview_path=preview_path,
    )

    rendered_interactive = False
    if interactive_ready and plan is not None and preview_path is not None:
        rendered_interactive = _render_interactive_canvas(
            slide_snapshot=slide_snapshot,
            plan=plan,
            preview_path=preview_path,
            selected_element_id=selected_element_id_str,
            project_id=project_id,
        )

    if not rendered_interactive:
        _render_static_or_empty_state(
            slide_snapshot=slide_snapshot,
            selected_element_id=selected_element_id_str,
        )

    if plan is not None:
        highlight = ""
        if selected_element_id_str and plan.element_by_id(selected_element_id_str) is not None:
            element = plan.element_by_id(selected_element_id_str)
            if element is not None:
                highlight = (
                    f" · 当前元素：{format_element_label(element_id=element.id, role=element.role)}"
                )
        st.caption(
            f"版式：{format_layout_family_label(plan.layout_family)} · "
            f"变体 {plan.layout_variant} · 留白 {plan.whitespace_ratio:.0%}{highlight}"
        )

    with st.expander(entity_label("SlideSpec", advanced=advanced), expanded=False):
        st.write(f"{field_label('title', advanced=advanced)}：{slide.title}")
        st.write(f"{field_label('message', advanced=advanced)}：{slide.message or '—'}")
        st.write(f"状态：`{slide.status.value}`")
        if advanced:
            st.write(f"SlideSpec ID：`{slide.id}`")

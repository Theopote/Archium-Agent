"""Canvas Editor - Streamlit custom component for interactive slide editing."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene
from archium.ui.components.canvas_editor.runtime import (
    CanvasEditorUnavailableError,
    canvas_editor_available,
    canvas_editor_release_mode,
    canvas_editor_unavailable_reason,
    get_canvas_editor_component,
    reset_canvas_editor_component_cache,
)

_BUILD_EXPORTS = frozenset(
    {"build_canvas_editor", "canvas_editor_build_dir", "is_canvas_editor_built"}
)


class CanvasSelectEvent(TypedDict):
    type: Literal["select"]
    elementId: str | None


class CanvasMoveEvent(TypedDict):
    type: Literal["move"]
    elementId: str
    x: float
    y: float


class CanvasResizeEvent(TypedDict):
    type: Literal["resize"]
    elementId: str
    x: float
    y: float
    width: float
    height: float
    preserveAspectRatio: NotRequired[bool]


class CanvasEditTextEvent(TypedDict):
    type: Literal["editText"]
    elementId: str


CanvasEditorEvent = (
    str | CanvasSelectEvent | CanvasMoveEvent | CanvasResizeEvent | CanvasEditTextEvent | None
)


def parse_canvas_editor_event(value: object) -> CanvasEditorEvent:
    """Normalize legacy string selections and structured canvas events."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        event_type = value.get("type")
        if event_type == "move":
            element_id = value.get("elementId")
            x = value.get("x")
            y = value.get("y")
            if element_id is not None and x is not None and y is not None:
                return CanvasMoveEvent(
                    type="move",
                    elementId=str(element_id),
                    x=float(x),
                    y=float(y),
                )
        if event_type == "resize":
            element_id = value.get("elementId")
            x = value.get("x")
            y = value.get("y")
            width = value.get("width")
            height = value.get("height")
            if (
                element_id is not None
                and x is not None
                and y is not None
                and width is not None
                and height is not None
            ):
                return CanvasResizeEvent(
                    type="resize",
                    elementId=str(element_id),
                    x=float(x),
                    y=float(y),
                    width=float(width),
                    height=float(height),
                    preserveAspectRatio=bool(value.get("preserveAspectRatio", False)),
                )
        if event_type == "editText":
            element_id = value.get("elementId")
            if element_id is not None:
                return CanvasEditTextEvent(type="editText", elementId=str(element_id))
        if event_type == "select":
            element_id = value.get("elementId")
            return CanvasSelectEvent(type="select", elementId=str(element_id) if element_id else None)
    return None


def __getattr__(name: str) -> Any:
    if name in _BUILD_EXPORTS:
        from archium.ui.components.canvas_editor import build_frontend as _build_frontend

        return getattr(_build_frontend, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def canvas_editor(
    image_url: str,
    layout_plan: LayoutPlan,
    *,
    render_scene: RenderScene | None = None,
    selected_element_id: str | None = None,
    show_labels: bool = True,
    show_all_borders: bool = True,
    key: str | None = None,
) -> CanvasEditorEvent:
    """
    Render an interactive canvas editor for slide elements.

    Raises:
        CanvasEditorUnavailableError: When the frontend build or dev server is missing.
    """
    component_func = get_canvas_editor_component()
    elements = convert_elements_for_canvas(layout_plan, render_scene=render_scene)
    component_value = component_func(
        imageUrl=image_url,
        elements=elements,
        selectedId=selected_element_id,
        showLabels=show_labels,
        showAllBorders=show_all_borders,
        key=key,
        default=None,
    )
    return parse_canvas_editor_event(component_value)


def convert_elements_for_canvas(
    layout_plan: LayoutPlan,
    *,
    render_scene: RenderScene | None = None,
) -> list[dict[str, Any]]:
    """Convert layout/scene geometry to canvas overlay elements."""
    from archium.application.visual.studio_command_executor import node_geometry_locked
    from archium.domain.visual.element_lock import canvas_geometry_locked

    page_width = float(layout_plan.page_width or 10.0)
    page_height = float(layout_plan.page_height or 5.625)

    elements: list[dict[str, Any]] = []
    for element in layout_plan.elements:
        node = None
        if render_scene is not None:
            node = render_scene.node_by_layout_element_id(element.id) or render_scene.node_by_id(
                element.id
            )
            if node is not None and not node.visible:
                continue

        x = node.x if node is not None else element.x
        y = node.y if node is not None else element.y
        width = node.width if node is not None else element.width
        height = node.height if node is not None else element.height
        locked = node_geometry_locked(node) if node is not None else canvas_geometry_locked(element)

        content_type = (
            element.content_type.value
            if hasattr(element.content_type, "value")
            else str(element.content_type)
        )
        elements.append(
            {
                "id": element.id,
                "x": (x / page_width) * 100,
                "y": (y / page_height) * 100,
                "width": (width / page_width) * 100,
                "height": (height / page_height) * 100,
                "role": element.role.value if hasattr(element.role, "value") else str(element.role),
                "locked": locked,
                "content_type": content_type,
                "text_content": element.text_content or "",
            }
        )
    return elements


def _convert_elements(layout_plan: LayoutPlan) -> list[dict[str, Any]]:
    """Backward-compatible wrapper for tests."""
    return convert_elements_for_canvas(layout_plan)


__all__ = [
    "CanvasEditorUnavailableError",
    "CanvasEditorEvent",
    "CanvasEditTextEvent",
    "CanvasMoveEvent",
    "CanvasResizeEvent",
    "CanvasSelectEvent",
    "build_canvas_editor",
    "canvas_editor",
    "canvas_editor_available",
    "canvas_editor_build_dir",
    "canvas_editor_release_mode",
    "canvas_editor_unavailable_reason",
    "convert_elements_for_canvas",
    "is_canvas_editor_built",
    "parse_canvas_editor_event",
    "reset_canvas_editor_component_cache",
]

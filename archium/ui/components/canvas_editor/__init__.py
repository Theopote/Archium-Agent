"""Canvas Editor - Streamlit custom component for interactive slide editing."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from archium.domain.visual.layout import LayoutPlan
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


CanvasEditorEvent = str | CanvasSelectEvent | CanvasMoveEvent | None


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
    elements = _convert_elements(layout_plan)
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


def _convert_elements(layout_plan: LayoutPlan) -> list[dict[str, Any]]:
    """Convert LayoutPlan elements to component format."""
    page_width = float(layout_plan.page_width or 10.0)
    page_height = float(layout_plan.page_height or 5.625)

    elements: list[dict[str, Any]] = []
    for element in layout_plan.elements:
        elements.append(
            {
                "id": element.id,
                "x": (element.x / page_width) * 100,
                "y": (element.y / page_height) * 100,
                "width": (element.width / page_width) * 100,
                "height": (element.height / page_height) * 100,
                "role": element.role.value if hasattr(element.role, "value") else str(element.role),
                "locked": element.locked,
                "text_content": element.text_content or "",
            }
        )
    return elements


__all__ = [
    "CanvasEditorUnavailableError",
    "CanvasEditorEvent",
    "CanvasMoveEvent",
    "CanvasSelectEvent",
    "build_canvas_editor",
    "canvas_editor",
    "canvas_editor_available",
    "canvas_editor_build_dir",
    "canvas_editor_release_mode",
    "canvas_editor_unavailable_reason",
    "is_canvas_editor_built",
    "parse_canvas_editor_event",
    "reset_canvas_editor_component_cache",
]

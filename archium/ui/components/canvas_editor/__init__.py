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
    elementIds: NotRequired[list[str]]


class CanvasMoveEvent(TypedDict):
    type: Literal["move"]
    elementId: str
    x: float
    y: float


class CanvasMoveManyItem(TypedDict):
    elementId: str
    x: float
    y: float


class CanvasMoveManyEvent(TypedDict):
    type: Literal["moveMany"]
    moves: list[CanvasMoveManyItem]


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


class CanvasCommitTextEvent(TypedDict):
    type: Literal["commitText"]
    elementId: str
    text: str


class CanvasCommitReplaceAssetEvent(TypedDict):
    type: Literal["commitReplaceAsset"]
    elementId: str
    assetId: str


class CanvasCommitDeleteEvent(TypedDict):
    type: Literal["commitDelete"]
    elementId: str


class CanvasCommitDuplicateEvent(TypedDict):
    type: Literal["commitDuplicate"]
    elementIds: list[str]


class CanvasRequestReplaceAssetEvent(TypedDict):
    type: Literal["requestReplaceAsset"]
    elementId: str


CanvasEditorEvent = (
    str
    | CanvasSelectEvent
    | CanvasMoveEvent
    | CanvasMoveManyEvent
    | CanvasResizeEvent
    | CanvasEditTextEvent
    | CanvasCommitTextEvent
    | CanvasCommitReplaceAssetEvent
    | CanvasCommitDeleteEvent
    | CanvasCommitDuplicateEvent
    | CanvasRequestReplaceAssetEvent
    | None
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
        if event_type == "moveMany":
            raw_moves = value.get("moves")
            if isinstance(raw_moves, list) and raw_moves:
                moves: list[CanvasMoveManyItem] = []
                for item in raw_moves:
                    if not isinstance(item, dict):
                        continue
                    element_id = item.get("elementId")
                    x = item.get("x")
                    y = item.get("y")
                    if element_id is None or x is None or y is None:
                        continue
                    moves.append(
                        CanvasMoveManyItem(
                            elementId=str(element_id),
                            x=float(x),
                            y=float(y),
                        )
                    )
                if moves:
                    return CanvasMoveManyEvent(type="moveMany", moves=moves)
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
        if event_type == "commitText":
            element_id = value.get("elementId")
            text = value.get("text")
            if element_id is not None and text is not None:
                return CanvasCommitTextEvent(
                    type="commitText",
                    elementId=str(element_id),
                    text=str(text),
                )
        if event_type == "commitReplaceAsset":
            element_id = value.get("elementId")
            asset_id = value.get("assetId")
            if element_id is not None and asset_id is not None:
                return CanvasCommitReplaceAssetEvent(
                    type="commitReplaceAsset",
                    elementId=str(element_id),
                    assetId=str(asset_id),
                )
        if event_type == "commitDelete":
            element_id = value.get("elementId")
            if element_id is not None:
                return CanvasCommitDeleteEvent(
                    type="commitDelete",
                    elementId=str(element_id),
                )
        if event_type == "commitDuplicate":
            raw_ids = value.get("elementIds")
            element_ids: list[str] = []
            if isinstance(raw_ids, list):
                element_ids = [str(item) for item in raw_ids if item]
            single = value.get("elementId")
            if not element_ids and single is not None:
                element_ids = [str(single)]
            if element_ids:
                return CanvasCommitDuplicateEvent(
                    type="commitDuplicate",
                    elementIds=element_ids,
                )
        if event_type == "requestReplaceAsset":
            element_id = value.get("elementId")
            if element_id is not None:
                return CanvasRequestReplaceAssetEvent(
                    type="requestReplaceAsset",
                    elementId=str(element_id),
                )
        if event_type == "select":
            element_id = value.get("elementId")
            raw_ids = value.get("elementIds")
            element_ids: list[str] = []
            if isinstance(raw_ids, list):
                element_ids = [str(item) for item in raw_ids if item]
            elif element_id:
                element_ids = [str(element_id)]
            return CanvasSelectEvent(
                type="select",
                elementId=str(element_id) if element_id else None,
                elementIds=element_ids,
            )
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
    selected_element_ids: list[str] | None = None,
    assets: list[dict[str, str]] | None = None,
    comment_anchors: list[dict[str, Any]] | None = None,
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
    ids = list(selected_element_ids or [])
    if not ids and selected_element_id:
        ids = [selected_element_id]
    component_value = component_func(
        imageUrl=image_url,
        elements=elements,
        selectedId=ids[0] if ids else selected_element_id,
        selectedIds=ids,
        assets=assets or [],
        commentAnchors=comment_anchors or [],
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
    from archium.domain.visual.render_scene import TextNode

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
        text_content = element.text_content or ""
        if isinstance(node, TextNode):
            text_content = node.text
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
                "text_content": text_content,
            }
        )
    return elements


def _convert_elements(layout_plan: LayoutPlan) -> list[dict[str, Any]]:
    """Backward-compatible wrapper for tests."""
    return convert_elements_for_canvas(layout_plan)


__all__ = [
    "CanvasEditorUnavailableError",
    "CanvasEditorEvent",
    "CanvasCommitDeleteEvent",
    "CanvasCommitDuplicateEvent",
    "CanvasCommitReplaceAssetEvent",
    "CanvasCommitTextEvent",
    "CanvasEditTextEvent",
    "CanvasMoveEvent",
    "CanvasMoveManyEvent",
    "CanvasRequestReplaceAssetEvent",
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

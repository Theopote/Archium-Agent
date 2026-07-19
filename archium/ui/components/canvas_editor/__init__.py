"""Canvas Editor - Streamlit custom component for interactive slide editing."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

from archium.domain.visual.layout import LayoutPlan

# Create a _RELEASE constant for production builds
_RELEASE = True

# Declare component (production mode: use pre-built frontend)
if _RELEASE:
    parent_dir = Path(__file__).parent
    build_dir = parent_dir / "frontend" / "build"
    _component_func = components.declare_component(
        "canvas_editor",
        path=str(build_dir),
    )
else:
    # Development mode: use React dev server
    _component_func = components.declare_component(
        "canvas_editor",
        url="http://localhost:3000",
    )


def canvas_editor(
    image_url: str,
    layout_plan: LayoutPlan,
    *,
    selected_element_id: str | None = None,
    show_labels: bool = True,
    show_all_borders: bool = True,
    key: str | None = None,
) -> str | None:
    """
    Render an interactive canvas editor for slide elements.

    Args:
        image_url: URL or path to the slide preview image
        layout_plan: LayoutPlan containing element positions
        selected_element_id: Currently selected element ID (optional)
        show_labels: Show element labels on hover/select
        show_all_borders: Show borders for all elements (not just selected/hovered)
        key: Streamlit component key

    Returns:
        The ID of the clicked element, or None if canvas was clicked
    """
    # Convert LayoutPlan elements to component format
    elements = _convert_elements(layout_plan)

    # Call the component
    component_value = _component_func(
        imageUrl=image_url,
        elements=elements,
        selectedId=selected_element_id,
        showLabels=show_labels,
        showAllBorders=show_all_borders,
        key=key,
        default=None,
    )

    return component_value


def _convert_elements(layout_plan: LayoutPlan) -> list[dict[str, Any]]:
    """Convert LayoutPlan elements to component format."""
    if layout_plan is None:
        return []

    page_width = float(layout_plan.page_width or 10.0)
    page_height = float(layout_plan.page_height or 5.625)

    elements = []
    for element in layout_plan.elements:
        elements.append({
            "id": element.id,
            "x": (element.x / page_width) * 100,
            "y": (element.y / page_height) * 100,
            "width": (element.width / page_width) * 100,
            "height": (element.height / page_height) * 100,
            "role": element.role.value if hasattr(element.role, "value") else str(element.role),
            "locked": element.locked,
            "text_content": element.text_content or "",
        })

    return elements


# For backward compatibility and simpler imports
__all__ = ["canvas_editor"]

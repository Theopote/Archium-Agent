"""Lazy Streamlit component registration for Canvas Editor."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from archium.ui.components.canvas_editor.build_frontend import (
    canvas_editor_build_dir,
    is_canvas_editor_built,
)

_COMPONENT_NAME = "canvas_editor"
_COMPONENT_ROOT = Path(__file__).resolve().parent
_DEV_SERVER_URL = os.environ.get("ARCHIUM_CANVAS_EDITOR_DEV_URL", "http://localhost:3000")

_component_func: Callable[..., Any] | None = None
_component_error: str | None = None


class CanvasEditorUnavailableError(RuntimeError):
    """Raised when the canvas editor component cannot be loaded."""


def canvas_editor_release_mode() -> bool:
    """Return True when using pre-built frontend assets (production mode)."""
    return os.environ.get("ARCHIUM_CANVAS_EDITOR_DEV", "").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }


def canvas_editor_available() -> bool:
    """Return True when the interactive canvas can likely be rendered."""
    if not canvas_editor_release_mode():
        return True
    return is_canvas_editor_built(_COMPONENT_ROOT)


def canvas_editor_unavailable_reason() -> str | None:
    if canvas_editor_available():
        return None
    if canvas_editor_release_mode():
        build_dir = canvas_editor_build_dir(_COMPONENT_ROOT)
        return (
            "Canvas Editor frontend is not built. "
            f"Run: python -m archium.ui.components.canvas_editor.build_frontend "
            f"(expected {build_dir / 'index.html'})"
        )
    return f"Canvas Editor dev server not configured at {_DEV_SERVER_URL}"


def _declare_component() -> Callable[..., Any]:
    import streamlit.components.v1 as components

    if canvas_editor_release_mode():
        build_dir = canvas_editor_build_dir(_COMPONENT_ROOT)
        if not is_canvas_editor_built(_COMPONENT_ROOT):
            raise CanvasEditorUnavailableError(canvas_editor_unavailable_reason() or "unavailable")
        return components.declare_component(_COMPONENT_NAME, path=str(build_dir))

    return components.declare_component(_COMPONENT_NAME, url=_DEV_SERVER_URL)


def get_canvas_editor_component() -> Callable[..., Any]:
    """Return the declared Streamlit component callable (lazy, cached)."""
    global _component_func, _component_error

    if _component_func is not None:
        return _component_func
    if _component_error is not None:
        raise CanvasEditorUnavailableError(_component_error)

    try:
        _component_func = _declare_component()
    except Exception as exc:
        _component_error = str(exc)
        raise CanvasEditorUnavailableError(_component_error) from exc
    return _component_func


def reset_canvas_editor_component_cache() -> None:
    """Clear lazy component cache (for tests)."""
    global _component_func, _component_error
    _component_func = None
    _component_error = None

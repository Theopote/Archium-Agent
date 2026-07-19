"""Canvas editor runtime/build availability tests."""

from __future__ import annotations

import pytest

from archium.ui.components.canvas_editor import (
    CanvasEditorUnavailableError,
    canvas_editor_available,
    canvas_editor_unavailable_reason,
    is_canvas_editor_built,
    reset_canvas_editor_component_cache,
)
from archium.ui.components.canvas_editor.runtime import get_canvas_editor_component


def test_canvas_editor_import_does_not_require_build_at_import_time() -> None:
    """Importing the package must not fail when frontend/build is absent."""
    from archium.ui.components.canvas_editor import canvas_editor  # noqa: F401

    assert callable(canvas_editor)


def test_is_canvas_editor_built_false_for_empty_component_root(tmp_path) -> None:  # noqa: ANN001
    root = tmp_path / "canvas_editor"
    (root / "frontend").mkdir(parents=True)
    (root / "frontend" / "package.json").write_text("{}", encoding="utf-8")
    assert is_canvas_editor_built(root) is False


def test_canvas_editor_available_false_when_build_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARCHIUM_CANVAS_EDITOR_DEV", raising=False)
    monkeypatch.setattr(
        "archium.ui.components.canvas_editor.runtime.is_canvas_editor_built",
        lambda *_args, **_kwargs: False,
    )
    reset_canvas_editor_component_cache()
    assert canvas_editor_available() is False
    reason = canvas_editor_unavailable_reason()
    assert reason is not None
    assert "not built" in reason.lower() or "build_frontend" in reason


def test_get_canvas_editor_component_raises_when_build_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ARCHIUM_CANVAS_EDITOR_DEV", raising=False)
    monkeypatch.setattr(
        "archium.ui.components.canvas_editor.runtime.is_canvas_editor_built",
        lambda *_args, **_kwargs: False,
    )
    reset_canvas_editor_component_cache()
    with pytest.raises(CanvasEditorUnavailableError):
        get_canvas_editor_component()


def test_dev_mode_available_without_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCHIUM_CANVAS_EDITOR_DEV", "1")
    reset_canvas_editor_component_cache()
    assert canvas_editor_available() is True

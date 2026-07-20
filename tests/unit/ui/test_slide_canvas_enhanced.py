"""Unit tests for slide canvas preview state helpers."""

from __future__ import annotations

from archium.ui.studio.slide_canvas_enhanced import (
    can_render_interactive_canvas,
    parse_canvas_editor_event,
    preview_file_exists,
)


def test_preview_file_exists_false_for_missing_path(tmp_path) -> None:  # noqa: ANN001
    assert preview_file_exists(None) is False
    assert preview_file_exists(str(tmp_path / "missing.png")) is False


def test_preview_file_exists_true_for_existing_file(tmp_path) -> None:  # noqa: ANN001
    image = tmp_path / "slide.png"
    image.write_bytes(b"png")
    assert preview_file_exists(str(image)) is True


def test_can_render_interactive_requires_plan_and_preview(tmp_path) -> None:  # noqa: ANN001
    image = tmp_path / "slide.png"
    image.write_bytes(b"png")
    assert (
        can_render_interactive_canvas(
            use_interactive_canvas=True,
            plan=None,
            preview_path=str(image),
        )
        is False
    )
    assert (
        can_render_interactive_canvas(
            use_interactive_canvas=True,
            plan=object(),  # type: ignore[arg-type]
            preview_path=None,
        )
        is False
    )
    assert (
        can_render_interactive_canvas(
            use_interactive_canvas=False,
            plan=object(),  # type: ignore[arg-type]
            preview_path=str(image),
        )
        is False
    )
    assert (
        can_render_interactive_canvas(
            use_interactive_canvas=True,
            plan=object(),  # type: ignore[arg-type]
            preview_path=str(image),
        )
        is True
    )


def test_parse_canvas_editor_event_supports_structured_move() -> None:
    kind, element_id, x_percent, y_percent = parse_canvas_editor_event(
        {"type": "move", "elementId": "hero", "x": 12.5, "y": 30.0}
    )
    assert kind == "move"
    assert element_id == "hero"
    assert x_percent == 12.5
    assert y_percent == 30.0


def test_parse_canvas_editor_event_supports_legacy_string_select() -> None:
    kind, element_id, x_percent, y_percent = parse_canvas_editor_event("hero")
    assert kind == "select"
    assert element_id == "hero"
    assert x_percent is None
    assert y_percent is None

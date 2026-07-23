"""UI selection and Studio context warning contracts."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.ui.studio.canvas_command_bridge import set_studio_selection
from archium.ui.studio_service import StudioPresentationContext, studio_readiness_label
from archium.ui.visual_service import PresentationVisualSnapshot


def test_set_studio_selection_keeps_singular_and_plural_in_sync(monkeypatch) -> None:
    state: dict[str, object] = {}

    class _Session:
        def get(self, key, default=None):  # noqa: ANN001
            return state.get(key, default)

        def __setattr__(self, key, value) -> None:  # noqa: ANN001
            state[key] = value

        def __getattr__(self, key):  # noqa: ANN001
            try:
                return state[key]
            except KeyError as exc:
                raise AttributeError(key) from exc

    import archium.ui.studio.canvas_command_bridge as bridge

    monkeypatch.setattr(bridge, "st", type("S", (), {"session_state": _Session()})())

    set_studio_selection(["a", "b"])
    assert state["studio_selected_element_ids"] == ["a", "b"]
    assert state["studio_selected_element_id"] == "a"

    set_studio_selection([])
    assert state["studio_selected_element_ids"] == []
    assert state["studio_selected_element_id"] is None


def test_studio_context_carries_warnings() -> None:
    project_id = uuid4()
    context = StudioPresentationContext(
        project=Project(name="Demo"),
        presentation=Presentation(project_id=project_id, title="Test Deck"),
        snapshot=PresentationVisualSnapshot(presentation_id=uuid4()),
        ready_for_export=False,
        slide_count=1,
        layout_ready_count=1,
        preview_ready_count=0,
        warnings=("第 1 页 RenderScene 编译失败：boom",),
    )
    assert context.warnings
    assert studio_readiness_label(context) == "has_issues"

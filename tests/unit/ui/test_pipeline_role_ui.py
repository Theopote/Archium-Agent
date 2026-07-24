"""UI helpers collapse internal Visual substages onto the product roster."""

from __future__ import annotations

from archium.domain.enums import PipelineRole
from archium.ui.pipeline_role_ui import role_button_label


def test_role_button_label_collapses_visual_substages() -> None:
    label = role_button_label(
        "归纳模板",
        PipelineRole.ARCHITECTURE,
        PipelineRole.COMPOSITION,
        PipelineRole.LAYOUT,
    )
    assert "〔visual〕" in label
    assert "architecture" not in label
    assert "composition" not in label
    assert "layout" not in label


def test_role_button_label_can_show_internal_tags() -> None:
    label = role_button_label(
        "归纳模板",
        PipelineRole.ARCHITECTURE,
        show_internal=True,
    )
    assert "〔architecture〕" in label

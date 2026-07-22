"""Product-flow stage: 工作室."""

from __future__ import annotations

from archium.ui.pages import studio
from archium.ui.pages.flow import render_stage_header, render_stage_nav


def render() -> None:
    render_stage_header("edit")
    studio.render(
        embedded=True,
        show_header=False,
        show_export=False,
        show_progress=False,
    )
    render_stage_nav("edit")

"""Product-flow stage: 编辑."""

from __future__ import annotations

from archium.ui.pages import studio
from archium.ui.pages.flow import render_stage_header, render_stage_nav


def render() -> None:
    render_stage_header("edit")
    studio.render()
    render_stage_nav("edit")

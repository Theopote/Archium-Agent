"""Product-flow stage: 工作室 (page key ``edit``).

This is the formal five-stage entry. It embeds ``pages.studio`` as the
workbench shell; do not navigate users to the legacy ``studio`` page key.
"""

from __future__ import annotations

from archium.ui.pages import studio
from archium.ui.pages.flow import render_stage_header, render_stage_nav
from archium.ui.product_flow import PRODUCT_STUDIO_PAGE_KEY


def render() -> None:
    from archium.ui.components.navigation import (
        render_workflow_progress_indicator,
        set_current_stage,
    )

    # 设置当前阶段
    set_current_stage("edit")

    # 显示五阶段进度（在 Studio 头部上方）
    render_workflow_progress_indicator("edit")

    render_stage_header(PRODUCT_STUDIO_PAGE_KEY)
    studio.render(
        embedded=True,
        show_header=False,
        show_export=False,
        show_progress=True,
    )
    render_stage_nav(PRODUCT_STUDIO_PAGE_KEY)

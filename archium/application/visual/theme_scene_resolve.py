"""Re-resolve token-referenced styles onto a RenderScene without geometry edits."""

from __future__ import annotations

import contextlib

from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode, ThemeTokens


def resolve_scene_with_design_system(
    scene: RenderScene,
    design_system: DesignSystem,
) -> RenderScene:
    """Return a resolved copy: token refs → concrete colors/fonts from DesignSystem.

    Nodes with empty ``color_token`` keep their explicit ``color`` (local override).
    Geometry and asset URIs are unchanged.
    """
    resolved = scene.model_copy(deep=True)
    resolved.design_system_id = design_system.id
    resolved.background = BackgroundStyle(
        color=design_system.colors.resolve("background"),
        image_asset_path=scene.background.image_asset_path,
    )
    resolved.theme_tokens = ThemeTokens(
        colors={
            name: design_system.colors.resolve(name)
            for name in (
                "background",
                "surface",
                "primary_text",
                "secondary_text",
                "muted_text",
                "primary",
                "secondary",
                "accent",
                "border",
            )
        },
        typography={
            name: getattr(design_system.typography, name).model_dump()
            for name in (
                "display",
                "title",
                "subtitle",
                "heading",
                "body",
                "caption",
                "metric",
                "footnote",
                "source",
            )
        },
        spacing=design_system.spacing.model_dump(),
    )

    for node in resolved.nodes:
        if not isinstance(node, TextNode):
            continue
        if node.color_token:
            with contextlib.suppress(KeyError):
                node.color = design_system.colors.resolve(node.color_token)
        if node.typography_token and hasattr(design_system.typography, node.typography_token):
            token = getattr(design_system.typography, node.typography_token)
            # Only refresh size/weight/family when still token-bound (no local pin).
            node.font_size = token.font_size
            node.font_weight = token.font_weight
            node.line_height = token.line_height
            if not node.font_family_cjk:
                node.font_family = token.font_family
    return resolved

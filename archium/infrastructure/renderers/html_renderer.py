"""HTML renderer for RenderScene — browser-preview and screenshot source."""

from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import quote

from archium.application.visual.scene_fonts import (
    DEFAULT_CJK_FONT,
    css_font_stack,
)
from archium.domain.visual.render_scene import (
    DrawingNode,
    ImageNode,
    RenderScene,
    ShapeNode,
    TextNode,
)

DEFAULT_DPI = 96


class HtmlRenderer:
    """Render a RenderScene to a self-contained HTML document."""

    def __init__(self, *, dpi: int = DEFAULT_DPI) -> None:
        self._dpi = dpi

    def render(self, scene: RenderScene) -> str:
        width_px = int(scene.page_width * self._dpi)
        height_px = int(scene.page_height * self._dpi)
        bg = html.escape(scene.background.color)
        node_html = "\n".join(self._render_node(node, scene) for node in scene.sorted_nodes())
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width={width_px}, height={height_px}"/>
<title>RenderScene</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #e8e8e8; display: flex; justify-content: center; padding: 16px; }}
  .slide {{
    position: relative;
    width: {width_px}px;
    height: {height_px}px;
    background: {bg};
    overflow: hidden;
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", Arial, sans-serif;
  }}
  .node {{ position: absolute; overflow: hidden; }}
  .text-node {{
    white-space: pre-wrap;
    word-wrap: break-word;
  }}
  .image-node img {{
    width: 100%;
    height: 100%;
    display: block;
  }}
  .image-contain img {{ object-fit: contain; }}
  .image-cover img {{ object-fit: cover; }}
  .shape-card {{ border-radius: 4px; }}
</style>
</head>
<body>
<div class="slide" data-scene-id="{html.escape(str(scene.id))}">
{node_html}
</div>
</body>
</html>
"""

    def render_to_file(self, scene: RenderScene, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render(scene), encoding="utf-8")
        return output_path

    def _render_node(self, node: object, scene: RenderScene) -> str:
        if isinstance(node, TextNode):
            return self._render_text(node)
        if isinstance(node, ImageNode):
            return self._render_image(node)
        if isinstance(node, DrawingNode):
            return self._render_drawing(node)
        if isinstance(node, ShapeNode):
            return self._render_shape(node)
        return ""

    def _px(self, inches: float) -> int:
        return max(0, int(round(inches * self._dpi)))

    def _box_style(self, node: TextNode | ImageNode | DrawingNode | ShapeNode) -> str:
        return (
            f"left:{self._px(node.x)}px;"
            f"top:{self._px(node.y)}px;"
            f"width:{self._px(node.width)}px;"
            f"height:{self._px(node.height)}px;"
            f"z-index:{node.z_index};"
            f"opacity:{node.opacity};"
        )

    def _render_text(self, node: TextNode) -> str:
        size_px = max(1, int(round(node.font_size * self._dpi / 72)))
        line_px = max(1, int(round(node.line_height * self._dpi / 72)))
        align = html.escape(node.alignment)
        color = html.escape(node.color)
        weight = node.font_weight
        stack = css_font_stack(
            primary=node.font_family,
            cjk=node.font_family_cjk or DEFAULT_CJK_FONT,
            latin=node.font_family_latin or node.font_family,
        )
        family = html.escape(stack)
        text = html.escape(node.text)
        pad = node.padding
        padding = (
            f"padding:{self._px(pad.top)}px {self._px(pad.right)}px "
            f"{self._px(pad.bottom)}px {self._px(pad.left)}px;"
        )
        return (
            f'<div class="node text-node" id="{html.escape(node.id)}" '
            f'style="{self._box_style(node)}{padding}'
            f"font-family:{family};font-size:{size_px}px;"
            f"font-weight:{weight};line-height:{line_px}px;color:{color};"
            f'text-align:{align};">{text}</div>'
        )

    def _render_image(self, node: ImageNode) -> str:
        fit_class = "image-contain" if node.fit_mode == "contain" else "image-cover"
        if node.asset_unresolved or not node.asset_path:
            return (
                f'<div class="node" id="{html.escape(node.id)}" '
                f'style="{self._box_style(node)}background:#dde3ea;border:1px dashed #889;">'
                f'<span style="font-size:11px;color:#666;padding:4px;">missing asset</span></div>'
            )
        src = self._file_uri(node.asset_path)
        return (
            f'<div class="node image-node {fit_class}" id="{html.escape(node.id)}" '
            f'style="{self._box_style(node)}">'
            f'<img src="{src}" alt="{html.escape(node.semantic_role)}"/></div>'
        )

    def _render_drawing(self, node: DrawingNode) -> str:
        if node.asset_unresolved or not node.asset_path:
            return (
                f'<div class="node" id="{html.escape(node.id)}" '
                f'style="{self._box_style(node)}background:#eef2f6;border:2px solid #456;">'
                f'<span style="font-size:11px;color:#345;padding:4px;">drawing missing</span></div>'
            )
        src = self._file_uri(node.asset_path)
        return (
            f'<div class="node image-node image-contain" id="{html.escape(node.id)}" '
            f'style="{self._box_style(node)}" data-drawing-type="{html.escape(node.drawing_type)}">'
            f'<img src="{src}" alt="{html.escape(node.drawing_type)}"/></div>'
        )

    def _render_shape(self, node: ShapeNode) -> str:
        fill = html.escape(node.fill_color or "transparent")
        stroke = html.escape(node.stroke_color or "transparent")
        sw = max(0, int(round(node.stroke_width * self._dpi)))
        radius = max(0, int(round(node.corner_radius * self._dpi)))
        extra = " shape-card" if node.shape_kind == "card" else ""
        return (
            f'<div class="node{extra}" id="{html.escape(node.id)}" '
            f'style="{self._box_style(node)}background:{fill};'
            f"border:{sw}px solid {stroke};border-radius:{radius}px;\"></div>"
        )

    @staticmethod
    def _file_uri(path: str) -> str:
        resolved = Path(path).resolve()
        return resolved.as_uri() if resolved.is_file() else quote(path)

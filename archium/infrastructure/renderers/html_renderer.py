"""HTML renderer for RenderScene — browser-preview and screenshot source."""

from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import quote

from archium.domain.visual.font_names import (
    DEFAULT_CJK_FONT,
)
from archium.domain.visual.render_scene import (
    ConnectorNode,
    DrawingNode,
    FreeformNode,
    ImageNode,
    RenderScene,
    ShapeNode,
    TextNode,
    connector_path_points,
)
from archium.domain.visual.scene_fonts import (
    css_font_stack,
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
        if isinstance(node, ConnectorNode):
            return self._render_connector(node, scene)
        if isinstance(node, FreeformNode):
            return self._render_freeform(node)
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
        from archium.domain.visual.render_scene import effective_run_style

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
        pad = node.padding
        padding = (
            f"padding:{self._px(pad.top)}px {self._px(pad.right)}px "
            f"{self._px(pad.bottom)}px {self._px(pad.left)}px;"
        )
        if node.runs:
            spans: list[str] = []
            for run in node.runs:
                style = effective_run_style(node, run)
                run_size = max(1, int(round(float(style["font_size"]) * self._dpi / 72)))
                run_weight = int(style["font_weight"])
                run_color = html.escape(str(style["color"]))
                run_stack = css_font_stack(
                    primary=str(style["font_family"]),
                    cjk=str(style["font_family_cjk"] or DEFAULT_CJK_FONT),
                    latin=str(style["font_family_latin"] or style["font_family"]),
                )
                run_family = html.escape(run_stack)
                italic = "font-style:italic;" if style["font_style"] == "italic" else ""
                spans.append(
                    f'<span style="font-family:{run_family};font-size:{run_size}px;'
                    f'font-weight:{run_weight};color:{run_color};{italic}">'
                    f"{html.escape(run.text)}</span>"
                )
            inner = "".join(spans)
        else:
            inner = html.escape(node.text)
        return (
            f'<div class="node text-node" id="{html.escape(node.id)}" '
            f'style="{self._box_style(node)}{padding}'
            f"font-family:{family};font-size:{size_px}px;"
            f"font-weight:{weight};line-height:{line_px}px;color:{color};"
            f'text-align:{align};">{inner}</div>'
        )

    def _render_image(self, node: ImageNode) -> str:
        fit_class = "image-contain" if node.fit_mode == "contain" else "image-cover"
        asset = (node.resolved_path or node.asset_path or node.storage_uri or "").strip()
        if node.asset_unresolved or not asset:
            return (
                f'<div class="node" id="{html.escape(node.id)}" '
                f'style="{self._box_style(node)}background:#dde3ea;border:1px dashed #889;">'
                f'<span style="font-size:11px;color:#666;padding:4px;">missing asset</span></div>'
            )
        src = self._file_uri(asset)
        return (
            f'<div class="node image-node {fit_class}" id="{html.escape(node.id)}" '
            f'style="{self._box_style(node)}">'
            f'<img src="{src}" alt="{html.escape(node.semantic_role)}"/></div>'
        )

    def _render_drawing(self, node: DrawingNode) -> str:
        asset = (node.resolved_path or node.asset_path or node.storage_uri or "").strip()
        if node.asset_unresolved or not asset:
            return (
                f'<div class="node" id="{html.escape(node.id)}" '
                f'style="{self._box_style(node)}background:#eef2f6;border:2px solid #456;">'
                f'<span style="font-size:11px;color:#345;padding:4px;">drawing missing</span></div>'
            )
        src = self._file_uri(asset)
        return (
            f'<div class="node image-node image-contain" id="{html.escape(node.id)}" '
            f'style="{self._box_style(node)}" data-drawing-type="{html.escape(node.drawing_type)}">'
            f'<img src="{src}" alt="{html.escape(node.drawing_type)}"/></div>'
        )

    def _render_shape(self, node: ShapeNode) -> str:
        fill = html.escape(node.fill_color or "transparent")
        stroke = html.escape(node.stroke_color or "transparent")
        sw = max(0, int(round(node.stroke_width * self._dpi / 72)))
        radius = max(0, int(round(node.corner_radius * self._dpi)))
        if node.shape_kind == "ellipse":
            radius = max(self._px(node.width), self._px(node.height)) // 2
        if node.shape_kind == "line":
            # Approximate as a thin absolute-positioned border box rotated via SVG later;
            # keep a 2px stroke bar for preview fidelity.
            return (
                f'<div class="node" id="{html.escape(node.id)}" '
                f'style="{self._box_style(node)}background:{stroke};'
                f'height:{max(1, sw)}px;"></div>'
            )
        extra = " shape-card" if node.shape_kind == "card" else ""
        return (
            f'<div class="node{extra}" id="{html.escape(node.id)}" '
            f'style="{self._box_style(node)}background:{fill};'
            f"border:{sw}px solid {stroke};border-radius:{radius}px;\"></div>"
        )

    def _render_connector(self, node: ConnectorNode, scene: RenderScene) -> str:
        points = connector_path_points(scene, node)
        if len(points) < 2:
            points = [
                (node.x, node.y),
                (node.x + node.width, node.y + node.height),
            ]
        color = html.escape(node.stroke_color)
        width = max(1.0, node.stroke_width)
        path_d = " ".join(
            f"{'M' if i == 0 else 'L'}{self._px(x)},{self._px(y)}"
            for i, (x, y) in enumerate(points)
        )
        marker = (
            f'<marker id="arrow-{html.escape(node.id)}" markerWidth="8" markerHeight="8" '
            f'refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="{color}"/></marker>'
            if node.arrow_end
            else ""
        )
        end_attr = (
            f' marker-end="url(#arrow-{html.escape(node.id)})"' if node.arrow_end else ""
        )
        label_html = ""
        if node.label.strip():
            mid = points[len(points) // 2]
            label_html = (
                f'<div style="position:absolute;left:{self._px(mid[0])}px;'
                f'top:{self._px(mid[1]) - 14}px;font-size:10px;color:{color};">'
                f"{html.escape(node.label.strip())}</div>"
            )
        return (
            f'<div class="node" id="{html.escape(node.id)}" '
            f'style="left:0;top:0;width:100%;height:100%;z-index:{node.z_index};'
            f'opacity:{node.opacity};pointer-events:none;">'
            f'<svg width="100%" height="100%" style="position:absolute;inset:0;overflow:visible;">'
            f"<defs>{marker}</defs>"
            f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="{width}"{end_attr}/>'
            f"</svg>{label_html}</div>"
        )

    def _render_freeform(self, node: FreeformNode) -> str:
        if len(node.points) < 2:
            return ""
        color = html.escape(node.stroke_color or "#333333")
        fill = html.escape(node.fill_color) if node.fill_color else "none"
        width = max(1.0, node.stroke_width)
        coords = " ".join(f"{self._px(p.x)},{self._px(p.y)}" for p in node.points)
        tag = "polygon" if node.closed and len(node.points) >= 3 else "polyline"
        return (
            f'<div class="node" id="{html.escape(node.id)}" '
            f'style="left:0;top:0;width:100%;height:100%;z-index:{node.z_index};'
            f'opacity:{node.opacity};pointer-events:none;">'
            f'<svg width="100%" height="100%" style="position:absolute;inset:0;overflow:visible;">'
            f'<{tag} points="{coords}" fill="{fill}" stroke="{color}" '
            f'stroke-width="{width}"/></svg></div>'
        )

    @staticmethod
    def _file_uri(path: str) -> str:
        resolved = Path(path).resolve()
        return resolved.as_uri() if resolved.is_file() else quote(path)

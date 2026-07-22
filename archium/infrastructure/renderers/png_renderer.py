"""PIL-based PNG renderer for RenderScene — deterministic scene preview."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

from archium.application.visual.scene_fonts import (
    CJK_FALLBACK_CHAIN,
    LATIN_FALLBACK_CHAIN,
    text_has_cjk,
)
from archium.domain.visual.render_scene import (
    DrawingNode,
    ImageNode,
    RenderScene,
    ShapeNode,
    TextNode,
)
from archium.infrastructure.layout.font_resolver import load_truetype_font

DEFAULT_DPI = 96


class PngRenderer:
    """Rasterize a RenderScene to PNG using Pillow (no browser required)."""

    def __init__(self, *, dpi: int = DEFAULT_DPI) -> None:
        self._dpi = dpi
        self._font_cache: dict[tuple[str, int, int, str, str], object] = {}

    def render(self, scene: RenderScene, output_path: Path) -> Path:
        from PIL import Image, ImageDraw

        width = max(1, int(scene.page_width * self._dpi))
        height = max(1, int(scene.page_height * self._dpi))
        bg = self._parse_color(scene.background.color)
        image = Image.new("RGB", (width, height), color=bg)
        draw = ImageDraw.Draw(image)

        for node in scene.sorted_nodes():
            if not node.visible:
                continue
            if isinstance(node, ShapeNode):
                self._draw_shape(draw, node)
            elif isinstance(node, DrawingNode):
                self._paste_image(image, node, fit="contain")
            elif isinstance(node, ImageNode):
                self._paste_image(image, node, fit=node.fit_mode)
            elif isinstance(node, TextNode):
                self._draw_text(draw, node)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG")
        return output_path

    def _px(self, inches: float) -> int:
        return max(0, int(round(inches * self._dpi)))

    def _box(self, node: TextNode | ImageNode | DrawingNode | ShapeNode) -> tuple[int, int, int, int]:
        x0 = self._px(node.x)
        y0 = self._px(node.y)
        x1 = self._px(node.x + node.width)
        y1 = self._px(node.y + node.height)
        return x0, y0, max(x0 + 1, x1), max(y0 + 1, y1)

    def _parse_color(self, value: str) -> tuple[int, int, int]:
        cleaned = value.strip().lstrip("#")
        if len(cleaned) == 6:
            return (
                int(cleaned[0:2], 16),
                int(cleaned[2:4], 16),
                int(cleaned[4:6], 16),
            )
        if len(cleaned) == 8:
            return (
                int(cleaned[0:2], 16),
                int(cleaned[2:4], 16),
                int(cleaned[4:6], 16),
            )
        return (248, 248, 246)

    def _font_candidates(self, node: TextNode) -> tuple[str, ...]:
        primary = node.font_family
        cjk = node.font_family_cjk or primary
        latin = node.font_family_latin or primary
        if text_has_cjk(node.text):
            chain = (primary, cjk, *CJK_FALLBACK_CHAIN, latin, *LATIN_FALLBACK_CHAIN)
        else:
            chain = (primary, latin, *LATIN_FALLBACK_CHAIN, cjk, *CJK_FALLBACK_CHAIN)
        seen: list[str] = []
        for name in chain:
            if name and name not in seen:
                seen.append(name)
        return tuple(seen)

    def _load_font(self, node: TextNode, size_pt: float) -> object:
        from PIL import ImageFont

        px = max(8, int(round(size_pt * self._dpi / 72)))
        bold = node.font_weight >= 600
        key = (node.font_family, px, node.font_weight, node.font_family_cjk, node.text[:8])
        cached = self._font_cache.get(key)
        if cached is not None:
            return cached
        for name in self._font_candidates(node):
            loaded = load_truetype_font(name, bold=bold, size_px=px)
            if loaded is not None:
                self._font_cache[key] = loaded
                return loaded
            try:
                font: object = ImageFont.truetype(name, px)
                self._font_cache[key] = font
                return font
            except OSError:
                continue
        font = ImageFont.load_default()
        self._font_cache[key] = font
        return font

    def _draw_shape(self, draw: object, node: ShapeNode) -> None:
        box = self._box(node)
        fill = self._parse_color(node.fill_color) if node.fill_color else None
        outline = self._parse_color(node.stroke_color) if node.stroke_color else None
        width = max(0, int(round(node.stroke_width * self._dpi)))
        draw.rectangle(box, fill=fill, outline=outline, width=width or 0)  # type: ignore[attr-defined]

    def _draw_text(self, draw: object, node: TextNode) -> None:
        box = self._box(node)
        font = self._load_font(node, node.font_size)
        color = self._parse_color(node.color)
        pad_x = self._px(node.padding.left)
        pad_y = self._px(node.padding.top)
        draw.multiline_text(  # type: ignore[attr-defined]
            (box[0] + pad_x, box[1] + pad_y),
            node.text,
            fill=color,
            font=font,
            spacing=int(round(node.line_height * self._dpi / 72))
            - int(node.font_size * self._dpi / 72),
        )

    def _paste_image(
        self,
        canvas: object,
        node: ImageNode | DrawingNode,
        *,
        fit: str,
    ) -> None:
        from PIL import Image

        if node.asset_unresolved or not node.asset_path:
            return
        path = Path(node.asset_path)
        if not path.is_file():
            return
        box = self._box(node)
        target_w = box[2] - box[0]
        target_h = box[3] - box[1]
        if target_w <= 0 or target_h <= 0:
            return
        try:
            asset = self._load_image_asset(path, target_w=target_w, target_h=target_h)
        except OSError:
            if path.suffix.lower() == ".svg":
                self._draw_svg_placeholder(canvas, box)
                return
            return

        src_w, src_h = asset.size
        if fit == "contain":
            scale = min(target_w / src_w, target_h / src_h)
            new_w = max(1, int(src_w * scale))
            new_h = max(1, int(src_h * scale))
            resized = asset.resize((new_w, new_h), Image.Resampling.LANCZOS)
            offset_x = box[0] + (target_w - new_w) // 2
            offset_y = box[1] + (target_h - new_h) // 2
            canvas.paste(resized, (offset_x, offset_y), resized)  # type: ignore[attr-defined]
            return

        scale = max(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * scale))
        new_h = max(1, int(src_h * scale))
        resized = asset.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = max(0, (new_w - target_w) // 2)
        top = max(0, (new_h - target_h) // 2)
        cropped = resized.crop((left, top, left + target_w, top + target_h))
        canvas.paste(cropped, (box[0], box[1]), cropped)  # type: ignore[attr-defined]

    def _load_image_asset(self, path: Path, *, target_w: int, target_h: int):
        from PIL import Image

        if path.suffix.lower() != ".svg":
            return Image.open(path).convert("RGBA")
        try:
            return self._load_svg_via_cairosvg(path, target_w=target_w, target_h=target_h)
        except Exception:
            return self._load_svg_via_simple_parser(path, target_w=target_w, target_h=target_h)

    @staticmethod
    def _load_svg_via_cairosvg(path: Path, *, target_w: int, target_h: int):
        from PIL import Image

        try:
            import cairosvg
        except Exception as exc:  # pragma: no cover - platform/env dependent
            raise OSError("CairoSVG unavailable") from exc

        png_bytes = cairosvg.svg2png(
            url=str(path),
            output_width=max(target_w * 2, 32),
            output_height=max(target_h * 2, 32),
        )
        return Image.open(BytesIO(png_bytes)).convert("RGBA")

    @staticmethod
    def _load_svg_via_simple_parser(path: Path, *, target_w: int, target_h: int):
        from PIL import Image, ImageDraw
        from svg.path import parse_path

        scale = 2
        canvas_w = max(target_w * scale, 32)
        canvas_h = max(target_h * scale, 32)
        image = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)

        root = ET.fromstring(path.read_text(encoding="utf-8"))
        view_box = root.attrib.get("viewBox", "0 0 24 24").replace(",", " ").split()
        if len(view_box) != 4:
            raise OSError("unsupported SVG viewBox")
        vb_x, vb_y, vb_w, vb_h = (float(part) for part in view_box)
        sx = canvas_w / max(vb_w, 1.0)
        sy = canvas_h / max(vb_h, 1.0)

        def px_x(value: float) -> float:
            return (value - vb_x) * sx

        def px_y(value: float) -> float:
            return (value - vb_y) * sy

        def parse_color(value: str | None, *, default: tuple[int, int, int, int] = (26, 26, 26, 255)):
            text = (value or "").strip()
            if not text or text == "currentColor":
                return default
            if text == "none":
                return None
            cleaned = text.lstrip("#")
            if len(cleaned) == 6:
                return (
                    int(cleaned[0:2], 16),
                    int(cleaned[2:4], 16),
                    int(cleaned[4:6], 16),
                    255,
                )
            return default

        def stroke_width(elem: ET.Element) -> int:
            raw = elem.attrib.get("stroke-width", root.attrib.get("stroke-width", "1.0"))
            try:
                return max(1, int(round(float(raw) * ((sx + sy) / 2))))
            except ValueError:
                return max(1, int(round((sx + sy) / 2)))

        def inherit(elem: ET.Element, name: str, fallback: str | None = None) -> str | None:
            return elem.attrib.get(name, root.attrib.get(name, fallback))

        for elem in root.iter():
            tag = elem.tag.rsplit("}", 1)[-1]
            if tag == "svg":
                continue
            stroke = parse_color(inherit(elem, "stroke"))
            fill = parse_color(inherit(elem, "fill", "none"))
            width = stroke_width(elem)

            if tag == "circle":
                cx = float(elem.attrib["cx"])
                cy = float(elem.attrib["cy"])
                r = float(elem.attrib["r"])
                box = (px_x(cx - r), px_y(cy - r), px_x(cx + r), px_y(cy + r))
                if fill is not None:
                    draw.ellipse(box, fill=fill)
                if stroke is not None:
                    draw.ellipse(box, outline=stroke, width=width)
            elif tag == "rect":
                x = float(elem.attrib.get("x", "0"))
                y = float(elem.attrib.get("y", "0"))
                w = float(elem.attrib["width"])
                h = float(elem.attrib["height"])
                box = (px_x(x), px_y(y), px_x(x + w), px_y(y + h))
                if fill is not None:
                    draw.rounded_rectangle(box, radius=0, fill=fill)
                if stroke is not None:
                    draw.rounded_rectangle(box, radius=0, outline=stroke, width=width)
            elif tag == "line":
                x1 = px_x(float(elem.attrib["x1"]))
                y1 = px_y(float(elem.attrib["y1"]))
                x2 = px_x(float(elem.attrib["x2"]))
                y2 = px_y(float(elem.attrib["y2"]))
                if stroke is not None:
                    draw.line((x1, y1, x2, y2), fill=stroke, width=width)
            elif tag == "path":
                d = elem.attrib.get("d")
                if not d or stroke is None:
                    continue
                for segment in parse_path(d):
                    samples = max(8, min(64, int(segment.length(error=1e-2) * max(sx, sy) / 4)))
                    points: list[tuple[float, float]] = []
                    for i in range(samples + 1):
                        t = i / max(samples, 1)
                        point = segment.point(t)
                        points.append((px_x(point.real), px_y(point.imag)))
                    if len(points) >= 2:
                        draw.line(points, fill=stroke, width=width, joint="curve")
        return image

    @staticmethod
    def _draw_svg_placeholder(
        canvas: object,
        box: tuple[int, int, int, int],
    ) -> None:
        from PIL import ImageDraw

        placeholder_color = (210, 210, 210)
        draw = ImageDraw.Draw(canvas)
        draw.rectangle(box, outline=placeholder_color, width=2)
        cx = (box[0] + box[2]) // 2
        cy = (box[1] + box[3]) // 2
        draw.line((cx - 6, cy, cx + 6, cy), fill=placeholder_color, width=2)
        draw.line((cx, cy - 6, cx, cy + 6), fill=placeholder_color, width=2)

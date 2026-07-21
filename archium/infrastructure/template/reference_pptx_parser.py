"""Parse reference PPTX into ReferenceSlideSnapshot (induction IR).

Extends Template Studio extraction with richer element typing, signatures,
and portable relative image paths. Does not invent a parallel generation kernel.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Emu

from archium.domain.visual.reference_slide import (
    REFERENCE_TEMPLATE_ASSET_ORIGIN,
    ReferenceAsset,
    ReferenceElement,
    ReferenceElementType,
    ReferencePresentation,
    ReferenceSlideSnapshot,
)
from archium.application.visual.drawing_inference_service import DrawingInferenceService
from archium.infrastructure.renderers.pptx_screenshot import (
    export_pptx_slide_pngs,
    screenshot_tools_available,
)

_EMU_PER_INCH = 914400.0
_WINDOWS_ABS = re.compile(r"^[A-Za-z]:[\\/]")


def _emu_to_inches(value: int | float | None) -> float:
    if value is None:
        return 0.0
    return round(float(value) / _EMU_PER_INCH, 4)


def _rgb_to_hex(rgb: object) -> str | None:
    try:
        return f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}"  # type: ignore[index]
    except Exception:
        return None


def _slide_id(index: int) -> str:
    return f"slide_{index + 1:03d}"


def _relative_slide_image(index: int) -> str:
    return f"slides/{_slide_id(index)}.png"


def _assert_relative(path: str) -> str:
    text = (path or "").strip().replace("\\", "/")
    if not text:
        return ""
    if text.startswith(("/", "\\\\")) or _WINDOWS_ABS.match(text):
        raise ValueError(f"must not persist machine absolute path: {path}")
    return text


def _content_signature(
    *,
    layout_name: str | None,
    element_types: list[str],
    image_count: int,
    text_length: int,
    chart_count: int,
    table_count: int,
) -> str:
    payload = {
        "layout": layout_name or "",
        "types": element_types,
        "images": image_count,
        "text_len_bucket": text_length // 40,
        "charts": chart_count,
        "tables": table_count,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _visual_embedding(
    *,
    width: float,
    height: float,
    elements: list[ReferenceElement],
    image_count: int,
    text_length: int,
    chart_count: int,
    table_count: int,
) -> list[float]:
    """Deterministic structural embedding for clustering (not a neural model)."""
    area = max(width * height, 0.01)
    type_counts = Counter(e.element_type.value for e in elements)
    covered = sum(e.width * e.height for e in elements) / area
    top_heavy = sum(e.width * e.height for e in elements if e.y < height * 0.33) / area
    left_heavy = sum(e.width * e.height for e in elements if e.x < width * 0.45) / area
    max_element = max((e.width * e.height for e in elements), default=0.0) / area
    return [
        round(min(covered, 2.0), 4),
        round(min(top_heavy, 1.5), 4),
        round(min(left_heavy, 1.5), 4),
        round(min(max_element, 1.5), 4),
        round(image_count / 8.0, 4),
        round(min(text_length, 800) / 800.0, 4),
        round(chart_count / 3.0, 4),
        round(table_count / 2.0, 4),
        round(type_counts.get("text", 0) / 12.0, 4),
        round(type_counts.get("decoration", 0) / 8.0, 4),
        round(type_counts.get("drawing", 0) / 3.0, 4),
        round(len(elements) / 20.0, 4),
    ]


def _infer_element_type(
    *,
    shape_type: object,
    has_text: bool,
    text: str,
    is_picture: bool,
    width: float,
    height: float,
    page_height: float,
) -> ReferenceElementType:
    if shape_type == MSO_SHAPE_TYPE.GROUP:
        return ReferenceElementType.GROUP
    if shape_type == MSO_SHAPE_TYPE.TABLE or getattr(shape_type, "name", "") == "TABLE":
        return ReferenceElementType.TABLE
    if shape_type == MSO_SHAPE_TYPE.CHART:
        return ReferenceElementType.CHART
    if is_picture:
        # Picture shapes almost never have a text frame. Drawing vs photo is
        # decided later by DrawingInferenceService (neighbors / name / alt / title).
        return ReferenceElementType.IMAGE
    if has_text and text.strip():
        return ReferenceElementType.TEXT
    if width * height >= page_height * 0.35 * 10 * 0.5:
        return ReferenceElementType.DECORATION
    if not has_text:
        return ReferenceElementType.DECORATION
    return ReferenceElementType.SHAPE


def _picture_alt_text(shape: object) -> str:
    """Read OOXML cNvPr descr/title — the usual home for picture alt text."""
    with contextlib.suppress(Exception):
        c_nv_pr = shape._element.nvPicPr.cNvPr  # type: ignore[attr-defined]
        descr = (c_nv_pr.get("descr") or "").strip()
        if descr:
            return descr
        title = (c_nv_pr.get("title") or "").strip()
        if title:
            return title
    return ""


def _infer_semantic_role(
    *,
    element_type: ReferenceElementType,
    text: str,
    y: float,
    height: float,
    page_height: float,
    font_size_pt: float | None,
) -> str:
    lower = text.lower()
    if element_type == ReferenceElementType.IMAGE:
        return "supporting_image" if height < page_height * 0.45 else "hero_image"
    if element_type == ReferenceElementType.DRAWING:
        return "drawing"
    if element_type == ReferenceElementType.CHART:
        return "chart"
    if element_type == ReferenceElementType.TABLE:
        return "table"
    if element_type == ReferenceElementType.DECORATION:
        return "decoration"
    if y <= page_height * 0.22 and (font_size_pt or 0) >= 20:
        return "title"
    if y <= page_height * 0.35 and (font_size_pt or 0) >= 14:
        return "subtitle"
    if "来源" in text or "source" in lower:
        return "source"
    if any(token in text for token in ("% ", "㎡", "m²", "指标", "面积")):
        return "metric"
    if y >= page_height * 0.82:
        return "caption"
    return "body"


class ReferencePptxParser:
    """Parse a reference PPTX into portable ReferencePresentation snapshots."""

    def __init__(self, *, drawing_inference: DrawingInferenceService | None = None) -> None:
        self._drawing_inference = drawing_inference or DrawingInferenceService()

    def parse(
        self,
        pptx_path: Path | str,
        *,
        workspace_dir: Path,
        name: str | None = None,
        capture_screenshots: bool = True,
    ) -> ReferencePresentation:
        source = Path(pptx_path)
        workspace = Path(workspace_dir)
        workspace.mkdir(parents=True, exist_ok=True)
        slides_dir = workspace / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)

        warnings: list[str] = []
        try:
            presentation = Presentation(str(source))
        except Exception as exc:  # noqa: BLE001
            return ReferencePresentation(
                name=name or source.stem or "unreadable",
                source_filename=source.name,
                warnings=[f"无法打开 PPTX：{exc}"],
            )

        slide_width = int(presentation.slide_width or 0)
        slide_height = int(presentation.slide_height or 0)
        page_width = _emu_to_inches(slide_width) or 10.0
        page_height = _emu_to_inches(slide_height) or 5.625

        screenshot_map: dict[int, Path] = {}
        if capture_screenshots and screenshot_tools_available():
            pngs = export_pptx_slide_pngs(source, slides_dir)
            for index, png in enumerate(pngs):
                # Normalize to slide_XXX.png naming for acceptance artifacts.
                target = slides_dir / f"{_slide_id(index)}.png"
                if png.resolve() != target.resolve():
                    with contextlib.suppress(Exception):
                        if target.exists():
                            target.unlink()
                        png.replace(target)
                screenshot_map[index] = target if target.exists() else png
        elif capture_screenshots:
            warnings.append("截图工具不可用；仍输出结构 JSON，image_path 可为空。")

        slides: list[ReferenceSlideSnapshot] = []
        all_fonts: Counter[str] = Counter()
        all_colors: Counter[str] = Counter()
        # Track shape names that appear on many slides → repeated chrome.
        shape_name_pages: dict[str, set[int]] = {}

        for index, slide in enumerate(presentation.slides):
            try:
                snapshot = self._parse_slide(
                    slide,
                    index=index,
                    page_width=page_width,
                    page_height=page_height,
                    image_path=_relative_slide_image(index)
                    if index in screenshot_map
                    else "",
                    fonts_counter=all_fonts,
                    colors_counter=all_colors,
                    shape_name_pages=shape_name_pages,
                )
                slides.append(snapshot)
            except Exception as exc:  # noqa: BLE001 — page failure must not drop deck
                warnings.append(f"页面 {index + 1} 解析失败：{exc}")
                slides.append(
                    ReferenceSlideSnapshot(
                        slide_index=index,
                        slide_id=_slide_id(index),
                        width=page_width,
                        height=page_height,
                        parse_warnings=[str(exc)],
                        content_signature=f"parse_failed_{index}",
                    )
                )

        # Mark repeated chrome elements.
        repeated_names = {
            name
            for name, pages in shape_name_pages.items()
            if name and len(pages) >= max(2, len(slides) // 3)
        }
        for slide in slides:
            for element in slide.elements:
                if element.source_shape_name in repeated_names:
                    element.repeats_across_pages = True
                    if element.element_type in {
                        ReferenceElementType.SHAPE,
                        ReferenceElementType.DECORATION,
                        ReferenceElementType.TEXT,
                    } and element.semantic_role in {"", "body", "caption"}:
                        element.likely_background_or_decoration = True

        return ReferencePresentation(
            name=name or source.stem or "reference",
            source_filename=source.name,
            slide_count=len(slides),
            page_width=page_width,
            page_height=page_height,
            fonts=[n for n, _ in all_fonts.most_common(12)],
            colors=[c for c, _ in all_colors.most_common(12)],
            slides=slides,
            warnings=warnings,
            source_pptx_relative=_assert_relative("source.pptx"),
        )

    def _parse_slide(
        self,
        slide: object,
        *,
        index: int,
        page_width: float,
        page_height: float,
        image_path: str,
        fonts_counter: Counter[str],
        colors_counter: Counter[str],
        shape_name_pages: dict[str, set[int]],
    ) -> ReferenceSlideSnapshot:
        layout_name: str | None = None
        master_name: str | None = None
        with contextlib.suppress(Exception):
            layout = getattr(slide, "slide_layout", None)
            if layout is not None:
                layout_name = getattr(layout, "name", None)
                master = getattr(layout, "slide_master", None)
                if master is not None:
                    master_name = getattr(master, "name", None)

        elements: list[ReferenceElement] = []
        text_content: list[str] = []
        image_assets: list[ReferenceAsset] = []
        page_fonts: list[str] = []
        page_colors: list[str] = []
        parse_warnings: list[str] = []

        shapes = list(getattr(slide, "shapes", []))
        for z_index, shape in enumerate(shapes):
            try:
                element, asset, texts, fonts, colors = self._parse_shape(
                    shape,
                    slide_index=index,
                    z_index=z_index,
                    page_height=page_height,
                )
            except Exception as exc:  # noqa: BLE001
                parse_warnings.append(f"shape[{z_index}] failed: {exc}")
                continue
            if element is None:
                continue
            elements.append(element)
            text_content.extend(texts)
            page_fonts.extend(fonts)
            page_colors.extend(colors)
            for font in fonts:
                fonts_counter[font] += 1
            for color in colors:
                colors_counter[color] += 1
                page_colors.append(color)
            if asset is not None:
                image_assets.append(asset)
            shape_name = element.source_shape_name
            if shape_name:
                shape_name_pages.setdefault(shape_name, set()).add(index)

        # Notes (needed before drawing inference).
        notes = ""
        with contextlib.suppress(Exception):
            notes_slide = getattr(slide, "notes_slide", None)
            if notes_slide is not None and notes_slide.notes_text_frame is not None:
                notes = (notes_slide.notes_text_frame.text or "").strip()

        # Promote bare Picture shapes to DRAWING using neighborhood cues.
        self._drawing_inference.refine_slide_elements(
            elements,
            slide_notes=notes,
        )

        image_count = sum(
            1
            for e in elements
            if e.element_type
            in {ReferenceElementType.IMAGE, ReferenceElementType.DRAWING}
        )
        chart_count = sum(1 for e in elements if e.element_type == ReferenceElementType.CHART)
        table_count = sum(1 for e in elements if e.element_type == ReferenceElementType.TABLE)
        text_length = sum(len(t) for t in text_content)
        type_list = sorted(e.element_type.value for e in elements)
        signature = _content_signature(
            layout_name=layout_name,
            element_types=type_list,
            image_count=image_count,
            text_length=text_length,
            chart_count=chart_count,
            table_count=table_count,
        )
        embedding = _visual_embedding(
            width=page_width,
            height=page_height,
            elements=elements,
            image_count=image_count,
            text_length=text_length,
            chart_count=chart_count,
            table_count=table_count,
        )

        return ReferenceSlideSnapshot(
            slide_index=index,
            slide_id=_slide_id(index),
            image_path=_assert_relative(image_path),
            width=page_width,
            height=page_height,
            master_name=master_name,
            layout_name=layout_name,
            elements=elements,
            text_content=text_content,
            image_assets=image_assets,
            visual_embedding=embedding,
            content_signature=signature,
            notes=notes,
            fonts=list(dict.fromkeys(page_fonts)),
            colors=list(dict.fromkeys(page_colors)),
            parse_warnings=parse_warnings,
        )

    def _parse_shape(
        self,
        shape: object,
        *,
        slide_index: int,
        z_index: int,
        page_height: float,
    ) -> tuple[
        ReferenceElement | None,
        ReferenceAsset | None,
        list[str],
        list[str],
        list[str],
    ]:
        try:
            x = _emu_to_inches(getattr(shape, "left", 0))
            y = _emu_to_inches(getattr(shape, "top", 0))
            width = max(_emu_to_inches(getattr(shape, "width", 0)), 0.05)
            height = max(_emu_to_inches(getattr(shape, "height", 0)), 0.05)
        except Exception:
            return None, None, [], [], []

        shape_type = getattr(shape, "shape_type", None)
        is_picture = shape_type == MSO_SHAPE_TYPE.PICTURE
        has_text = bool(getattr(shape, "has_text_frame", False))
        text = ""
        font_name: str | None = None
        font_size_pt: float | None = None
        fonts: list[str] = []
        colors: list[str] = []
        texts: list[str] = []

        if has_text:
            lines: list[str] = []
            for paragraph in shape.text_frame.paragraphs:  # type: ignore[attr-defined]
                chunk = (paragraph.text or "").strip()
                if chunk:
                    lines.append(chunk)
                for run in paragraph.runs:
                    if run.font.name:
                        font_name = run.font.name
                        fonts.append(run.font.name)
                    if run.font.size is not None:
                        with contextlib.suppress(Exception):
                            font_size_pt = float(run.font.size.pt)
                    try:
                        if run.font.color is not None and run.font.color.rgb is not None:
                            hex_color = _rgb_to_hex(run.font.color.rgb)
                            if hex_color:
                                colors.append(hex_color)
                    except Exception:
                        pass
            text = "\n".join(lines)
            if text:
                texts.append(text)

        # Skip tiny marks.
        if width < 0.12 or height < 0.1:
            return None, None, texts, fonts, colors
        if not has_text and not is_picture and width * height < 0.25:
            return None, None, texts, fonts, colors

        element_type = _infer_element_type(
            shape_type=shape_type,
            has_text=bool(text),
            text=text,
            is_picture=is_picture,
            width=width,
            height=height,
            page_height=page_height,
        )
        role = _infer_semantic_role(
            element_type=element_type,
            text=text,
            y=y,
            height=height,
            page_height=page_height,
            font_size_pt=font_size_pt,
        )
        shape_name = getattr(shape, "name", "") or ""
        alt_text = _picture_alt_text(shape) if is_picture else ""
        element_id = f"s{slide_index + 1:03d}_e{z_index + 1:03d}"

        asset: ReferenceAsset | None = None
        asset_id: str | None = None
        style_notes: list[str] = []
        if is_picture:
            asset_id = f"refimg_{slide_index + 1:03d}_{z_index + 1:03d}"
            blob_hash = ""
            with contextlib.suppress(Exception):
                image = shape.image  # type: ignore[attr-defined]
                blob = getattr(image, "blob", b"") or b""
                if blob:
                    blob_hash = hashlib.sha256(blob).hexdigest()[:16]
            asset = ReferenceAsset(
                id=asset_id,
                asset_origin=REFERENCE_TEMPLATE_ASSET_ORIGIN,
                relative_path="",  # images stay inside PPTX; not extracted as project assets
                width=width,
                height=height,
                content_hash=blob_hash,
                notes="reference_template_only",
            )
            if alt_text:
                style_notes.append(f"alt:{alt_text}")

        element = ReferenceElement(
            id=element_id,
            element_type=element_type,
            x=x,
            y=y,
            width=width,
            height=height,
            z_index=z_index,
            text=text,
            font_name=font_name,
            font_size_pt=font_size_pt,
            style_notes=style_notes,
            semantic_role=role,
            likely_background_or_decoration=element_type == ReferenceElementType.DECORATION,
            asset_id=asset_id,
            source_shape_name=shape_name,
            alt_text=alt_text,
            parse_ok=True,
        )
        return element, asset, texts, fonts, colors


# Keep Emu imported for parity with structure extractor / type checkers.
_ = Emu

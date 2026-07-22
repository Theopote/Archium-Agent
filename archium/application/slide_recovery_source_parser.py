"""Parse external page sources into proxy RenderScenes for slide recovery."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from uuid import uuid4

from archium.domain.visual.render_scene import (
    BackgroundStyle,
    ImageNode,
    RenderScene,
    ShapeNode,
    TextNode,
)
from archium.exceptions import WorkflowError

_EMU_PER_INCH = 914400.0
_SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def parse_source_page(
    path: Path | str,
    *,
    slide_index: int = 0,
    workspace_dir: Path | None = None,
) -> tuple[RenderScene, str]:
    """Load a single page from PNG/JPG or PPTX into a proxy RenderScene."""
    source = Path(path)
    if not source.is_file():
        raise WorkflowError(f"源文件不存在：{source}")

    suffix = source.suffix.lower()
    if suffix in _SUPPORTED_IMAGE_SUFFIXES:
        return _parse_image_page(source, workspace_dir=workspace_dir), source.stem
    if suffix == ".pptx":
        return (
            _parse_pptx_slide(source, slide_index=slide_index, workspace_dir=workspace_dir),
            f"{source.stem}_slide_{slide_index + 1:03d}",
        )
    if suffix == ".pdf":
        raise WorkflowError("PDF 输入将在后续版本支持；请先将单页导出为 PNG 或 PPTX。")
    raise WorkflowError(f"不支持的文件类型：{suffix}")


def _parse_image_page(path: Path, *, workspace_dir: Path | None) -> RenderScene:
    page_w, page_h = _image_page_size(path)
    storage_uri = _materialize_asset(path, workspace_dir=workspace_dir, label="page_image")
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=page_w,
        page_height=page_h,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="source_page_image",
                x=0,
                y=0,
                width=page_w,
                height=page_h,
                z_index=0,
                storage_uri=storage_uri,
                semantic_role="source_page",
                asset_origin="project_upload",
                fit_mode="contain",
            ),
        ],
    )


def _parse_pptx_slide(
    path: Path,
    *,
    slide_index: int,
    workspace_dir: Path | None,
) -> RenderScene:
    try:
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE
    except ImportError as exc:  # pragma: no cover
        raise WorkflowError("需要 python-pptx 才能解析 PPTX 页面。") from exc

    presentation = Presentation(str(path))
    if slide_index < 0 or slide_index >= len(presentation.slides):
        raise WorkflowError(
            f"PPTX 只有 {len(presentation.slides)} 页，无法读取第 {slide_index + 1} 页。"
        )

    page_w = float(presentation.slide_width) / _EMU_PER_INCH
    page_h = float(presentation.slide_height) / _EMU_PER_INCH
    slide = presentation.slides[slide_index]
    nodes: list[TextNode | ImageNode | ShapeNode] = []
    z_index = 0

    for shape_index, shape in enumerate(slide.shapes):
        left = float(shape.left) / _EMU_PER_INCH
        top = float(shape.top) / _EMU_PER_INCH
        width = max(float(shape.width) / _EMU_PER_INCH, 0.05)
        height = max(float(shape.height) / _EMU_PER_INCH, 0.05)

        text = str(getattr(shape, "text", "") or "").strip()
        if text:
            nodes.append(
                TextNode(
                    id=f"text_{shape_index}",
                    x=left,
                    y=top,
                    width=width,
                    height=height,
                    z_index=z_index,
                    text=text,
                    semantic_role=_infer_text_role(text, left, top, page_w, page_h),
                    font_family="Microsoft YaHei",
                    font_size=18,
                    color="#1A1A1A",
                    line_height=24,
                )
            )
            z_index += 1
            continue

        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            storage_uri = _extract_picture_asset(
                shape,
                source_path=path,
                slide_index=slide_index,
                shape_index=shape_index,
                workspace_dir=workspace_dir,
            )
            nodes.append(
                ImageNode(
                    id=f"image_{shape_index}",
                    x=left,
                    y=top,
                    width=width,
                    height=height,
                    z_index=z_index,
                    storage_uri=storage_uri,
                    semantic_role="image",
                    asset_origin="project_upload",
                    fit_mode="contain",
                )
            )
            z_index += 1
            continue

        if shape.shape_type == MSO_SHAPE_TYPE.LINE:
            nodes.append(
                ShapeNode(
                    id=f"line_{shape_index}",
                    x=left,
                    y=top,
                    width=max(width, 0.01),
                    height=max(height, 0.01),
                    z_index=z_index,
                    shape_kind="line",
                    stroke_color="#333333",
                    stroke_width=1,
                    semantic_role="line",
                )
            )
            z_index += 1

    if not nodes:
        nodes.append(
            ImageNode(
                id="pptx_fallback",
                x=0,
                y=0,
                width=page_w,
                height=page_h,
                z_index=0,
                storage_uri=f"file://{path.resolve().as_posix()}",
                semantic_role="source_page",
                asset_origin="project_upload",
                fit_mode="contain",
            )
        )

    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=page_w,
        page_height=page_h,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=nodes,
    )


def _infer_text_role(text: str, x: float, y: float, page_w: float, page_h: float) -> str:
    if y <= page_h * 0.2 and len(text) <= 40:
        return "title"
    if y >= page_h * 0.85:
        return "caption"
    if "\t" in text or text.count(" ") >= 3 and len(text) < 30:
        return "table_cell"
    return "body"


def _image_page_size(path: Path) -> tuple[float, float]:
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        return 10.0, 5.625
    with Image.open(path) as image:
        width, height = image.size
    if width <= 0 or height <= 0:
        return 10.0, 5.625
    aspect = height / width
    page_w = 10.0
    return page_w, round(page_w * aspect, 4)


def _materialize_asset(
    path: Path,
    *,
    workspace_dir: Path | None,
    label: str,
) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    if workspace_dir is not None:
        workspace_dir.mkdir(parents=True, exist_ok=True)
        target = workspace_dir / f"{label}_{digest}{path.suffix.lower() or '.bin'}"
        if not target.is_file():
            target.write_bytes(path.read_bytes())
        return f"file://{target.resolve().as_posix()}"
    return f"file://{path.resolve().as_posix()}"


def _extract_picture_asset(
    shape: object,
    *,
    source_path: Path,
    slide_index: int,
    shape_index: int,
    workspace_dir: Path | None,
) -> str:
    image = getattr(shape, "image", None)
    blob = getattr(image, "blob", None) if image is not None else None
    if not blob:
        return f"file://{source_path.resolve().as_posix()}#slide={slide_index}&shape={shape_index}"

    ext = getattr(getattr(image, "ext", None), "lower", lambda: "png")()
    if not ext:
        ext = "png"
    if workspace_dir is None:
        workspace_dir = Path(tempfile.gettempdir()) / "archium-slide-recovery"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(blob).hexdigest()[:16]
    target = workspace_dir / f"slide_{slide_index + 1:03d}_img_{shape_index}_{digest}.{ext}"
    if not target.is_file():
        target.write_bytes(blob)
    return f"file://{target.resolve().as_posix()}"

"""Render PDF pages to PNG for slide recovery perceptual analysis."""

from __future__ import annotations

import hashlib
from pathlib import Path

from archium.exceptions import WorkflowError

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None  # type: ignore[assignment]


def pymupdf_available() -> bool:
    return fitz is not None


def render_pdf_page_png(
    pdf_path: Path | str,
    *,
    page_index: int = 0,
    workspace_dir: Path | None = None,
    zoom: float = 2.0,
) -> tuple[Path, float, float]:
    """Rasterize one PDF page to PNG; return path and page aspect ratio dimensions."""
    if fitz is None:
        raise WorkflowError("需要 pymupdf 才能解析 PDF 页面。")

    source = Path(pdf_path)
    if not source.is_file():
        raise WorkflowError(f"PDF 文件不存在：{source}")

    with fitz.open(source) as document:
        if page_index < 0 or page_index >= document.page_count:
            raise WorkflowError(
                f"PDF 只有 {document.page_count} 页，无法读取第 {page_index + 1} 页。"
            )
        page = document[page_index]
        rect = page.rect
        page_w = 10.0
        page_h = round(page_w * (rect.height / rect.width), 4) if rect.width > 0 else 5.625

        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        if workspace_dir is None:
            workspace_dir = source.parent
        workspace_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
        target = workspace_dir / f"pdf_page_{page_index + 1:03d}_{digest}.png"
        if not target.is_file():
            pixmap.save(str(target))

    return target, page_w, page_h

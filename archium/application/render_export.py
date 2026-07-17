"""Shared helpers for optional Marp binary exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from archium.infrastructure.renderers.marp_renderer import MarpPresentationRenderer


@dataclass
class MarpExportExtras:
    pptx_path: Path | None = None
    pdf_path: Path | None = None
    preview_images: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def export_marp_extras(
    marp: MarpPresentationRenderer,
    markdown_path: Path,
    *,
    export_pptx: bool = False,
    export_pdf: bool = False,
    export_preview_images: bool = False,
) -> MarpExportExtras:
    """Export optional PPTX/PDF/preview images; collect non-fatal failures as warnings."""
    extras = MarpExportExtras()

    if export_pptx:
        try:
            extras.pptx_path = marp.export_pptx(markdown_path)
        except Exception as exc:
            extras.warnings.append(f"PPTX 导出失败：{exc}")

    if export_pdf:
        try:
            extras.pdf_path = marp.export_pdf(markdown_path)
        except Exception as exc:
            extras.warnings.append(f"PDF 导出失败：{exc}")

    if export_preview_images:
        try:
            extras.preview_images = marp.export_preview_images(markdown_path)
        except Exception as exc:
            extras.warnings.append(f"预览图导出失败：{exc}")

    return extras


def export_marp_binaries(
    marp: MarpPresentationRenderer,
    markdown_path: Path,
    *,
    export_pptx: bool = False,
    export_pdf: bool = False,
) -> tuple[Path | None, Path | None, list[str]]:
    """Backward-compatible wrapper for PPTX/PDF-only export."""
    extras = export_marp_extras(
        marp,
        markdown_path,
        export_pptx=export_pptx,
        export_pdf=export_pdf,
        export_preview_images=False,
    )
    return extras.pptx_path, extras.pdf_path, extras.warnings

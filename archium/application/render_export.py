"""Shared helpers for optional Marp binary exports."""

from __future__ import annotations

from pathlib import Path

from archium.infrastructure.renderers.marp_renderer import MarpPresentationRenderer


def export_marp_binaries(
    marp: MarpPresentationRenderer,
    markdown_path: Path,
    *,
    export_pptx: bool = False,
    export_pdf: bool = False,
) -> tuple[Path | None, Path | None, list[str]]:
    """Export PPTX/PDF when requested; collect non-fatal failures as warnings."""
    warnings: list[str] = []
    pptx_path: Path | None = None
    pdf_path: Path | None = None

    if export_pptx:
        try:
            pptx_path = marp.export_pptx(markdown_path)
        except Exception as exc:
            warnings.append(f"PPTX 导出失败：{exc}")

    if export_pdf:
        try:
            pdf_path = marp.export_pdf(markdown_path)
        except Exception as exc:
            warnings.append(f"PDF 导出失败：{exc}")

    return pptx_path, pdf_path, warnings

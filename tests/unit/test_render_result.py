"""Unit tests for RenderResult and optional Marp binary exports."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from archium.application.render_export import (
    export_marp_binaries,
    export_marp_extras,
    export_pptxgen_extras,
)
from archium.domain.render import RenderResult
from archium.exceptions import RenderingError


def test_render_result_from_state_paths_supports_legacy_names() -> None:
    result = RenderResult.from_state_paths(
        json_path="/tmp/out.json",
        spec_path="/tmp/out/presentation.spec.json",
        editable_pptx_path="/tmp/out/presentation.editable.pptx",
        marp_md_path="/tmp/out/presentation.md",
        marp_pptx_path="/tmp/out/presentation.pptx",
        pdf_path="/tmp/out/presentation.pdf",
        warnings=["PPTX 导出失败：missing cli"],
    )

    assert result.json_path == Path("/tmp/out.json")
    assert result.spec_path == Path("/tmp/out/presentation.spec.json")
    assert result.editable_pptx_path == Path("/tmp/out/presentation.editable.pptx")
    assert result.markdown_path == Path("/tmp/out/presentation.md")
    assert result.marp_md_path == result.markdown_path
    assert result.pptx_path == Path("/tmp/out/presentation.pptx")
    assert result.pdf_path == Path("/tmp/out/presentation.pdf")
    assert result.warnings == ["PPTX 导出失败：missing cli"]
    assert len(result.output_paths()) == 6


def test_export_marp_binaries_collects_warnings_without_raising() -> None:
    marp = MagicMock()
    markdown_path = Path("/tmp/presentation.md")
    marp.export_pptx.side_effect = RenderingError("no marp")
    marp.export_pdf.return_value = Path("/tmp/presentation.pdf")

    pptx_path, pdf_path, warnings = export_marp_binaries(
        marp,
        markdown_path,
        export_pptx=True,
        export_pdf=True,
    )

    assert pptx_path is None
    assert pdf_path == Path("/tmp/presentation.pdf")
    assert len(warnings) == 1
    assert "PPTX" in warnings[0]
    marp.export_pptx.assert_called_once_with(markdown_path)
    marp.export_pdf.assert_called_once_with(markdown_path)


def test_export_marp_extras_generates_preview_images() -> None:
    marp = MagicMock()
    markdown_path = Path("/tmp/presentation.md")
    marp.export_preview_images.return_value = [
        Path("/tmp/previews/presentation.001.png"),
        Path("/tmp/previews/presentation.002.png"),
    ]

    extras = export_marp_extras(
        marp,
        markdown_path,
        export_preview_images=True,
    )

    assert len(extras.preview_images) == 2
    assert extras.warnings == []
    marp.export_preview_images.assert_called_once_with(markdown_path)


def test_export_marp_extras_preview_failure_becomes_warning() -> None:
    marp = MagicMock()
    marp.export_preview_images.side_effect = RenderingError("no marp")

    extras = export_marp_extras(
        marp,
        Path("/tmp/presentation.md"),
        export_preview_images=True,
    )

    assert extras.preview_images == []
    assert len(extras.warnings) == 1
    assert "预览图" in extras.warnings[0]


def test_export_marp_binaries_skips_when_not_requested() -> None:
    marp = MagicMock()
    pptx_path, pdf_path, warnings = export_marp_binaries(
        marp,
        Path("/tmp/presentation.md"),
        export_pptx=False,
        export_pdf=False,
    )
    assert pptx_path is None
    assert pdf_path is None
    assert warnings == []
    marp.export_pptx.assert_not_called()
    marp.export_pdf.assert_not_called()


def test_export_pptxgen_extras_collects_warnings_without_raising() -> None:
    from archium.exceptions import RenderingError

    renderer = MagicMock()
    spec_path = Path("/tmp/presentation.spec.json")
    renderer.export_pptx.side_effect = RenderingError("no node")

    extras = export_pptxgen_extras(renderer, spec_path, export_editable_pptx=True)

    assert extras.editable_pptx_path is None
    assert len(extras.warnings) == 1
    assert "可编辑 PPTX" in extras.warnings[0]
    renderer.export_pptx.assert_called_once_with(spec_path)


def test_export_pptxgen_extras_skips_when_not_requested() -> None:
    renderer = MagicMock()
    extras = export_pptxgen_extras(renderer, Path("/tmp/presentation.spec.json"))
    assert extras.editable_pptx_path is None
    assert extras.warnings == []
    renderer.export_pptx.assert_not_called()

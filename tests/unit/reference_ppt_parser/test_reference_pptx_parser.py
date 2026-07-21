"""Unit tests for ReferencePptxParser."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.asset_path_resolver import is_machine_absolute_path
from archium.domain.visual.reference_slide import REFERENCE_TEMPLATE_ASSET_ORIGIN
from archium.infrastructure.template.reference_pptx_parser import ReferencePptxParser
from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


def test_parser_slide_count_matches_pptx(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    workspace = tmp_path / "ws"
    presentation = ReferencePptxParser().parse(
        pptx, workspace_dir=workspace, capture_screenshots=False
    )
    assert presentation.slide_count == len(presentation.slides)
    # +1 anomalous page appended by helper when pages>=12
    assert presentation.slide_count >= 16


def test_parser_elements_and_relative_paths(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    workspace = tmp_path / "ws"
    presentation = ReferencePptxParser().parse(
        pptx, workspace_dir=workspace, capture_screenshots=False
    )
    assert presentation.slides
    first = presentation.slides[0]
    assert first.elements
    assert first.content_signature
    assert first.visual_embedding
    for slide in presentation.slides:
        assert not is_machine_absolute_path(slide.image_path)
        for asset in slide.image_assets:
            assert asset.asset_origin == REFERENCE_TEMPLATE_ASSET_ORIGIN
            assert not is_machine_absolute_path(asset.relative_path)


def test_parser_page_failure_does_not_drop_deck(tmp_path: Path, monkeypatch) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=8)
    workspace = tmp_path / "ws"
    parser = ReferencePptxParser()
    original = parser._parse_slide
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return original(*args, **kwargs)

    monkeypatch.setattr(parser, "_parse_slide", flaky)
    presentation = parser.parse(pptx, workspace_dir=workspace, capture_screenshots=False)
    assert len(presentation.slides) >= 8
    assert any(s.parse_warnings for s in presentation.slides)
    assert any("解析失败" in w or "boom" in w for w in presentation.warnings) or any(
        s.parse_warnings for s in presentation.slides
    )

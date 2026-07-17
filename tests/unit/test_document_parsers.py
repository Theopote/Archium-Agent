"""Tests for document parsers."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.infrastructure.document_parsers.docx_parser import DocxParser
from archium.infrastructure.document_parsers.image_parser import ImageParser
from archium.infrastructure.document_parsers.pdf_parser import PdfParser
from archium.infrastructure.document_parsers.pptx_parser import PptxParser
from archium.infrastructure.document_parsers.xlsx_parser import XlsxParser

from tests.fixtures.sample_files import (
    create_sample_docx,
    create_sample_image,
    create_sample_pdf,
    create_sample_xlsx,
)


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    return create_sample_pdf(tmp_path / "sample.pdf")


@pytest.fixture
def sample_docx(tmp_path: Path) -> Path:
    return create_sample_docx(tmp_path / "sample.docx")


@pytest.fixture
def sample_xlsx(tmp_path: Path) -> Path:
    return create_sample_xlsx(tmp_path / "sample.xlsx")


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    return create_sample_image(tmp_path / "site.jpg")


def test_pdf_parser_extracts_text(sample_pdf: Path) -> None:
    parsed = PdfParser().parse(sample_pdf)
    assert parsed.pages
    assert "traffic" in parsed.text.lower()


def test_docx_parser_extracts_heading_and_body(sample_docx: Path) -> None:
    parsed = DocxParser().parse(sample_docx)
    assert any("现状分析" in page.text or page.section_title == "现状分析" for page in parsed.pages)
    assert "项目背景" in parsed.text


def test_xlsx_parser_extracts_sheet_rows(sample_xlsx: Path) -> None:
    parsed = XlsxParser().parse(sample_xlsx)
    assert parsed.pages
    assert "用地面积" in parsed.text


def test_image_parser_extracts_metadata(sample_image: Path) -> None:
    parsed = ImageParser().parse(sample_image)
    assert parsed.pages[0].page_number == 1
    assert parsed.assets
    assert parsed.metadata["width"] == 800


def test_pptx_parser_supports_pptx_suffix(tmp_path: Path) -> None:
    parser = PptxParser()
    assert parser.supports(tmp_path / "report.pptx")
    assert not parser.supports(tmp_path / "report.pdf")

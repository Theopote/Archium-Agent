"""Shared parser utilities."""

from __future__ import annotations

import re
from pathlib import Path

from archium.domain.enums import DocumentType
from archium.exceptions import DocumentParseError
from archium.infrastructure.document_parsers.base import ParsedDocument, ParsedPage

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
_DOCX_SUFFIXES = {".docx"}
_PPTX_SUFFIXES = {".pptx"}
_XLSX_SUFFIXES = {".xlsx", ".xlsm"}
_PDF_SUFFIXES = {".pdf"}


def suffix_of(path: Path) -> str:
    return path.suffix.lower()


def infer_document_type(path: Path) -> DocumentType:
    suffix = suffix_of(path)
    if suffix in _PDF_SUFFIXES:
        return DocumentType.PDF
    if suffix in _DOCX_SUFFIXES:
        return DocumentType.DOCX
    if suffix in _PPTX_SUFFIXES:
        return DocumentType.PPTX
    if suffix in _XLSX_SUFFIXES:
        return DocumentType.XLSX
    if suffix in _IMAGE_SUFFIXES:
        return DocumentType.IMAGE
    return DocumentType.OTHER


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_parsed_document(
    pages: list[ParsedPage],
    *,
    metadata: dict[str, object] | None = None,
    needs_ocr: bool = False,
) -> ParsedDocument:
    joined = normalize_whitespace("\n\n".join(page.text for page in pages if page.text.strip()))
    return ParsedDocument(
        text=joined,
        pages=pages,
        metadata=metadata or {},
        needs_ocr=needs_ocr,
    )


def safe_parse(label: str, path: Path, parser_fn: object) -> ParsedDocument:
    """Run a parser function and wrap unexpected errors."""
    try:
        result = parser_fn(path)  # type: ignore[operator]
        if not isinstance(result, ParsedDocument):
            raise DocumentParseError(f"{label} parser returned invalid result for {path.name}")
        return result
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError(f"Failed to parse {path.name} with {label} parser: {exc}") from exc

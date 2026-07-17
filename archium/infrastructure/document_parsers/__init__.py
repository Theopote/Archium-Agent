"""Document parser protocol and registry."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from archium.infrastructure.document_parsers.base import ParsedDocument


class DocumentParser(Protocol):
    """Parse a supported file into a normalized document structure."""

    def supports(self, file_path: Path) -> bool:
        """Return True when this parser handles the given file."""
        ...

    def parse(self, file_path: Path) -> ParsedDocument:
        """Parse the file. Must not raise for single-page failures."""
        ...


def get_parser_for_path(file_path: Path, parsers: list[DocumentParser] | None = None) -> DocumentParser:
    """Return the first parser that supports the file path."""
    available = parsers if parsers is not None else default_parsers()
    for parser in available:
        if parser.supports(file_path):
            return parser
    raise ValueError(f"No parser available for file: {file_path.name}")


def default_parsers() -> list[DocumentParser]:
    """Return all built-in document parsers."""
    from archium.infrastructure.document_parsers.docx_parser import DocxParser
    from archium.infrastructure.document_parsers.image_parser import ImageParser
    from archium.infrastructure.document_parsers.pdf_parser import PdfParser
    from archium.infrastructure.document_parsers.pptx_parser import PptxParser
    from archium.infrastructure.document_parsers.xlsx_parser import XlsxParser

    return [PdfParser(), DocxParser(), PptxParser(), XlsxParser(), ImageParser()]

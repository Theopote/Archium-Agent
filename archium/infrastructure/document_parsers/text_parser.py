"""Plain-text and Markdown brief parser."""

from __future__ import annotations

from pathlib import Path

from archium.infrastructure.document_parsers._utils import (
    build_parsed_document,
    normalize_whitespace,
    suffix_of,
)
from archium.infrastructure.document_parsers.base import ParsedDocument, ParsedPage

_TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".text"}


class TextParser:
    """Parse UTF-8 (or fallback) plain-text / Markdown project briefs."""

    def supports(self, file_path: Path) -> bool:
        return suffix_of(file_path) in _TEXT_SUFFIXES

    def parse(self, file_path: Path) -> ParsedDocument:
        raw = file_path.read_bytes()
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", errors="replace")

        text = normalize_whitespace(text)
        section_title = file_path.stem
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if first_line.startswith("#"):
            section_title = first_line.lstrip("#").strip() or section_title

        page = ParsedPage(
            page_number=1,
            text=text or f"(empty text file: {file_path.name})",
            section_title=section_title,
            content_type="text",
        )
        return build_parsed_document(
            [page],
            metadata={
                "format": suffix_of(file_path).lstrip(".") or "txt",
                "source_filename": file_path.name,
            },
        )

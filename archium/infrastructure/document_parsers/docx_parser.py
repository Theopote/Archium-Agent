"""DOCX document parser."""

from __future__ import annotations

from pathlib import Path

from docx import Document as DocumentFactory
from docx.document import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph

from archium.domain.enums import AssetType
from archium.infrastructure.document_parsers._utils import (
    _DOCX_SUFFIXES,
    build_parsed_document,
    normalize_whitespace,
    suffix_of,
)
from archium.infrastructure.document_parsers.base import ExtractedAsset, ParsedDocument, ParsedPage


class DocxParser:
    """Extract headings, paragraphs, tables, and images from DOCX files."""

    def supports(self, file_path: Path) -> bool:
        return suffix_of(file_path) in _DOCX_SUFFIXES

    def parse(self, file_path: Path) -> ParsedDocument:
        document = DocumentFactory(str(file_path))
        pages: list[ParsedPage] = []
        assets: list[ExtractedAsset] = []
        current_title: str | None = None
        chunk_index = 0

        for block in self._iter_block_items(document):
            if isinstance(block, Paragraph):
                text = normalize_whitespace(block.text)
                if not text:
                    continue
                style_name = block.style.name if block.style is not None else ""
                if style_name.lower().startswith("heading"):
                    current_title = text
                pages.append(
                    ParsedPage(
                        page_number=None,
                        text=text,
                        section_title=current_title,
                        content_type="paragraph",
                    )
                )
                chunk_index += 1
            elif isinstance(block, Table):
                table_text = self._table_to_text(block)
                if table_text:
                    pages.append(
                        ParsedPage(
                            page_number=None,
                            text=table_text,
                            section_title=current_title,
                            content_type="table",
                        )
                    )
                    chunk_index += 1

        for rel_index, rel in enumerate(document.part.rels.values(), start=1):
            if "image" not in rel.reltype:
                continue
            try:
                image_part = rel.target_part
                assets.append(
                    ExtractedAsset(
                        filename=f"image_{rel_index}.{image_part.content_type.split('/')[-1]}",
                        data=image_part.blob,
                        asset_type=AssetType.IMAGE,
                        description="Embedded DOCX image",
                    )
                )
            except Exception:
                continue

        metadata: dict[str, object] = {
            "paragraph_count": sum(1 for page in pages if page.content_type == "paragraph"),
            "table_count": sum(1 for page in pages if page.content_type == "table"),
        }
        return build_parsed_document(pages, metadata=metadata).model_copy(update={"assets": assets})

    def _iter_block_items(self, document: DocxDocument) -> list[Paragraph | Table]:
        items: list[Paragraph | Table] = []
        for element in document.element.body:
            tag = element.tag.split("}")[-1]
            if tag == "p":
                items.append(Paragraph(element, document))
            elif tag == "tbl":
                items.append(Table(element, document))
        return items

    def _table_to_text(self, table: Table, *, max_rows: int = 50) -> str:
        lines: list[str] = []
        for row_index, row in enumerate(table.rows):
            if row_index >= max_rows:
                lines.append("[table truncated]")
                break
            cells = [normalize_whitespace(cell.text) for cell in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))
        return normalize_whitespace("\n".join(lines))

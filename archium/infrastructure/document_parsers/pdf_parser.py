"""PDF document parser using PyMuPDF."""

from __future__ import annotations

from pathlib import Path

import fitz

from archium.domain.enums import AssetType
from archium.infrastructure.document_parsers._utils import (
    _PDF_SUFFIXES,
    build_parsed_document,
    normalize_whitespace,
    suffix_of,
)
from archium.infrastructure.document_parsers.base import ExtractedAsset, ParsedDocument, ParsedPage


class PdfParser:
    """Extract page-level text and embedded images from PDF files."""

    def supports(self, file_path: Path) -> bool:
        return suffix_of(file_path) in _PDF_SUFFIXES

    def parse(self, file_path: Path) -> ParsedDocument:
        pages: list[ParsedPage] = []
        assets: list[ExtractedAsset] = []
        needs_ocr = False
        metadata: dict[str, object] = {}

        with fitz.open(file_path) as document:
            metadata["page_count"] = document.page_count
            metadata["title"] = document.metadata.get("title") or ""
            metadata["author"] = document.metadata.get("author") or ""

            for index, page in enumerate(document, start=1):
                try:
                    text = normalize_whitespace(page.get_text("text"))
                except Exception:
                    text = ""

                if len(text) < 20:
                    needs_ocr = True

                pages.append(
                    ParsedPage(
                        page_number=index,
                        text=text or f"[Page {index} contains no extractable text]",
                        content_type="text",
                    )
                )

                for image_index, image in enumerate(page.get_images(full=True), start=1):
                    try:
                        extracted = document.extract_image(image[0])
                        image_bytes = extracted.get("image")
                        if not image_bytes:
                            continue
                        extension = extracted.get("ext", "png")
                        assets.append(
                            ExtractedAsset(
                                filename=f"page{index}_img{image_index}.{extension}",
                                data=image_bytes,
                                page_number=index,
                                asset_type=AssetType.IMAGE,
                                description=f"Embedded image from page {index}",
                            )
                        )
                    except Exception:
                        continue

        result = build_parsed_document(pages, metadata=metadata, needs_ocr=needs_ocr)
        return result.model_copy(update={"assets": assets})

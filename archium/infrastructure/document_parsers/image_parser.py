"""Image metadata parser."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from archium.domain.enums import AssetType
from archium.infrastructure.document_parsers._utils import (
    _IMAGE_SUFFIXES,
    build_parsed_document,
    suffix_of,
)
from archium.infrastructure.document_parsers.base import ExtractedAsset, ParsedDocument, ParsedPage


class ImageParser:
    """Extract image metadata and register the image as an asset."""

    def supports(self, file_path: Path) -> bool:
        return suffix_of(file_path) in _IMAGE_SUFFIXES

    def parse(self, file_path: Path) -> ParsedDocument:
        with Image.open(file_path) as image:
            width, height = image.size
            metadata: dict[str, object] = {
                "format": image.format or suffix_of(file_path).lstrip("."),
                "mode": image.mode,
                "width": width,
                "height": height,
            }

        image_bytes = file_path.read_bytes()
        asset = ExtractedAsset(
            filename=file_path.name,
            data=image_bytes,
            width=width,
            height=height,
            asset_type=AssetType.PHOTO,
            description=f"Image file {file_path.name}",
        )
        page = ParsedPage(
            page_number=1,
            text=f"Image: {file_path.name} ({width}x{height})",
            section_title=file_path.stem,
            content_type="image",
        )
        return build_parsed_document([page], metadata=metadata).model_copy(update={"assets": [asset]})

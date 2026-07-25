"""CAD / BIM metadata parser — registers assets without full geometry parse."""

from __future__ import annotations

from pathlib import Path

from archium.application.cad_bim_analysis import analyze_cad_bim_file, is_cad_bim_path
from archium.infrastructure.document_parsers._utils import (
    build_parsed_document,
    safe_parse,
)
from archium.infrastructure.document_parsers.base import ParsedDocument, ParsedPage


class CadBimParser:
    """Metadata-only parser for DWG / DXF / IFC / RVT."""

    def supports(self, file_path: Path) -> bool:
        return is_cad_bim_path(file_path)

    def parse(self, file_path: Path) -> ParsedDocument:
        return safe_parse("cad_bim", file_path, self._parse)

    def _parse(self, file_path: Path) -> ParsedDocument:
        analysis = analyze_cad_bim_file(file_path)
        page = ParsedPage(
            page_number=1,
            text=analysis.summary_text(),
            section_title=file_path.stem,
            content_type="cad_bim",
        )
        return build_parsed_document([page], metadata=analysis.as_metadata())

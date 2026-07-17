"""Recursive semantic text chunking for imported documents."""

from __future__ import annotations

from dataclasses import dataclass, field

from archium.config.settings import Settings
from archium.infrastructure.document_parsers._utils import normalize_whitespace
from archium.infrastructure.document_parsers.base import ParsedPage

_BREAK_SEPARATORS = (
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    ".",
    "!",
    "?",
    "；",
    ";",
    "，",
    ",",
    " ",
)


@dataclass(frozen=True)
class SemanticChunkPart:
    """Intermediate chunk produced before persistence."""

    content: str
    page_number: int | None
    section_title: str | None
    content_type: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _PageSegment:
    text: str
    page_number: int | None
    section_title: str | None
    content_type: str


class SemanticChunker:
    """Split parsed pages into retrieval-friendly semantic chunks."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def chunk_pages(
        self,
        pages: list[ParsedPage],
        *,
        extra_metadata: dict[str, object] | None = None,
    ) -> list[SemanticChunkPart]:
        if not pages:
            return []

        base_metadata = dict(extra_metadata or {})
        segments = self._merge_pages(pages)
        parts: list[SemanticChunkPart] = []

        for segment_index, segment in enumerate(segments):
            split_texts = split_text(
                segment.text,
                chunk_size=self._settings.chunk_max_chars,
                chunk_overlap=self._settings.chunk_overlap_chars,
            )
            for part_index, content in enumerate(split_texts):
                parts.append(
                    SemanticChunkPart(
                        content=content,
                        page_number=segment.page_number,
                        section_title=segment.section_title,
                        content_type=segment.content_type,
                        metadata={
                            **base_metadata,
                            "chunk_strategy": "semantic",
                            "segment_index": segment_index,
                            "part_index": part_index,
                        },
                    )
                )
        return parts

    def _merge_pages(self, pages: list[ParsedPage]) -> list[_PageSegment]:
        merged: list[_PageSegment] = []
        buffer: list[str] = []
        current: _PageSegment | None = None

        for page in pages:
            text = normalize_whitespace(page.text)
            if not text:
                continue

            segment = _PageSegment(
                text=text,
                page_number=page.page_number,
                section_title=page.section_title,
                content_type=page.content_type,
            )

            if current is None:
                current = segment
                buffer = [text]
                continue

            same_section = current.section_title == segment.section_title
            combined_len = sum(len(item) for item in buffer) + len(text) + 2
            should_merge = same_section and (
                combined_len <= self._settings.chunk_max_chars
                or len(text) < self._settings.chunk_min_chars
                or sum(len(item) for item in buffer) < self._settings.chunk_min_chars
            )

            if should_merge:
                buffer.append(text)
                current = _PageSegment(
                    text=normalize_whitespace("\n\n".join(buffer)),
                    page_number=current.page_number or segment.page_number,
                    section_title=current.section_title or segment.section_title,
                    content_type=current.content_type,
                )
                continue

            merged.append(current)
            current = segment
            buffer = [text]

        if current is not None:
            merged.append(current)
        return merged


def split_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text on semantic boundaries with optional overlap."""
    normalized = normalize_whitespace(text)
    if not normalized:
        return []
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    text_len = len(normalized)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            break_at = _find_break_point(normalized, start, end)
            if break_at <= start:
                break_at = end
        else:
            break_at = end

        piece = normalized[start:break_at].strip()
        if piece:
            chunks.append(piece)
        if break_at >= text_len:
            break
        start = max(break_at - chunk_overlap, start + 1)

    return chunks


def _find_break_point(text: str, start: int, end: int) -> int:
    window = text[start:end]
    min_pos = max(int(len(window) * 0.5), 1)

    for separator in _BREAK_SEPARATORS:
        index = window.rfind(separator)
        if index >= min_pos:
            return start + index + len(separator)
    return end

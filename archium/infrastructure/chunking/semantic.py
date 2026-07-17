"""Recursive semantic text chunking for imported documents."""

from __future__ import annotations

from dataclasses import dataclass, field

from archium.config.settings import Settings
from archium.infrastructure.chunking.embedding_breakpoints import split_by_embedding_breakpoints
from archium.infrastructure.chunking.text_splitter import split_text
from archium.infrastructure.document_parsers._utils import normalize_whitespace
from archium.infrastructure.document_parsers.base import ParsedPage
from archium.infrastructure.embeddings.base import EmbeddingProvider


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

    def __init__(
        self,
        settings: Settings,
        *,
        embedder: EmbeddingProvider | None = None,
    ) -> None:
        self._settings = settings
        self._embedder = embedder

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
            split_texts = self._split_segment(segment.text)
            strategy = self._segment_strategy(segment.text)
            for part_index, content in enumerate(split_texts):
                parts.append(
                    SemanticChunkPart(
                        content=content,
                        page_number=segment.page_number,
                        section_title=segment.section_title,
                        content_type=segment.content_type,
                        metadata={
                            **base_metadata,
                            "chunk_strategy": strategy,
                            "segment_index": segment_index,
                            "part_index": part_index,
                        },
                    )
                )
        return parts

    def _segment_strategy(self, text: str) -> str:
        if (
            self._settings.embedding_chunking_enabled
            and self._embedder is not None
            and len(text) >= self._settings.embedding_chunk_min_segment_chars
        ):
            return "embedding_semantic"
        return "semantic"

    def _split_segment(self, text: str) -> list[str]:
        chunk_size = self._settings.chunk_max_chars
        chunk_overlap = self._settings.chunk_overlap_chars
        if (
            self._settings.embedding_chunking_enabled
            and self._embedder is not None
            and len(text) >= self._settings.embedding_chunk_min_segment_chars
        ):
            return split_by_embedding_breakpoints(
                text,
                self._embedder,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                threshold=self._settings.embedding_breakpoint_threshold,
            )
        return split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

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

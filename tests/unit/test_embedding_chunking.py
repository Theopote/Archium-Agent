"""Unit tests for embedding-based chunk breakpoints."""

from __future__ import annotations

from archium.config.settings import Settings
from archium.infrastructure.chunking.embedding_breakpoints import split_by_embedding_breakpoints
from archium.infrastructure.chunking.semantic import SemanticChunker
from archium.infrastructure.document_parsers.base import ParsedPage
from archium.infrastructure.embeddings.mock import MockEmbeddingProvider


def test_embedding_breakpoints_split_different_topics() -> None:
    traffic = "老院区交通组织混乱，人车混行严重，需优化流线。"
    landscape = "景观绿化以本地乔木为主，强调四季有景与生态多样性。"
    text = traffic * 20 + landscape * 20
    chunks = split_by_embedding_breakpoints(
        text,
        MockEmbeddingProvider(),
        chunk_size=800,
        chunk_overlap=80,
        threshold=0.65,
    )
    assert len(chunks) >= 2
    joined = "".join(chunks)
    assert "交通组织" in joined
    assert "景观绿化" in joined


def test_semantic_chunker_uses_embedding_strategy_for_long_segment() -> None:
    settings = Settings(
        _env_file=None,
        database_url="sqlite:///:memory:",
        embedding_chunking_enabled=True,
        embedding_chunk_min_segment_chars=400,
        chunk_max_chars=300,
        chunk_overlap_chars=30,
    )
    traffic = "老院区交通组织混乱，人车混行严重。"
    landscape = "景观绿化以本地乔木为主，强调四季有景。"
    long_text = traffic * 15 + landscape * 15
    parts = SemanticChunker(settings, embedder=MockEmbeddingProvider()).chunk_pages(
        [ParsedPage(page_number=1, text=long_text, section_title="现状", content_type="text")]
    )
    assert len(parts) >= 2
    assert any(part.metadata.get("chunk_strategy") == "embedding_semantic" for part in parts)

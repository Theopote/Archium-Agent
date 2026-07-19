"""Tests for keyword-augmented retrieval reranking."""

from __future__ import annotations

from uuid import uuid4

from archium.application.retrieval_hybrid import rerank_retrieved_chunks
from archium.domain.document import DocumentChunk
from archium.infrastructure.vector.chroma_store import VectorSearchHit


def test_rerank_prefers_keyword_match_for_drawing_caption() -> None:
    text_chunk = DocumentChunk(
        id=uuid4(),
        project_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content="本项目强调景观绿化与生态设计。",
    )
    asset_chunk = DocumentChunk(
        id=uuid4(),
        project_id=uuid4(),
        document_id=uuid4(),
        chunk_index=1,
        content="【图纸资产 · site_plan】摘要：总平面图展示主入口与门诊楼布局。",
        content_type="asset_caption",
    )
    hits = [
        VectorSearchHit(
            chunk_id=text_chunk.id,
            document_id=text_chunk.document_id,
            content=text_chunk.content,
            score=0.9,
            page_number=1,
            section_title=None,
            chunk_index=0,
        ),
        VectorSearchHit(
            chunk_id=asset_chunk.id,
            document_id=asset_chunk.document_id,
            content=asset_chunk.content,
            score=0.4,
            page_number=2,
            section_title=None,
            chunk_index=1,
        ),
    ]
    ranked = rerank_retrieved_chunks(
        [text_chunk, asset_chunk],
        hits,
        "总平面图 主入口",
    )
    assert ranked[0].content_type == "asset_caption"

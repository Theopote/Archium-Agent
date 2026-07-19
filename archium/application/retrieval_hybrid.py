"""Keyword overlap helpers for hybrid vector + lexical retrieval."""

from __future__ import annotations

import re

from archium.domain.document import DocumentChunk
from archium.infrastructure.vector.chroma_store import VectorSearchHit

_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+")
_DRAWING_QUERY_HINTS = ("图", "平面", "总规", "剖面", "立面", "图纸", "plan", "drawing", "site")


def tokenize_query(query: str) -> list[str]:
    tokens = [token.strip().lower() for token in _TOKEN_PATTERN.findall(query.strip())]
    return [token for token in tokens if len(token) >= 2]


def keyword_overlap_score(query: str, content: str) -> float:
    tokens = tokenize_query(query)
    if not tokens:
        return 0.0
    normalized = content.lower()
    hits = sum(1 for token in tokens if token in normalized)
    return hits / len(tokens)


def rerank_retrieved_chunks(
    chunks: list[DocumentChunk],
    hits: list[VectorSearchHit],
    query: str,
    *,
    vector_weight: float = 0.75,
    keyword_weight: float = 0.25,
) -> list[DocumentChunk]:
    """Combine vector similarity with lexical overlap for architectural queries."""
    if not chunks:
        return []
    hit_scores = {hit.chunk_id: hit.score for hit in hits}
    drawing_query = any(hint in query for hint in _DRAWING_QUERY_HINTS)
    scored: list[tuple[float, DocumentChunk]] = []
    for chunk in chunks:
        vector_score = hit_scores.get(chunk.id, 0.0)
        keyword_score = keyword_overlap_score(query, chunk.content)
        if drawing_query and chunk.content_type == "asset_caption":
            keyword_score = min(1.0, keyword_score + 0.35)
        combined = (vector_weight * vector_score) + (keyword_weight * keyword_score)
        if drawing_query and chunk.content_type == "asset_caption" and keyword_score >= 0.5:
            combined += 0.15
        scored.append((combined, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored]

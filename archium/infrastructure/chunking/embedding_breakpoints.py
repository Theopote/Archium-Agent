"""Embedding-based semantic breakpoints for long text segments."""

from __future__ import annotations

import math
import re

from archium.infrastructure.chunking.text_splitter import split_text
from archium.infrastructure.document_parsers._utils import normalize_whitespace
from archium.infrastructure.embeddings.base import EmbeddingProvider

_SENTENCE_PATTERN = re.compile(r"(?<=[。！？.!?；;])\s*")


def split_by_embedding_breakpoints(
    text: str,
    embedder: EmbeddingProvider,
    *,
    chunk_size: int,
    chunk_overlap: int,
    threshold: float,
) -> list[str]:
    """Split long text at embedding-detected topic boundaries."""
    normalized = normalize_whitespace(text)
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    sentences = _split_sentences(normalized)
    if len(sentences) <= 1:
        return split_text(normalized, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    embeddings = embedder.embed_documents(sentences)
    breakpoints = [0]
    for index in range(len(sentences) - 1):
        similarity = _cosine_similarity(embeddings[index], embeddings[index + 1])
        if similarity < threshold:
            breakpoints.append(index + 1)
    breakpoints.append(len(sentences))

    groups: list[str] = []
    for start, end in zip(breakpoints[:-1], breakpoints[1:], strict=False):
        groups.append("".join(sentences[start:end]).strip())

    chunks: list[str] = []
    for group in groups:
        if not group:
            continue
        if len(group) <= chunk_size:
            chunks.append(group)
        else:
            chunks.extend(split_text(group, chunk_size=chunk_size, chunk_overlap=chunk_overlap))
    return chunks


def _split_sentences(text: str) -> list[str]:
    parts = [part.strip() for part in _SENTENCE_PATTERN.split(text) if part.strip()]
    if parts:
        return parts
    return [text]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)

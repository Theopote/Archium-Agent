"""Offline lexical embeddings for small curated packs (e.g. architectural icons).

Not a neural model — character/token hashing with CJK support. Used so icon
matching never depends on MockEmbeddingProvider or per-request API calls.
Icon vectors are precomputed into ``embeddings.json``; queries are embedded
once per match.
"""

from __future__ import annotations

import math
import re

_VECTOR_DIM = 256
_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    normalized = text.casefold().strip()
    tokens = _TOKEN_PATTERN.findall(normalized)
    cjk_chars = [char for char in normalized if "\u4e00" <= char <= "\u9fff"]
    ngrams: list[str] = []
    for size in (2, 3):
        for index in range(max(0, len(normalized) - size + 1)):
            gram = normalized[index : index + size]
            if gram.strip():
                ngrams.append(gram)
    return tokens + cjk_chars + ngrams


def lexical_embed(text: str, *, dim: int = _VECTOR_DIM) -> list[float]:
    """Deterministic L2-normalized lexical vector for offline icon retrieval."""
    vector = [0.0] * dim
    for token in _tokenize(text):
        # Stable across process runs (unlike Python's salted hash()).
        bucket = sum(ord(ch) for ch in token) % dim
        vector[bucket] += 1.0 + (len(token) % 5) * 0.05
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [value / norm for value in vector]


class LocalLexicalEmbeddingProvider:
    """Lightweight offline embedding — suitable for frozen icon packs."""

    def __init__(self, *, dim: int = _VECTOR_DIM) -> None:
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [lexical_embed(text, dim=self._dim) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return lexical_embed(text, dim=self._dim)

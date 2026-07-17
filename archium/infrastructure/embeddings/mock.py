"""Deterministic mock embeddings for tests."""

from __future__ import annotations

import math
import re

_VECTOR_DIM = 128
_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+")


def _tokenize(text: str) -> list[str]:
    tokens = _TOKEN_PATTERN.findall(text.lower())
    if not tokens:
        return [text.lower()] if text else []
    if len(tokens) == 1 and len(tokens[0]) > 2:
        word = tokens[0]
        bigrams = [word[index : index + 2] for index in range(len(word) - 1)]
        return bigrams + tokens
    return tokens


def _embed_text(text: str) -> list[float]:
    vector = [0.0] * _VECTOR_DIM
    for token in _tokenize(text):
        vector[hash(token) % _VECTOR_DIM] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


class MockEmbeddingProvider:
    """Bag-of-token embeddings suitable for offline retrieval tests."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [_embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return _embed_text(text)

"""Embedding providers for vector retrieval."""

from archium.infrastructure.embeddings.base import EmbeddingProvider
from archium.infrastructure.embeddings.factory import create_embedding_provider

__all__ = ["EmbeddingProvider", "create_embedding_provider"]

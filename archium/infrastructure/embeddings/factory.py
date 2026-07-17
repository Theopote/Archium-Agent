"""Embedding provider factory."""

from __future__ import annotations

from archium.config.settings import Settings, get_settings
from archium.infrastructure.embeddings.base import EmbeddingProvider
from archium.infrastructure.embeddings.mock import MockEmbeddingProvider
from archium.infrastructure.embeddings.openai_compatible import OpenAICompatibleEmbeddingProvider


def create_embedding_provider(
    settings: Settings | None = None,
    *,
    provider: str | None = None,
) -> EmbeddingProvider | None:
    """Create an embedding provider based on settings."""
    settings = settings or get_settings()
    if not settings.retrieval_enabled:
        return None

    name = (provider or settings.embedding_provider).lower()
    if name == "mock":
        return MockEmbeddingProvider()

    if name in {"openai_compatible", "openai", "gemini"}:
        if not settings.embedding_configured:
            return None
        return OpenAICompatibleEmbeddingProvider(settings)

    raise ValueError(f"Unknown embedding provider: {name}")

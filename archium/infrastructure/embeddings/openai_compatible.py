"""OpenAI-compatible embedding provider."""

from __future__ import annotations

from openai import OpenAI

from archium.config.settings import Settings, get_settings
from archium.exceptions import ConfigurationError


class OpenAICompatibleEmbeddingProvider:
    """Embedding provider using any OpenAI-compatible embeddings API."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: OpenAI | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self._settings.embedding_configured:
                raise ConfigurationError(
                    "未配置 Embedding API Key。请在 .env 中设置 GEMINI_API_KEY 或 LLM_API_KEY。"
                )
            self._client = OpenAI(
                api_key=self._settings.llm_api_key,
                base_url=self._settings.llm_base_url,
                timeout=self._settings.llm_timeout_seconds,
                max_retries=0,
            )
        return self._client

    @property
    def model(self) -> str:
        return self._settings.embedding_model or "text-embedding-3-small"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(model=self.model, input=texts)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

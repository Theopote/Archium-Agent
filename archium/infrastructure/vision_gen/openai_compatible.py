"""OpenAI-compatible Images API adapter for Vision Engine."""

from __future__ import annotations

import base64
from typing import Any

from archium.config.settings import Settings, get_settings
from archium.domain.visual.vision_generation import GenerationSpec
from archium.infrastructure.vision_gen.base import GeneratedImageBytes
from archium.logging import get_logger

logger = get_logger(__name__, operation="vision_openai_images")


def _map_size(width: int, height: int) -> str:
    ratio = width / max(height, 1)
    if ratio >= 1.25:
        return "1792x1024"
    if ratio <= 0.8:
        return "1024x1792"
    return "1024x1024"


class OpenAICompatibleVisionImageGenerator:
    """Calls ``images.generate`` on an OpenAI-compatible endpoint."""

    provider = "openai_compatible"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    @property
    def model(self) -> str:
        return self._settings.vision_image_generation_model

    def is_available(self) -> bool:
        return self._settings.vision_image_api_configured or self._client is not None

    def generate(self, spec: GenerationSpec) -> GeneratedImageBytes:
        if not self.is_available():
            raise RuntimeError("Vision image API is not configured")

        client = self._client_or_create()
        prompt = self._build_prompt(spec)
        size = _map_size(spec.width, spec.height)
        logger.info(
            "Vision image generate model=%s size=%s hash=%s",
            self.model,
            size,
            spec.prompt_hash,
        )
        response = client.images.generate(
            model=self.model,
            prompt=prompt,
            size=size,
            response_format="b64_json",
            n=1,
        )
        return self._decode_response(response)

    def edit(self, spec: GenerationSpec, *, base_image_path: str) -> GeneratedImageBytes:
        """Conditioned edit via Images API when the provider supports it.

        Many DALL-E 3 endpoints reject ``images.edit``; callers should fall back
        to the local conditioned editor on failure.
        """
        if not self.is_available():
            raise RuntimeError("Vision image API is not configured")

        from pathlib import Path

        path = Path(base_image_path)
        if not path.is_file():
            raise FileNotFoundError(f"base image not found: {path}")

        client = self._client_or_create()
        prompt = self._build_prompt(spec)
        # Classic edit API historically expects square PNG; map toward 1024.
        size = "1024x1024"
        logger.info(
            "Vision image edit model=%s hash=%s base=%s",
            self.model,
            spec.prompt_hash,
            path.name,
        )
        with path.open("rb") as handle:
            response = client.images.edit(
                model=self.model,
                image=handle,
                prompt=prompt[:1000],
                size=size,
                response_format="b64_json",
                n=1,
            )
        return self._decode_response(response)

    def _client_or_create(self) -> Any:
        if self._client is not None:
            return self._client
        from openai import OpenAI

        return OpenAI(
            api_key=self._settings.effective_vision_image_api_key,
            base_url=self._settings.effective_vision_image_base_url,
            timeout=self._settings.llm_timeout_seconds,
            max_retries=0,
        )

    @staticmethod
    def _build_prompt(spec: GenerationSpec) -> str:
        prompt = spec.prompt
        if spec.negative_prompt:
            prompt = f"{prompt}\n\nAvoid: {spec.negative_prompt}"
        return prompt[:3800]

    def _decode_response(self, response: Any) -> GeneratedImageBytes:
        data = response.data[0]
        raw_b64 = getattr(data, "b64_json", None) or (
            data.get("b64_json") if isinstance(data, dict) else None
        )
        if not raw_b64:
            raise RuntimeError("Image API returned no b64_json payload")
        return GeneratedImageBytes(
            data=base64.b64decode(raw_b64),
            mime_type="image/png",
            provider=self.provider,
            model=self.model,
        )

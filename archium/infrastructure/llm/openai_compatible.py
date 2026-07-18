"""OpenAI-compatible LLM provider."""

from __future__ import annotations

import time
from typing import TypeVar

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from pydantic import BaseModel

from archium.config.settings import Settings, get_settings
from archium.exceptions import ConfigurationError, LLMProviderError, StructuredOutputError
from archium.infrastructure.llm.base import LLMRequest, LLMResponse
from archium.infrastructure.llm.structured import parse_and_validate, strip_code_fence
from archium.logging import get_logger

T = TypeVar("T", bound=BaseModel)

_TRANSIENT_ERRORS = (APIConnectionError, APITimeoutError, RateLimitError)

logger = get_logger(__name__, operation="llm")


class OpenAICompatibleProvider:
    """LLM provider using any OpenAI-compatible HTTP API (e.g. Gemini)."""

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
            if not self._settings.llm_configured:
                raise ConfigurationError(
                    "未配置 LLM API Key。请在 .env 中设置 GEMINI_API_KEY 或 LLM_API_KEY。"
                )
            self._client = OpenAI(
                api_key=self._settings.llm_api_key,
                base_url=self._settings.llm_base_url,
                timeout=self._settings.llm_timeout_seconds,
                max_retries=0,
            )
        return self._client

    def generate_text(self, request: LLMRequest) -> str:
        response = self._complete(request)
        return strip_code_fence(response.content)

    def generate_structured(self, request: LLMRequest, schema: type[T]) -> T:
        structured_request = LLMRequest(
            system_prompt=request.system_prompt,
            user_prompt=request.user_prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            json_mode=True,
            metadata=request.metadata,
        )
        last_error: Exception | None = None
        raw = ""

        for attempt in range(self._settings.llm_repair_attempts + 1):
            try:
                raw = self._complete(
                    structured_request if attempt == 0 else self._repair_request(request, raw, last_error)
                ).content
                return parse_and_validate(raw, schema)
            except StructuredOutputError as exc:
                last_error = exc
                if attempt >= self._settings.llm_repair_attempts:
                    raise

        raise StructuredOutputError("Structured output repair exhausted")

    def _repair_request(
        self,
        original: LLMRequest,
        previous_output: str,
        error: Exception | None,
    ) -> LLMRequest:
        return LLMRequest(
            system_prompt=original.system_prompt,
            user_prompt=(
                f"{original.user_prompt}\n\n"
                "Your previous response was invalid. "
                f"Error: {error}\n"
                f"Previous output:\n{previous_output}\n\n"
                "Return ONLY valid JSON matching the requested schema."
            ),
            model=original.model,
            temperature=max(0.1, original.temperature - 0.2),
            max_tokens=original.max_tokens,
            json_mode=True,
            metadata=original.metadata,
        )

    def _complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self._settings.llm_model
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ]

        last_error: Exception | None = None
        for attempt in range(self._settings.llm_max_retries + 1):
            try:
                response = self._create_completion(
                    model=model,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    json_mode=request.json_mode,
                )

                choice = response.choices[0]
                content = choice.message.content or ""
                return LLMResponse(
                    content=content,
                    model=response.model,
                    finish_reason=choice.finish_reason,
                )
            except _TRANSIENT_ERRORS as exc:
                last_error = exc
                if attempt >= self._settings.llm_max_retries:
                    break
                time.sleep(0.5 * (attempt + 1))
            except Exception as exc:
                raise LLMProviderError(f"LLM request failed: {exc}") from exc

        raise LLMProviderError(f"LLM request failed after retries: {last_error}")

    def _create_completion(
        self,
        *,
        model: str,
        messages: list[ChatCompletionMessageParam],
        temperature: float,
        max_tokens: int | None,
        json_mode: bool,
    ) -> ChatCompletion:
        if json_mode:
            try:
                return self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
            except Exception as exc:
                logger.warning(
                    "JSON mode request failed for model %s; falling back to plain completion: %s",
                    model,
                    exc,
                )

        return self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

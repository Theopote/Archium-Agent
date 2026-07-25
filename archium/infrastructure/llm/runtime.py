"""Thin AI capability runtime: capability → model role → provider + trace.

Services should prefer ``LLMRuntime.generate_structured`` over picking models.
Does not introduce Agent classes.
"""

from __future__ import annotations

import time
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.domain.model_roles import ModelRole
from archium.infrastructure.llm.base import LLMProvider, LLMRequest, LLMResponse
from archium.infrastructure.llm.capabilities import (
    LLMCapability,
    model_role_for_capability,
)
from archium.infrastructure.llm.trace import (
    LLMTrace,
    get_llm_trace_recorder,
    new_request_id,
)
from archium.logging import get_logger

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__, operation="llm_runtime")


class LLMRuntime:
    """Capability-aware wrapper around an ``LLMProvider``."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        settings: Settings | None = None,
        session: Session | None = None,
        provider_name: str | None = None,
    ) -> None:
        self._provider = provider
        self._settings = settings or get_settings()
        self._session = session
        self._provider_name = (
            provider_name
            or getattr(self._settings, "llm_provider", None)
            or type(provider).__name__
        )

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    def generate_text(
        self,
        request: LLMRequest,
        *,
        capability: LLMCapability | None = None,
        project_id: UUID | str | None = None,
    ) -> str:
        prepared, role = self._prepare(request, capability=capability, project_id=project_id)
        return self._run(prepared, role=role, capability=capability, project_id=project_id, structured=False)

    def generate_structured(
        self,
        request: LLMRequest,
        schema: type[T],
        *,
        capability: LLMCapability | None = None,
        project_id: UUID | str | None = None,
    ) -> T:
        prepared, role = self._prepare(request, capability=capability, project_id=project_id)
        return self._run(
            prepared,
            role=role,
            capability=capability,
            project_id=project_id,
            structured=True,
            schema=schema,
        )

    def _prepare(
        self,
        request: LLMRequest,
        *,
        capability: LLMCapability | None,
        project_id: UUID | str | None,
    ) -> tuple[LLMRequest, ModelRole | None]:
        role: ModelRole | None = None
        model = request.model
        metadata = dict(request.metadata)

        if capability is not None:
            role = model_role_for_capability(capability)
            metadata.setdefault("capability", capability.value)
            metadata.setdefault("model_role", role.value)
            if model is None:
                model = self._resolve_model(role)

        if project_id is not None:
            metadata.setdefault("project_id", str(project_id))

        request_id = metadata.get("request_id") or new_request_id()
        metadata["request_id"] = request_id

        return (
            LLMRequest(
                system_prompt=request.system_prompt,
                user_prompt=request.user_prompt,
                model=model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                json_mode=request.json_mode,
                metadata=metadata,
                image_paths=request.image_paths,
            ),
            role,
        )

    def _resolve_model(self, role: ModelRole) -> str | None:
        if self._session is None:
            return self._settings.llm_model or None
        try:
            from archium.application.model_role_router import resolve_model_role

            profile = resolve_model_role(self._session, role)
            return (profile.model or "").strip() or self._settings.llm_model
        except Exception as exc:  # noqa: BLE001 — routing must not break generation
            logger.warning("model role resolve failed for %s: %s", role.value, exc)
            return self._settings.llm_model or None

    def _run(
        self,
        request: LLMRequest,
        *,
        role: ModelRole | None,
        capability: LLMCapability | None,
        project_id: UUID | str | None,
        structured: bool,
        schema: type[T] | None = None,
    ) -> T | str:
        request_id = request.metadata.get("request_id") or new_request_id()
        started = time.perf_counter()
        success = True
        error_type: str | None = None
        result: T | str | None = None
        try:
            if structured:
                assert schema is not None
                result = self._provider.generate_structured(request, schema)
            else:
                result = self._provider.generate_text(request)
            return result
        except Exception as exc:
            success = False
            error_type = type(exc).__name__
            raise
        finally:
            latency_ms = (time.perf_counter() - started) * 1000.0
            last = getattr(self._provider, "last_response", None)
            usage_prompt = usage_completion = usage_total = None
            model_name = request.model or self._settings.llm_model or ""
            if isinstance(last, LLMResponse):
                model_name = last.model or model_name
                usage_prompt = last.prompt_tokens
                usage_completion = last.completion_tokens
                usage_total = last.total_tokens
                if last.latency_ms is not None:
                    latency_ms = float(last.latency_ms)
            trace = LLMTrace(
                request_id=request_id,
                provider=str(self._provider_name),
                model=str(model_name),
                capability=capability.value if capability else request.metadata.get("capability"),
                model_role=role.value if role else request.metadata.get("model_role"),
                prompt_version=request.metadata.get("prompt_version"),
                project_id=(
                    str(project_id)
                    if project_id is not None
                    else request.metadata.get("project_id")
                ),
                prompt_tokens=usage_prompt,
                completion_tokens=usage_completion,
                total_tokens=usage_total,
                latency_ms=round(latency_ms, 2),
                success=success,
                error_type=error_type,
                metadata={
                    k: v
                    for k, v in request.metadata.items()
                    if k not in {"request_id"} and isinstance(v, str)
                },
            )
            try:
                get_llm_trace_recorder().record(trace)
            except Exception as exc:  # noqa: BLE001
                logger.warning("llm trace record failed: %s", exc)

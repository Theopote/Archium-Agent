"""LLM call tracing (tokens, latency, capability) — non-secret.

Traces stay in-process by default (ring buffer + structured log). When
``llm_trace_persist_enabled`` is on, also persist rows without prompts/keys.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Protocol
from uuid import UUID

from archium.logging import get_logger

logger = get_logger(__name__, operation="llm_trace")


@dataclass(frozen=True)
class LLMUsage:
    """Token usage from a provider response (when available)."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class LLMTrace:
    """One LLM call audit record (never includes prompts or API keys)."""

    request_id: str
    provider: str
    model: str
    capability: str | None = None
    model_role: str | None = None
    prompt_version: str | None = None
    project_id: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None
    success: bool = True
    error_type: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class LLMTraceRecorder(Protocol):
    def record(self, trace: LLMTrace) -> None: ...


class InMemoryLLMTraceRecorder:
    """Bounded in-memory sink for tests and local debugging."""

    def __init__(self, *, maxlen: int = 500) -> None:
        self._maxlen = max(1, int(maxlen))
        self._items: deque[LLMTrace] = deque(maxlen=self._maxlen)
        self._lock = threading.Lock()

    def record(self, trace: LLMTrace) -> None:
        with self._lock:
            self._items.append(trace)
        logger.info(
            "llm_trace request_id=%s capability=%s model=%s tokens=%s latency_ms=%s success=%s",
            trace.request_id,
            trace.capability,
            trace.model,
            trace.total_tokens,
            trace.latency_ms,
            trace.success,
        )

    def list_recent(self, limit: int = 50) -> list[LLMTrace]:
        with self._lock:
            items = list(self._items)
        if limit <= 0:
            return items
        return items[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class DatabaseLLMTraceRecorder:
    """Persist traces to ``llm_traces`` (independent short sessions)."""

    def record(self, trace: LLMTrace) -> None:
        try:
            from archium.config.settings import get_settings

            if not bool(getattr(get_settings(), "llm_trace_persist_enabled", True)):
                return
        except Exception:
            return
        try:
            from archium.infrastructure.database.repositories import LLMTraceRepository
            from archium.infrastructure.database.session import get_session

            with get_session() as session:
                LLMTraceRepository(session).create_from_trace(trace)
                session.commit()
        except Exception:
            logger.exception(
                "llm_trace persist failed request_id=%s",
                trace.request_id,
            )


class FanoutLLMTraceRecorder:
    """Record into multiple sinks; failures in one sink do not block others."""

    def __init__(self, recorders: Sequence[LLMTraceRecorder]) -> None:
        self._recorders = list(recorders)

    def record(self, trace: LLMTrace) -> None:
        for recorder in self._recorders:
            try:
                recorder.record(trace)
            except Exception:
                logger.exception("llm_trace sink failed")

    def list_recent(self, limit: int = 50) -> list[LLMTrace]:
        for recorder in self._recorders:
            list_fn = getattr(recorder, "list_recent", None)
            if callable(list_fn):
                result = list_fn(limit)
                return list(result) if result is not None else []
        return []

    def clear(self) -> None:
        for recorder in self._recorders:
            clear_fn = getattr(recorder, "clear", None)
            if callable(clear_fn):
                clear_fn()


_memory: InMemoryLLMTraceRecorder = InMemoryLLMTraceRecorder()
_recorder: LLMTraceRecorder = FanoutLLMTraceRecorder([_memory, DatabaseLLMTraceRecorder()])
_recorder_lock = threading.Lock()


def get_llm_trace_recorder() -> LLMTraceRecorder:
    return _recorder


def get_memory_llm_trace_recorder() -> InMemoryLLMTraceRecorder:
    return _memory


def set_llm_trace_recorder(recorder: LLMTraceRecorder | None) -> None:
    """Replace the process-wide recorder (tests). Pass None to reset default."""
    global _recorder, _memory
    with _recorder_lock:
        if recorder is None:
            _memory = InMemoryLLMTraceRecorder()
            _recorder = FanoutLLMTraceRecorder([_memory, DatabaseLLMTraceRecorder()])
        else:
            _recorder = recorder


def list_persisted_traces_for_project(project_id: UUID, *, limit: int = 50) -> list[LLMTrace]:
    from archium.infrastructure.database.repositories import LLMTraceRepository
    from archium.infrastructure.database.session import get_session

    with get_session() as session:
        return LLMTraceRepository(session).list_for_project(project_id, limit=limit)


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def usage_from_openai_completion(response: object) -> LLMUsage:
    """Extract usage from an OpenAI ChatCompletion-like object."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return LLMUsage()
    return LLMUsage(
        prompt_tokens=_as_optional_int(getattr(usage, "prompt_tokens", None)),
        completion_tokens=_as_optional_int(getattr(usage, "completion_tokens", None)),
        total_tokens=_as_optional_int(getattr(usage, "total_tokens", None)),
    )


def _as_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, (str, bytes, bytearray)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None

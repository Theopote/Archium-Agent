"""LLM call tracing (tokens, latency, capability) — non-secret.

Traces stay in-process by default (ring buffer + structured log). Persistence
to DB can wrap ``LLMTraceRecorder`` later without changing call sites.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Protocol

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


_recorder: InMemoryLLMTraceRecorder = InMemoryLLMTraceRecorder()
_recorder_lock = threading.Lock()


def get_llm_trace_recorder() -> InMemoryLLMTraceRecorder:
    return _recorder


def set_llm_trace_recorder(recorder: InMemoryLLMTraceRecorder | None) -> None:
    """Replace the process-wide recorder (tests). Pass None to reset default."""
    global _recorder
    with _recorder_lock:
        _recorder = recorder if recorder is not None else InMemoryLLMTraceRecorder()


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
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

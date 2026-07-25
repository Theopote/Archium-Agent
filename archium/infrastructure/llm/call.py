"""Helper so Services can call through Runtime without rewriting constructors."""

from __future__ import annotations

from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from archium.config.settings import Settings
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.capabilities import LLMCapability
from archium.infrastructure.llm.runtime import LLMRuntime

T = TypeVar("T", bound=BaseModel)


def generate_structured(
    llm: LLMProvider,
    request: LLMRequest,
    schema: type[T],
    *,
    capability: LLMCapability | None = None,
    project_id: UUID | str | None = None,
    session: Session | None = None,
    settings: Settings | None = None,
) -> T:
    """Capability-aware structured generation with tracing.

    If ``llm`` is already an ``LLMRuntime``, delegates to it; otherwise wraps once.
    """
    if isinstance(llm, LLMRuntime):
        return llm.generate_structured(
            request,
            schema,
            capability=capability,
            project_id=project_id,
        )
    return LLMRuntime(llm, settings=settings, session=session).generate_structured(
        request,
        schema,
        capability=capability,
        project_id=project_id,
    )

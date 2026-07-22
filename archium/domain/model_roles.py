"""Multi-model role registry — task-specific LLM / vision / OCR routing."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, field_serializer, field_validator

from archium.domain._base import DomainModel


class ModelRole(StrEnum):
    """Archium task roles for model routing (distinct from PipelineRole)."""

    PLANNING = "planning"
    STRUCTURED_OUTPUT = "structured_output"
    VISION = "vision"
    OCR = "ocr"
    IMAGE_GENERATION = "image_generation"
    IMAGE_EDITING = "image_editing"
    VISUAL_CRITIC = "visual_critic"
    RESEARCH = "research"
    EMBEDDING = "embedding"


# Roles required for the default generation path (OCR / image gen are optional).
CORE_MODEL_ROLES: frozenset[ModelRole] = frozenset(
    {
        ModelRole.PLANNING,
        ModelRole.STRUCTURED_OUTPUT,
        ModelRole.VISION,
        ModelRole.VISUAL_CRITIC,
        ModelRole.RESEARCH,
    }
)


class ModelProfile(DomainModel):
    """Non-secret model configuration; API keys resolved via credential store."""

    id: str = Field(min_length=1, max_length=80)
    provider: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=120)
    base_url: str | None = None
    api_key_env: str | None = Field(
        default=None,
        max_length=120,
        description="Env var name for optional per-profile key; never persisted as plaintext.",
    )

    roles: set[ModelRole] = Field(default_factory=set)
    local: bool = False
    supports_vision: bool = False
    supports_json_schema: bool = False
    supports_image_generation: bool = False
    supports_image_editing: bool = False

    context_window: int | None = Field(default=None, ge=1024)
    cost_tier: Literal["low", "medium", "high"] = "medium"
    timeout_seconds: int = Field(default=120, gt=0, le=600)
    max_retries: int = Field(default=2, ge=0, le=10)

    @field_validator("roles", mode="before")
    @classmethod
    def _coerce_roles(cls, value: object) -> set[ModelRole]:
        if value is None:
            return set()
        if isinstance(value, set):
            return {ModelRole(v) if not isinstance(v, ModelRole) else v for v in value}
        if isinstance(value, (list, tuple)):
            return {ModelRole(v) if not isinstance(v, ModelRole) else v for v in value}
        raise TypeError(f"roles must be a set or list, got {type(value)!r}")

    @field_serializer("roles")
    def _serialize_roles(self, roles: set[ModelRole]) -> list[str]:
        return sorted(role.value for role in roles)


class ModelRoleAssignment(DomainModel):
    """Explicit role → profile mapping for advanced configuration."""

    role: ModelRole
    profile_id: str = Field(min_length=1, max_length=80)


def model_profile_from_llm_profile(
    *,
    profile_id: str,
    provider: str,
    model: str,
    base_url: str | None,
    timeout_seconds: float,
    roles: set[ModelRole] | None = None,
) -> ModelProfile:
    """Bridge legacy single LLMProfile into ModelProfile for backward compatibility."""
    default_roles = roles or {
        ModelRole.PLANNING,
        ModelRole.STRUCTURED_OUTPUT,
        ModelRole.RESEARCH,
        ModelRole.VISUAL_CRITIC,
    }
    return ModelProfile(
        id=profile_id,
        provider=provider,
        model=model,
        base_url=base_url,
        roles=default_roles,
        supports_json_schema=True,
        timeout_seconds=int(timeout_seconds),
    )

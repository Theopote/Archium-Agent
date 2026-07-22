"""Model role registry persistence and task routing."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from archium.application.llm_profile_service import LLMProfileService
from archium.domain.llm_profile import LLMProfile
from archium.domain.model_roles import (
    CORE_MODEL_ROLES,
    ModelProfile,
    ModelRole,
    ModelRoleAssignment,
    model_profile_from_llm_profile,
)
from archium.exceptions import ConfigurationError
from archium.infrastructure.database.user_preference_repository import UserPreferenceRepository

MODEL_PROFILES_KEY = "archium.model.profiles"
MODEL_ROLE_ASSIGNMENTS_KEY = "archium.model.role_assignments"
DEFAULT_PROFILE_ID = "default"


@dataclass(frozen=True)
class ModelCallAudit:
    """Non-secret trace record for external model calls."""

    role: ModelRole
    provider: str
    model: str
    request_id: str | None = None
    workflow_run_id: str | None = None
    slide_id: str | None = None
    duration_ms: float | None = None
    retry_count: int = 0
    success: bool = True
    failure_type: str | None = None


class ModelRoleRegistryService:
    """Load/save model profiles and role assignments from user preferences."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._preferences = UserPreferenceRepository(session)
        self._llm_profiles = LLMProfileService(session)

    def list_profiles(self) -> list[ModelProfile]:
        pref = self._preferences.get_global(MODEL_PROFILES_KEY)
        if pref is not None and isinstance(pref.value, list):
            return [ModelProfile.model_validate(item) for item in pref.value]
        llm = self._llm_profiles.get_or_create_default_profile()
        return [self._default_profile_from_llm(llm)]

    def save_profiles(self, profiles: list[ModelProfile]) -> list[ModelProfile]:
        payload = [profile.model_dump(mode="json") for profile in profiles]
        self._preferences.upsert_global(
            MODEL_PROFILES_KEY,
            payload,
            description="Archium model profiles (non-secret)",
        )
        return profiles

    def list_role_assignments(self) -> list[ModelRoleAssignment]:
        pref = self._preferences.get_global(MODEL_ROLE_ASSIGNMENTS_KEY)
        if pref is not None and isinstance(pref.value, list):
            return [ModelRoleAssignment.model_validate(item) for item in pref.value]
        return []

    def save_role_assignments(
        self,
        assignments: list[ModelRoleAssignment],
    ) -> list[ModelRoleAssignment]:
        payload = [item.model_dump(mode="json") for item in assignments]
        self._preferences.upsert_global(
            MODEL_ROLE_ASSIGNMENTS_KEY,
            payload,
            description="Archium model role → profile assignments",
        )
        return assignments

    def profile_for_role(self, role: ModelRole) -> ModelProfile | None:
        profiles = {profile.id: profile for profile in self.list_profiles()}
        for assignment in self.list_role_assignments():
            if assignment.role == role:
                return profiles.get(assignment.profile_id)
        for profile in profiles.values():
            if role in profile.roles:
                return profile
        return None

    def _default_profile_from_llm(self, llm: LLMProfile) -> ModelProfile:
        return model_profile_from_llm_profile(
            profile_id=DEFAULT_PROFILE_ID,
            provider=llm.provider,
            model=llm.model,
            base_url=llm.base_url,
            timeout_seconds=llm.timeout_seconds,
        )


class ModelRoleRouter:
    """Resolve the best ModelProfile for a given task role."""

    def __init__(self, registry: ModelRoleRegistryService) -> None:
        self._registry = registry

    def resolve(
        self,
        role: ModelRole,
        *,
        require_local: bool = False,
        require_json_schema: bool = False,
        require_vision: bool = False,
    ) -> ModelProfile:
        profile = self._registry.profile_for_role(role)
        if profile is None:
            if role not in CORE_MODEL_ROLES:
                raise ConfigurationError(
                    f"未配置 {role.value} 模型角色。"
                    "请在「系统 → AI 服务 → 高级角色映射」中指定，"
                    "或禁用依赖该角色的功能。"
                )
            llm = self._registry._llm_profiles.get_or_create_default_profile()
            profile = self._registry._default_profile_from_llm(llm)

        if require_local and not profile.local:
            raise ConfigurationError(f"角色 {role.value} 需要本地模型，但当前配置为云端模型。")
        if require_json_schema and not profile.supports_json_schema:
            raise ConfigurationError(f"角色 {role.value} 需要 JSON Schema 支持。")
        if require_vision and not profile.supports_vision:
            raise ConfigurationError(f"角色 {role.value} 需要视觉模型能力。")
        return profile

    def resolve_optional(self, role: ModelRole) -> ModelProfile | None:
        """Return profile when configured; None for optional roles (OCR, image gen)."""
        try:
            return self.resolve(role)
        except ConfigurationError:
            if role in CORE_MODEL_ROLES:
                raise
            return None

    def configured_roles(self) -> set[ModelRole]:
        roles: set[ModelRole] = set()
        for profile in self._registry.list_profiles():
            roles.update(profile.roles)
        for assignment in self._registry.list_role_assignments():
            roles.add(assignment.role)
        return roles


def resolve_model_role(
    session: Session,
    role: ModelRole,
    *,
    require_local: bool = False,
    require_json_schema: bool = False,
    require_vision: bool = False,
) -> ModelProfile:
    """Convenience entry point for services that need a routed model profile."""
    registry = ModelRoleRegistryService(session)
    router = ModelRoleRouter(registry)
    return router.resolve(
        role,
        require_local=require_local,
        require_json_schema=require_json_schema,
        require_vision=require_vision,
    )


def audit_model_call(
    profile: ModelProfile,
    role: ModelRole,
    *,
    request_id: str | None = None,
    workflow_run_id: str | None = None,
    slide_id: str | None = None,
    duration_ms: float | None = None,
    retry_count: int = 0,
    success: bool = True,
    failure_type: str | None = None,
) -> ModelCallAudit:
    """Build a non-secret audit record (never includes API keys)."""
    return ModelCallAudit(
        role=role,
        provider=profile.provider,
        model=profile.model,
        request_id=request_id,
        workflow_run_id=workflow_run_id,
        slide_id=slide_id,
        duration_ms=duration_ms,
        retry_count=retry_count,
        success=success,
        failure_type=failure_type,
    )

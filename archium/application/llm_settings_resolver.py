"""Resolve effective LLM settings from session, keyring, and environment."""

from __future__ import annotations

from uuid import UUID

from archium.application.llm_profile_service import LLMProfileService
from archium.config.settings import Settings, get_settings
from archium.domain.llm_profile import LLMProfile
from archium.infrastructure.credentials.resolver import resolve_llm_api_key
from archium.infrastructure.credentials.store import CredentialStore
from archium.infrastructure.database.session import get_session


def get_effective_settings(
    *,
    session_api_key: str | None = None,
    base_settings: Settings | None = None,
    profile: LLMProfile | None = None,
    credential_store: CredentialStore | None = None,
    project_id: UUID | str | None = None,
) -> Settings:
    """Return settings with LLM config resolved in priority order.

    Priority:
    1. Session-only API key (Streamlit)
    2. Keyring credential for the active profile
    3. Environment / .env fallback
    4. Optional project LLM tier (fast / quality model override)
    """
    settings = base_settings or get_settings()
    resolved_profile = profile

    if resolved_profile is None:
        with get_session() as session:
            resolved_profile = LLMProfileService(session).get_default_profile()

    if resolved_profile is None:
        if session_api_key:
            settings = settings.model_copy(update={"llm_api_key": session_api_key})
        return _apply_project_tier(settings, project_id)

    api_key, _ = resolve_llm_api_key(
        resolved_profile,
        session_api_key=session_api_key,
        env_api_key=settings.llm_api_key,
        credential_store=credential_store,
    )

    updates: dict[str, object] = {
        "llm_provider": resolved_profile.llm_provider,
        "llm_api_key": api_key,
        "llm_model": resolved_profile.model,
        "llm_timeout_seconds": resolved_profile.timeout_seconds,
    }
    if resolved_profile.base_url:
        updates["llm_base_url"] = resolved_profile.base_url

    settings = settings.model_copy(update=updates)
    return _apply_project_tier(settings, project_id)


def _apply_project_tier(
    settings: Settings,
    project_id: UUID | str | None,
) -> Settings:
    if project_id is None:
        return settings
    try:
        pid = project_id if isinstance(project_id, UUID) else UUID(str(project_id))
    except ValueError:
        return settings
    try:
        from archium.application.project_llm_tier_service import ProjectLLMTierService

        with get_session() as session:
            return ProjectLLMTierService(session).apply_to_settings(settings, pid)
    except Exception:
        return settings

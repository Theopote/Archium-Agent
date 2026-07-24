"""Resolve effective LLM settings from session, keyring, and environment."""

from __future__ import annotations

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
) -> Settings:
    """Return settings with LLM config resolved in priority order.

    Priority:
    1. Session-only API key (Streamlit)
    2. Keyring credential for the active profile
    3. Environment / .env fallback
    """
    settings = base_settings or get_settings()
    resolved_profile = profile

    if resolved_profile is None:
        with get_session() as session:
            resolved_profile = LLMProfileService(session).get_default_profile()

    if resolved_profile is None:
        if session_api_key:
            return settings.model_copy(update={"llm_api_key": session_api_key})
        return settings

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

    return settings.model_copy(update=updates)

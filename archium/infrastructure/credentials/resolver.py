"""Resolve LLM API keys from session, keyring, and environment."""

from __future__ import annotations

from typing import Literal

from archium.domain.llm_profile import LLMProfile
from archium.infrastructure.credentials.store import CredentialStore

PEXELS_CREDENTIAL_KEY = "pexels_api_key"


UNSPLASH_CREDENTIAL_KEY = "unsplash_access_key"


def resolve_unsplash_access_key(
    *,
    session_api_key: str | None = None,
    env_api_key: str | None = None,
    credential_store: CredentialStore | None = None,
) -> tuple[str | None, Literal["session", "keyring", "env", "none"]]:
    """Resolve Unsplash access key with session > keyring > env priority."""
    store = credential_store or CredentialStore()
    if session_api_key:
        return session_api_key, "session"
    stored = store.get(UNSPLASH_CREDENTIAL_KEY)
    if stored:
        return stored, "keyring"
    if env_api_key:
        return env_api_key, "env"
    return None, "none"


def resolve_pexels_api_key(
    *,
    session_api_key: str | None = None,
    env_api_key: str | None = None,
    credential_store: CredentialStore | None = None,
) -> tuple[str | None, Literal["session", "keyring", "env", "none"]]:
    """Resolve Pexels API key with session > keyring > env priority."""
    store = credential_store or CredentialStore()
    if session_api_key:
        return session_api_key, "session"
    stored = store.get(PEXELS_CREDENTIAL_KEY)
    if stored:
        return stored, "keyring"
    if env_api_key:
        return env_api_key, "env"
    return None, "none"


def resolve_llm_api_key(
    profile: LLMProfile,
    *,
    session_api_key: str | None = None,
    env_api_key: str | None = None,
    credential_store: CredentialStore | None = None,
) -> tuple[str | None, Literal["session", "keyring", "env", "none"]]:
    """Resolve API key with session > keyring > env priority."""
    store = credential_store or CredentialStore()
    if session_api_key:
        return session_api_key, "session"
    stored = store.get(profile.credential_key)
    if stored:
        return stored, "keyring"
    if env_api_key:
        return env_api_key, "env"
    return None, "none"

"""Streamlit helpers for web research (Tavily) settings."""

from __future__ import annotations

import streamlit as st

from archium.config.settings import get_settings
from archium.infrastructure.credentials.resolver import (
    TAVILY_CREDENTIAL_KEY,
    resolve_tavily_api_key,
)
from archium.infrastructure.credentials.store import CredentialStore


def session_tavily_api_key() -> str | None:
    value = st.session_state.get("tavily_session_api_key")
    return value if isinstance(value, str) and value else None


def tavily_credential_status() -> tuple[bool, str | None, str]:
    api_key, source = resolve_tavily_api_key(
        session_api_key=session_tavily_api_key(),
        env_api_key=get_settings().tavily_api_key,
    )
    masked = CredentialStore.mask_secret(api_key) if api_key else None
    return bool(api_key), masked, source


def save_tavily_api_key(*, api_key: str, persist: bool, session_store: dict) -> None:
    cleaned = api_key.strip()
    if not cleaned:
        return
    if persist:
        CredentialStore().save(TAVILY_CREDENTIAL_KEY, cleaned)
        session_store.pop("tavily_session_api_key", None)
    else:
        session_store["tavily_session_api_key"] = cleaned


def delete_tavily_api_key(*, session_store: dict) -> None:
    CredentialStore().delete(TAVILY_CREDENTIAL_KEY)
    session_store.pop("tavily_session_api_key", None)

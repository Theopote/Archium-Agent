"""Streamlit helpers for Pexels web image search settings."""

from __future__ import annotations

import streamlit as st

from archium.config.settings import get_settings
from archium.infrastructure.credentials.resolver import (
    PEXELS_CREDENTIAL_KEY,
    UNSPLASH_CREDENTIAL_KEY,
    resolve_pexels_api_key,
    resolve_unsplash_access_key,
)
from archium.infrastructure.credentials.store import CredentialStore


def session_pexels_api_key() -> str | None:
    value = st.session_state.get("pexels_session_api_key")
    return value if isinstance(value, str) and value else None


def session_unsplash_api_key() -> str | None:
    value = st.session_state.get("unsplash_session_api_key")
    return value if isinstance(value, str) and value else None


def pexels_credential_status() -> tuple[bool, str | None, str]:
    api_key, source = resolve_pexels_api_key(
        session_api_key=session_pexels_api_key(),
        env_api_key=get_settings().pexels_api_key,
    )
    masked = CredentialStore.mask_secret(api_key) if api_key else None
    return bool(api_key), masked, source


def unsplash_credential_status() -> tuple[bool, str | None, str]:
    api_key, source = resolve_unsplash_access_key(
        session_api_key=session_unsplash_api_key(),
        env_api_key=get_settings().unsplash_access_key,
    )
    masked = CredentialStore.mask_secret(api_key) if api_key else None
    return bool(api_key), masked, source


def save_pexels_api_key(*, api_key: str, persist: bool, session_store: dict) -> None:
    cleaned = api_key.strip()
    if not cleaned:
        return
    if persist:
        CredentialStore().save(PEXELS_CREDENTIAL_KEY, cleaned)
        session_store.pop("pexels_session_api_key", None)
    else:
        session_store["pexels_session_api_key"] = cleaned


def save_unsplash_api_key(*, api_key: str, persist: bool, session_store: dict) -> None:
    cleaned = api_key.strip()
    if not cleaned:
        return
    if persist:
        CredentialStore().save(UNSPLASH_CREDENTIAL_KEY, cleaned)
        session_store.pop("unsplash_session_api_key", None)
    else:
        session_store["unsplash_session_api_key"] = cleaned


def delete_pexels_api_key(*, session_store: dict) -> None:
    CredentialStore().delete(PEXELS_CREDENTIAL_KEY)
    session_store.pop("pexels_session_api_key", None)


def delete_unsplash_api_key(*, session_store: dict) -> None:
    CredentialStore().delete(UNSPLASH_CREDENTIAL_KEY)
    session_store.pop("unsplash_session_api_key", None)

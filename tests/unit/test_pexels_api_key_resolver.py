"""Tests for Pexels API key resolution."""

from __future__ import annotations

from archium.infrastructure.credentials.resolver import (
    PEXELS_CREDENTIAL_KEY,
    resolve_pexels_api_key,
)
from archium.infrastructure.credentials.store import CredentialStore


class FakeCredentialStore(CredentialStore):
    def __init__(self, stored: dict[str, str]) -> None:
        self._stored = stored

    def get(self, credential_key: str) -> str | None:
        return self._stored.get(credential_key)


def test_resolve_pexels_api_key_prefers_session() -> None:
    key, source = resolve_pexels_api_key(
        session_api_key="session-key",
        env_api_key="env-key",
        credential_store=FakeCredentialStore({PEXELS_CREDENTIAL_KEY: "ring-key"}),
    )
    assert key == "session-key"
    assert source == "session"


def test_resolve_pexels_api_key_falls_back_to_keyring() -> None:
    key, source = resolve_pexels_api_key(
        env_api_key="env-key",
        credential_store=FakeCredentialStore({PEXELS_CREDENTIAL_KEY: "ring-key"}),
    )
    assert key == "ring-key"
    assert source == "keyring"

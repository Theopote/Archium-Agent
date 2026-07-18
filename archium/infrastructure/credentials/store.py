"""System credential store backed by the OS keyring."""

from __future__ import annotations

import contextlib

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

SERVICE_NAME = "archium-agent"


class CredentialStore:
    """Persist secrets in the platform credential manager (Windows/macOS/Linux)."""

    def __init__(self, service_name: str = SERVICE_NAME) -> None:
        self._service_name = service_name

    def save(self, credential_key: str, secret: str) -> None:
        keyring.set_password(self._service_name, credential_key, secret)

    def get(self, credential_key: str) -> str | None:
        try:
            return keyring.get_password(self._service_name, credential_key)
        except KeyringError:
            return None

    def delete(self, credential_key: str) -> None:
        with contextlib.suppress(PasswordDeleteError):
            keyring.delete_password(self._service_name, credential_key)

    def has_credential(self, credential_key: str) -> bool:
        return bool(self.get(credential_key))

    @staticmethod
    def mask_secret(secret: str, *, visible_chars: int = 4) -> str:
        """Return a display-safe suffix hint such as ••••••••A9x2."""
        if not secret:
            return ""
        suffix = secret[-visible_chars:] if len(secret) >= visible_chars else secret
        return f"••••••••{suffix}"

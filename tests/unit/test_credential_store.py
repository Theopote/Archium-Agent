"""Unit tests for credential store masking and keyring integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from archium.infrastructure.credentials.store import CredentialStore


def test_mask_secret_shows_suffix_only() -> None:
    masked = CredentialStore.mask_secret("sk-abcdefghijklmnop")
    assert masked == "••••••••mnop"
    assert "sk-" not in masked


def test_save_get_delete_round_trip() -> None:
    store = CredentialStore(service_name="archium-agent-test")
    with patch("archium.infrastructure.credentials.store.keyring") as mock_keyring:
        store.save("test-key", "secret-value")
        mock_keyring.set_password.assert_called_once_with(
            "archium-agent-test",
            "test-key",
            "secret-value",
        )

        mock_keyring.get_password.return_value = "secret-value"
        assert store.get("test-key") == "secret-value"

        store.delete("test-key")
        mock_keyring.delete_password.assert_called_once_with("archium-agent-test", "test-key")


def test_get_returns_none_on_keyring_error() -> None:
    import keyring.errors

    store = CredentialStore(service_name="archium-agent-test")
    with patch("archium.infrastructure.credentials.store.keyring") as mock_keyring:
        mock_keyring.get_password.side_effect = keyring.errors.KeyringError("backend unavailable")
        assert store.get("missing") is None

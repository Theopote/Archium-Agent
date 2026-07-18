"""LLM profile persistence and credential management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from archium.domain.llm_profile import (
    DEFAULT_CREDENTIAL_KEY,
    DEFAULT_PROFILE_NAME,
    LLMProfile,
)
from archium.infrastructure.credentials.resolver import resolve_llm_api_key
from archium.infrastructure.credentials.store import CredentialStore
from archium.infrastructure.database.user_preference_repository import UserPreferenceRepository
from archium.infrastructure.llm.provider_presets import PROVIDER_BY_SLUG

LLM_DEFAULT_PROFILE_KEY = "archium.llm.default_profile"


@dataclass(frozen=True)
class CredentialStatus:
    """Non-secret credential state for UI display."""

    configured: bool
    source: Literal["session", "keyring", "env", "none"]
    masked_hint: str | None = None


class LLMProfileService:
    """Manage default LLM profile metadata and associated credentials."""

    def __init__(
        self,
        session: Session,
        *,
        credential_store: CredentialStore | None = None,
    ) -> None:
        self._session = session
        self._preferences = UserPreferenceRepository(session)
        self._credentials = credential_store or CredentialStore()

    def get_default_profile(self) -> LLMProfile | None:
        pref = self._preferences.get_global(LLM_DEFAULT_PROFILE_KEY)
        if pref is None:
            return None
        if not isinstance(pref.value, dict):
            return None
        return LLMProfile.model_validate(pref.value)

    def get_or_create_default_profile(self) -> LLMProfile:
        profile = self.get_default_profile()
        if profile is not None:
            return profile
        gemini = PROVIDER_BY_SLUG["gemini"]
        return LLMProfile(
            name=DEFAULT_PROFILE_NAME,
            provider=gemini.slug,
            base_url=gemini.base_url,
            model=gemini.model,
            credential_key=DEFAULT_CREDENTIAL_KEY,
        )

    def save_default_profile(self, profile: LLMProfile) -> LLMProfile:
        profile.touch()
        self._preferences.upsert_global(
            LLM_DEFAULT_PROFILE_KEY,
            profile.model_dump(mode="json"),
            description="Default LLM profile for Archium UI",
        )
        return profile

    def save_api_key(
        self,
        profile: LLMProfile,
        api_key: str,
        *,
        persist: bool,
        session_store: dict[str, object] | None = None,
    ) -> None:
        if persist:
            self._credentials.save(profile.credential_key, api_key)
            if session_store is not None:
                session_store.pop("llm_session_api_key", None)
        elif session_store is not None:
            session_store["llm_session_api_key"] = api_key

    def delete_api_key(self, profile: LLMProfile, *, session_store: dict[str, object] | None = None) -> None:
        self._credentials.delete(profile.credential_key)
        if session_store is not None:
            session_store.pop("llm_session_api_key", None)

    def resolve_api_key(
        self,
        profile: LLMProfile,
        *,
        session_api_key: str | None = None,
        env_api_key: str | None = None,
    ) -> tuple[str | None, Literal["session", "keyring", "env", "none"]]:
        return resolve_llm_api_key(
            profile,
            session_api_key=session_api_key,
            env_api_key=env_api_key,
            credential_store=self._credentials,
        )

    def credential_status(
        self,
        profile: LLMProfile,
        *,
        session_api_key: str | None = None,
        env_api_key: str | None = None,
    ) -> CredentialStatus:
        api_key, source = self.resolve_api_key(
            profile,
            session_api_key=session_api_key,
            env_api_key=env_api_key,
        )
        if not api_key:
            return CredentialStatus(configured=False, source="none")
        return CredentialStatus(
            configured=True,
            source=source,
            masked_hint=CredentialStore.mask_secret(api_key),
        )

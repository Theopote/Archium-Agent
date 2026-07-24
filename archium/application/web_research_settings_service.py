"""Persist UI overrides for web research behavior."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.infrastructure.database.user_preference_repository import UserPreferenceRepository

WEB_RESEARCH_SETTINGS_KEY = "archium.web_research.settings"

_ALLOWED_PROVIDERS = frozenset({"tavily", "duckduckgo"})


@dataclass(frozen=True)
class WebResearchPreferences:
    """Effective web research flags for autonomous research."""

    enabled: bool
    provider: str
    auto_on_concept_planning: bool


def apply_web_research_preferences(
    settings: Settings,
    preferences: WebResearchPreferences,
) -> Settings:
    """Return settings with UI-persisted web research overrides applied."""
    return settings.model_copy(
        update={
            "web_research_enabled": preferences.enabled,
            "web_research_provider": preferences.provider,
            "web_research_auto_on_concept_planning": preferences.auto_on_concept_planning,
        }
    )


class WebResearchSettingsService:
    """Load and save non-secret web research preferences."""

    def __init__(self, session: Session) -> None:
        self._preferences = UserPreferenceRepository(session)

    def get_preferences(self, *, base_settings: Settings | None = None) -> WebResearchPreferences:
        settings = base_settings or get_settings()
        stored = self._load_stored()
        enabled = stored.get("enabled", settings.web_research_enabled)
        provider = stored.get("provider", settings.web_research_provider)
        auto_on_concept = stored.get(
            "auto_on_concept_planning",
            settings.web_research_auto_on_concept_planning,
        )
        normalized_provider = str(provider).strip().lower()
        if normalized_provider not in _ALLOWED_PROVIDERS:
            normalized_provider = (settings.web_research_provider or "tavily").strip().lower()
        return WebResearchPreferences(
            enabled=bool(enabled),
            provider=normalized_provider,
            auto_on_concept_planning=bool(auto_on_concept),
        )

    def save_preferences(
        self,
        *,
        enabled: bool,
        provider: str,
        auto_on_concept_planning: bool,
    ) -> WebResearchPreferences:
        normalized_provider = provider.strip().lower()
        if normalized_provider not in _ALLOWED_PROVIDERS:
            normalized_provider = "tavily"
        payload = {
            "enabled": enabled,
            "provider": normalized_provider,
            "auto_on_concept_planning": auto_on_concept_planning,
        }
        self._preferences.upsert_global(
            WEB_RESEARCH_SETTINGS_KEY,
            payload,
            description="Web research UI preferences",
        )
        return WebResearchPreferences(
            enabled=enabled,
            provider=normalized_provider,
            auto_on_concept_planning=auto_on_concept_planning,
        )

    def _load_stored(self) -> dict[str, object]:
        pref = self._preferences.get_global(WEB_RESEARCH_SETTINGS_KEY)
        if pref is None or not isinstance(pref.value, dict):
            return {}
        return pref.value

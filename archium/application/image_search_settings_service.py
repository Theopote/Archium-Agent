"""Persist UI overrides for web image search behavior."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.infrastructure.database.user_preference_repository import UserPreferenceRepository

IMAGE_SEARCH_SETTINGS_KEY = "archium.image_search.settings"


@dataclass(frozen=True)
class ImageSearchPreferences:
    """Effective web image search flags for export."""

    enabled: bool
    persist_to_library: bool


class ImageSearchSettingsService:
    """Load and save non-secret web image search preferences."""

    def __init__(self, session: Session) -> None:
        self._preferences = UserPreferenceRepository(session)

    def get_preferences(self, *, base_settings: Settings | None = None) -> ImageSearchPreferences:
        settings = base_settings or get_settings()
        stored = self._load_stored()
        enabled = stored.get("enabled", settings.web_image_search_enabled)
        persist = stored.get("persist_to_library", settings.web_image_search_persist_to_library)
        return ImageSearchPreferences(
            enabled=bool(enabled),
            persist_to_library=bool(persist),
        )

    def save_preferences(
        self,
        *,
        enabled: bool,
        persist_to_library: bool,
    ) -> ImageSearchPreferences:
        payload = {
            "enabled": enabled,
            "persist_to_library": persist_to_library,
        }
        self._preferences.upsert_global(
            IMAGE_SEARCH_SETTINGS_KEY,
            payload,
            description="Web image search UI preferences",
        )
        return ImageSearchPreferences(enabled=enabled, persist_to_library=persist_to_library)

    def _load_stored(self) -> dict[str, object]:
        pref = self._preferences.get_global(IMAGE_SEARCH_SETTINGS_KEY)
        if pref is None or not isinstance(pref.value, dict):
            return {}
        return pref.value

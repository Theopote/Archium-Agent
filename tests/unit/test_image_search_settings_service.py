"""Tests for image search preference persistence."""

from __future__ import annotations

from archium.application.image_search_settings_service import ImageSearchSettingsService
from archium.config.settings import Settings
from sqlalchemy.orm import Session


def test_image_search_preferences_default_from_settings(db_session: Session) -> None:
    settings = Settings(
        _env_file=None,
        web_image_search_enabled=False,
        web_image_search_persist_to_library=False,
    )
    prefs = ImageSearchSettingsService(db_session).get_preferences(base_settings=settings)
    assert prefs.enabled is False
    assert prefs.persist_to_library is False


def test_image_search_preferences_save_and_load(db_session: Session) -> None:
    service = ImageSearchSettingsService(db_session)
    saved = service.save_preferences(enabled=True, persist_to_library=True)
    assert saved.enabled is True
    assert saved.persist_to_library is True

    loaded = service.get_preferences(
        base_settings=Settings(_env_file=None, web_image_search_enabled=False)
    )
    assert loaded.enabled is True
    assert loaded.persist_to_library is True

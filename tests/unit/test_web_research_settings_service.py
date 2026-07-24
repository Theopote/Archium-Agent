"""Unit tests for web research settings service."""

from __future__ import annotations

from archium.application.web_research_settings_service import (
    WebResearchSettingsService,
    apply_web_research_preferences,
)
from archium.config.settings import Settings


def test_get_preferences_uses_env_defaults(db_session, test_settings) -> None:
    service = WebResearchSettingsService(db_session)
    prefs = service.get_preferences(base_settings=test_settings)

    assert prefs.enabled is True
    assert prefs.provider == "tavily"
    assert prefs.auto_on_concept_planning is True


def test_save_preferences_overrides_defaults(db_session, test_settings) -> None:
    service = WebResearchSettingsService(db_session)
    saved = service.save_preferences(
        enabled=False,
        provider="duckduckgo",
        auto_on_concept_planning=False,
    )
    db_session.commit()

    loaded = service.get_preferences(base_settings=test_settings)
    assert loaded == saved
    assert loaded.enabled is False
    assert loaded.provider == "duckduckgo"
    assert loaded.auto_on_concept_planning is False


def test_apply_web_research_preferences_copies_settings() -> None:
    base = Settings(_env_file=None, web_research_enabled=True, web_research_provider="tavily")
    from archium.application.web_research_settings_service import WebResearchPreferences

    prefs = WebResearchPreferences(
        enabled=False,
        provider="duckduckgo",
        auto_on_concept_planning=False,
    )
    effective = apply_web_research_preferences(base, prefs)

    assert effective.web_research_enabled is False
    assert effective.web_research_provider == "duckduckgo"
    assert effective.web_research_auto_on_concept_planning is False
    assert base.web_research_enabled is True

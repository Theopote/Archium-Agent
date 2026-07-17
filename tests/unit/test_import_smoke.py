"""Smoke test that core packages import without API keys."""

from __future__ import annotations


def test_archium_imports() -> None:
    import archium  # noqa: F401
    import archium.application  # noqa: F401
    import archium.domain  # noqa: F401
    import archium.infrastructure  # noqa: F401
    import archium.workflow  # noqa: F401


def test_settings_without_api_key() -> None:
    from archium.config.settings import Settings

    settings = Settings(_env_file=None, llm_api_key=None)
    assert settings.llm_configured is False

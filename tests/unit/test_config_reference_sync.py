"""Tests for configuration registry and generated reference artifacts."""

from __future__ import annotations

from pathlib import Path

from archium.config.registry import (
    FIELD_DOMAINS,
    ConfigDomain,
    iter_setting_specs,
    render_env_example,
    render_markdown_reference,
    validate_registry,
)
from archium.config.settings import Settings

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_registry_covers_all_settings_fields() -> None:
    validate_registry()
    assert set(FIELD_DOMAINS) == set(Settings.model_fields)


def test_review_and_repair_defaults_match_settings() -> None:
    settings = Settings(_env_file=None)
    assert settings.block_export_on_critical_review is False
    assert settings.llm_professional_review_enabled is False
    assert settings.slide_repair_enabled is False
    assert settings.fact_extraction_enabled is True
    assert settings.retrieval_enabled is False

    specs = {spec.field_name: spec for spec in iter_setting_specs()}
    assert specs["block_export_on_critical_review"].default is False
    assert specs["slide_repair_enabled"].default is False
    assert specs["fact_extraction_enabled"].default is True


def test_domain_grouping_includes_core_capability_domains() -> None:
    domains = {spec.domain for spec in iter_setting_specs()}
    assert ConfigDomain.RETRIEVAL in domains
    assert ConfigDomain.REVIEW in domains
    assert ConfigDomain.REPAIR in domains
    assert ConfigDomain.RENDER in domains


def test_generated_env_example_matches_committed_file() -> None:
    expected = render_env_example()
    committed = (_PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    assert committed.replace("\r\n", "\n") == expected.replace("\r\n", "\n")


def test_generated_configuration_reference_matches_committed_file() -> None:
    expected = render_markdown_reference()
    committed = (_PROJECT_ROOT / "docs" / "configuration-reference.md").read_text(encoding="utf-8")
    assert committed.replace("\r\n", "\n") == expected.replace("\r\n", "\n")

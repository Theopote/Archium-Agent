"""Tests for ModelRole and ModelProfile domain models."""

from __future__ import annotations

from archium.domain.model_roles import (
    CORE_MODEL_ROLES,
    ModelProfile,
    ModelRole,
    model_profile_from_llm_profile,
)


def test_model_profile_serializes_roles_as_sorted_list() -> None:
    profile = ModelProfile(
        id="main",
        provider="gemini",
        model="gemini-2.5-flash",
        roles={ModelRole.PLANNING, ModelRole.OCR, ModelRole.STRUCTURED_OUTPUT},
    )
    payload = profile.model_dump(mode="json")
    assert payload["roles"] == ["ocr", "planning", "structured_output"]


def test_model_profile_from_llm_bridge() -> None:
    profile = model_profile_from_llm_profile(
        profile_id="default",
        provider="gemini",
        model="gemini-2.5-flash",
        base_url="https://example.com",
        timeout_seconds=90.0,
    )
    assert profile.id == "default"
    assert ModelRole.PLANNING in profile.roles
    assert ModelRole.OCR not in profile.roles


def test_core_roles_exclude_optional_capabilities() -> None:
    assert ModelRole.OCR not in CORE_MODEL_ROLES
    assert ModelRole.IMAGE_GENERATION not in CORE_MODEL_ROLES
    assert ModelRole.STRUCTURED_OUTPUT in CORE_MODEL_ROLES

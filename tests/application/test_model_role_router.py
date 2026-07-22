"""Tests for ModelRoleRouter."""

from __future__ import annotations

import pytest

from archium.application.model_role_router import ModelRoleRegistryService, ModelRoleRouter
from archium.domain.model_roles import ModelProfile, ModelRole, ModelRoleAssignment
from archium.exceptions import ConfigurationError
from archium.infrastructure.database.session import get_session


def test_resolve_structured_output_from_default_llm() -> None:
    with get_session() as session:
        registry = ModelRoleRegistryService(session)
        registry.save_profiles(
            [
                ModelProfile(
                    id="default",
                    provider="gemini",
                    model="gemini-2.5-flash",
                    roles={ModelRole.STRUCTURED_OUTPUT, ModelRole.PLANNING},
                    supports_json_schema=True,
                )
            ]
        )
        registry.save_role_assignments([])
        session.commit()
        router = ModelRoleRouter(registry)
        profile = router.resolve(ModelRole.STRUCTURED_OUTPUT, require_json_schema=True)
    assert profile.model
    assert profile.provider


def test_missing_ocr_raises_configuration_error() -> None:
    with get_session() as session:
        registry = ModelRoleRegistryService(session)
        profiles = [
            ModelProfile(
                id="text-only",
                provider="gemini",
                model="gemini-2.5-flash",
                roles={ModelRole.STRUCTURED_OUTPUT},
            )
        ]
        registry.save_profiles(profiles)
        registry.save_role_assignments([])
        router = ModelRoleRouter(registry)
        with pytest.raises(ConfigurationError, match="ocr"):
            router.resolve(ModelRole.OCR)


def test_explicit_ocr_assignment() -> None:
    with get_session() as session:
        registry = ModelRoleRegistryService(session)
        ocr_profile = ModelProfile(
            id="ocr-model",
            provider="custom",
            model="ocr-v1",
            roles={ModelRole.OCR},
        )
        registry.save_profiles([ocr_profile])
        registry.save_role_assignments(
            [ModelRoleAssignment(role=ModelRole.OCR, profile_id="ocr-model")]
        )
        router = ModelRoleRouter(registry)
        profile = router.resolve(ModelRole.OCR)
    assert profile.id == "ocr-model"


def test_resolve_optional_returns_none_for_unconfigured_ocr() -> None:
    with get_session() as session:
        registry = ModelRoleRegistryService(session)
        registry.save_profiles(
            [
                ModelProfile(
                    id="main",
                    provider="gemini",
                    model="gemini-2.5-flash",
                    roles={ModelRole.STRUCTURED_OUTPUT},
                )
            ]
        )
        registry.save_role_assignments([])
        router = ModelRoleRouter(registry)
        assert router.resolve_optional(ModelRole.OCR) is None

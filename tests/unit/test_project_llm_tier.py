"""Unit tests for project LLM tier (fast / quality)."""

from __future__ import annotations

import pytest
from archium.application.project_llm_tier_service import (
    ProjectLLMTierService,
    model_for_tier,
)
from archium.config.settings import Settings
from archium.domain.project import Project
from archium.domain.project_llm_tier import ProjectLLMTier
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.repositories import ProjectRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import archium.infrastructure.database.models  # noqa: F401

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()
        engine.dispose()


def test_model_for_tier_reads_settings_overrides() -> None:
    settings = Settings(
        llm_model="base-model",
        llm_fast_model="fast-model",
        llm_quality_model="quality-model",
    )
    assert model_for_tier(settings, ProjectLLMTier.FAST) == "fast-model"
    assert model_for_tier(settings, ProjectLLMTier.QUALITY) == "quality-model"


def test_model_for_tier_rejects_gemini_override_on_deepseek_endpoint() -> None:
    settings = Settings(
        llm_provider="deepseek",
        llm_base_url="https://api.deepseek.com/v1",
        llm_model="deepseek-v4-flash",
        llm_quality_model="gemini-2.5-pro",
        llm_fast_model="gemini-2.0-flash",
    )
    assert model_for_tier(settings, ProjectLLMTier.QUALITY) == "deepseek-v4-flash"
    assert model_for_tier(settings, ProjectLLMTier.FAST) == "deepseek-v4-flash"


def test_project_tier_persists_and_applies(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="档位测试"))
    service = ProjectLLMTierService(db_session)
    assert service.get_tier(project.id) == ProjectLLMTier.QUALITY
    service.set_tier(project.id, ProjectLLMTier.FAST)
    assert service.get_tier(project.id) == ProjectLLMTier.FAST

    settings = Settings(
        llm_model="base",
        llm_fast_model="flash-x",
        llm_quality_model="pro-x",
    )
    applied = service.apply_to_settings(settings, project.id)
    assert applied.llm_model == "flash-x"

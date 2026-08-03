"""Project LLM tier — map fast/quality onto Settings.llm_model."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.config.settings import Settings
from archium.domain.project_llm_tier import (
    PROJECT_LLM_TIER_KEY,
    TIER_LABELS,
    ProjectLLMTier,
)
from archium.infrastructure.database.user_preference_repository import (
    UserPreferenceRepository,
)


class ProjectLLMTierService:
    """Persist and apply per-project model tier preferences."""

    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._preferences = UserPreferenceRepository(session)

    def get_tier(self, project_id: UUID) -> ProjectLLMTier:
        pref = self._preferences.get_for_project(project_id, PROJECT_LLM_TIER_KEY)
        if pref is None:
            return ProjectLLMTier.QUALITY
        raw = pref.value
        if isinstance(raw, dict):
            raw = raw.get("tier")
        try:
            return ProjectLLMTier(str(raw))
        except ValueError:
            return ProjectLLMTier.QUALITY

    def set_tier(self, project_id: UUID, tier: ProjectLLMTier) -> ProjectLLMTier:
        self._preferences.upsert_for_project(
            project_id,
            PROJECT_LLM_TIER_KEY,
            {"tier": tier.value},
            description="Project LLM model tier (fast concept vs quality)",
        )
        return tier

    def apply_to_settings(self, settings: Settings, project_id: UUID) -> Settings:
        """Return settings with llm_model overridden by project tier."""
        tier = self.get_tier(project_id)
        model = model_for_tier(settings, tier)
        if not model or model == settings.llm_model:
            return settings
        return settings.model_copy(update={"llm_model": model})


def model_for_tier(settings: Settings, tier: ProjectLLMTier) -> str:
    if tier == ProjectLLMTier.FAST:
        return (settings.llm_fast_model or settings.llm_model or "").strip()
    return (settings.llm_quality_model or settings.llm_model or "").strip()


def tier_label(tier: ProjectLLMTier) -> str:
    return TIER_LABELS.get(tier, tier.value)

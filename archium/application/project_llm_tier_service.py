"""Project LLM tier — map fast/quality onto Settings.llm_model."""

from __future__ import annotations

from uuid import UUID

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
        candidate = (settings.llm_fast_model or settings.llm_model or "").strip()
    else:
        candidate = (settings.llm_quality_model or settings.llm_model or "").strip()
    main = (settings.llm_model or "").strip()
    if candidate and _tier_model_compatible(settings, candidate):
        return candidate
    return main


def _tier_model_compatible(settings: Settings, model: str) -> bool:
    """Reject tier overrides that cannot work with the active provider endpoint."""
    model_l = model.lower()
    provider = (getattr(settings, "llm_provider", None) or "").strip().lower()
    base = (settings.llm_base_url or "").strip().lower()
    main = (settings.llm_model or "").strip().lower()

    looks_gemini = "gemini" in model_l or model_l.startswith("models/gemini")
    looks_deepseek = "deepseek" in model_l
    endpoint_deepseek = "deepseek" in provider or "deepseek" in base
    endpoint_gemini = (
        "gemini" in provider
        or "generativelanguage.googleapis.com" in base
        or "googleapis.com" in base
    )
    main_gemini = "gemini" in main
    main_deepseek = "deepseek" in main

    if endpoint_deepseek and looks_gemini:
        return False
    if endpoint_gemini and looks_deepseek:
        return False
    # Profile already switched main model family; keep tier models aligned.
    if main_deepseek and looks_gemini:
        return False
    return not (main_gemini and looks_deepseek)


def tier_label(tier: ProjectLLMTier) -> str:
    return TIER_LABELS.get(tier, tier.value)

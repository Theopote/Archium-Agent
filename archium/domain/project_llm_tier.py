"""Project-scoped LLM model tier — fast concept vs quality competition."""

from __future__ import annotations

from enum import StrEnum


class ProjectLLMTier(StrEnum):
    FAST = "fast"
    QUALITY = "quality"


PROJECT_LLM_TIER_KEY = "archium.project.llm_tier"

TIER_LABELS = {
    ProjectLLMTier.FAST: "快速概念",
    ProjectLLMTier.QUALITY: "高质量竞赛",
}

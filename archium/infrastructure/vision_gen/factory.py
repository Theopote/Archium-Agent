"""Resolve Vision Engine image generator from settings."""

from __future__ import annotations

from archium.config.settings import Settings, get_settings
from archium.infrastructure.vision_gen.base import (
    StubVisionImageGenerator,
    VisionImageGenerator,
)
from archium.infrastructure.vision_gen.openai_compatible import (
    OpenAICompatibleVisionImageGenerator,
)
from archium.logging import get_logger

logger = get_logger(__name__, operation="vision_gen_factory")


def build_vision_image_generator(settings: Settings | None = None) -> VisionImageGenerator:
    """Prefer configured OpenAI-compatible API; otherwise Pillow stub."""
    cfg = settings or get_settings()
    provider = (cfg.vision_image_generation_provider or "stub").strip().lower()
    if provider == "openai_compatible":
        candidate = OpenAICompatibleVisionImageGenerator(cfg)
        if candidate.is_available():
            logger.info("Vision Engine using openai_compatible model=%s", candidate.model)
            return candidate
        logger.info("Vision Engine openai_compatible unavailable; falling back to stub")
    return StubVisionImageGenerator()

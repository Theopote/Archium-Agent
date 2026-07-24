"""Shim: induction screenshot embedding lives in infrastructure.vision."""

from archium.infrastructure.vision.induction_screenshot_embedding import (
    enrich_slide_screenshot_embeddings,
)

__all__ = ["enrich_slide_screenshot_embeddings"]

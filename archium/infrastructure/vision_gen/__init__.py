"""Vision generation adapters."""

from archium.infrastructure.vision_gen.base import (
    GeneratedImageBytes,
    StubVisionImageGenerator,
    VisionImageGenerator,
)
from archium.infrastructure.vision_gen.factory import build_vision_image_generator
from archium.infrastructure.vision_gen.openai_compatible import (
    OpenAICompatibleVisionImageGenerator,
)

__all__ = [
    "GeneratedImageBytes",
    "StubVisionImageGenerator",
    "VisionImageGenerator",
    "OpenAICompatibleVisionImageGenerator",
    "build_vision_image_generator",
]

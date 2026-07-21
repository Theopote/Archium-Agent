"""Scene compiler chain — specialized processors first, generic fallback."""

from archium.application.visual.scene_compilers.base import (
    SceneCompileContext,
    SceneCompileResult,
    SceneCompiler,
)
from archium.application.visual.scene_compilers.chain import (
    SceneCompilerChain,
    default_scene_compilers,
)
from archium.application.visual.scene_compilers.generic import GenericContentCompiler
from archium.application.visual.scene_compilers.specialized import (
    BeforeAfterCompiler,
    DecisionCompiler,
    DrawingFocusCompiler,
    MetricCompiler,
    PhotoEvidenceGridCompiler,
)

__all__ = [
    "BeforeAfterCompiler",
    "DecisionCompiler",
    "DrawingFocusCompiler",
    "GenericContentCompiler",
    "MetricCompiler",
    "PhotoEvidenceGridCompiler",
    "SceneCompileContext",
    "SceneCompileResult",
    "SceneCompiler",
    "SceneCompilerChain",
    "default_scene_compilers",
]

"""Specialized-first SceneCompiler chain with generic fallback."""

from __future__ import annotations

from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.application.visual.scene_compilers.base import (
    SceneCompileContext,
    SceneCompiler,
    SceneCompileResult,
)
from archium.application.visual.scene_compilers.generic import GenericContentCompiler
from archium.application.visual.scene_compilers.specialized import (
    BeforeAfterCompiler,
    DecisionCompiler,
    DrawingFocusCompiler,
    MetricCompiler,
    PhotoEvidenceGridCompiler,
)
from archium.exceptions import WorkflowError


class SceneCompilerChain:
    """Try specialized compilers in order; GenericContentCompiler always last."""

    def __init__(self, compilers: list[SceneCompiler] | None = None) -> None:
        self._compilers = compilers or default_scene_compilers()

    @property
    def compilers(self) -> list[SceneCompiler]:
        return list(self._compilers)

    def compile(self, context: SceneCompileContext) -> SceneCompileResult:
        for compiler in self._compilers:
            if not compiler.supports(context):
                continue
            scene = compiler.compile(context)
            return SceneCompileResult(
                scene=scene,
                compiler_id=compiler.compiler_id,
                semantic_block_type=context.semantic_block_type,
            )
        raise WorkflowError("SceneCompilerChain has no supporting compiler")


def default_scene_compilers(
    *,
    inner: RenderSceneCompiler | None = None,
) -> list[SceneCompiler]:
    """Canonical order: specialized → generic fallback."""
    generic = GenericContentCompiler(inner)
    return [
        DrawingFocusCompiler(generic),
        PhotoEvidenceGridCompiler(generic),
        BeforeAfterCompiler(generic),
        MetricCompiler(generic),
        DecisionCompiler(generic),
        generic,
    ]

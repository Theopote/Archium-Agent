"""Default SceneCompiler wrapping RenderSceneCompiler."""

from __future__ import annotations

from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.application.visual.scene_compilers.base import SceneCompileContext
from archium.domain.visual.render_scene import RenderScene


class GenericContentCompiler:
    """Fallback compiler — always supports; delegates to RenderSceneCompiler."""

    def __init__(self, inner: RenderSceneCompiler | None = None) -> None:
        self._inner = inner or RenderSceneCompiler()

    @property
    def compiler_id(self) -> str:
        return "generic_content"

    def supports(self, context: SceneCompileContext) -> bool:
        _ = context
        return True

    def compile(self, context: SceneCompileContext) -> RenderScene:
        scene = self._inner.compile(
            slide=context.slide,
            layout_plan=context.layout_plan,
            design_system=context.design_system,
            content_bundle=context.content_bundle,
            visual_intent=context.visual_intent,
            art_direction=context.art_direction,
            reference_style=context.reference_style,
            presentation_id=context.presentation_id,
        )
        warnings = list(scene.warnings)
        tag = f"scene_compiler:{self.compiler_id}"
        if tag not in warnings:
            warnings.append(tag)
        return scene.model_copy(update={"warnings": warnings})

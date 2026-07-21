"""Specialized SceneCompilers — selected by SemanticBlockType / schema / intent."""

from __future__ import annotations

from archium.application.visual.scene_compilers.base import SceneCompileContext
from archium.application.visual.scene_compilers.generic import GenericContentCompiler
from archium.domain.visual.render_scene import DrawingNode, RenderScene
from archium.domain.visual.semantic_block import SemanticBlockType


class _SpecializedCompilerBase:
    """Compile via generic path, then apply light block-specific adjustments."""

    block_type: SemanticBlockType
    compiler_id: str

    def __init__(self, generic: GenericContentCompiler | None = None) -> None:
        self._generic = generic or GenericContentCompiler()

    def supports(self, context: SceneCompileContext) -> bool:
        return context.semantic_block_type == self.block_type

    def compile(self, context: SceneCompileContext) -> RenderScene:
        scene = self._generic.compile(context)
        scene = self._specialize(scene, context)
        warnings = [w for w in scene.warnings if not w.startswith("scene_compiler:")]
        warnings.append(f"scene_compiler:{self.compiler_id}")
        return scene.model_copy(update={"warnings": warnings})

    def _specialize(self, scene: RenderScene, context: SceneCompileContext) -> RenderScene:
        _ = context
        return scene


class DrawingFocusCompiler(_SpecializedCompilerBase):
    block_type = SemanticBlockType.DRAWING_FOCUS
    compiler_id = "drawing_focus"

    def _specialize(self, scene: RenderScene, context: SceneCompileContext) -> RenderScene:
        _ = context
        nodes = []
        for node in scene.nodes:
            if isinstance(node, DrawingNode):
                nodes.append(
                    node.model_copy(
                        update={
                            "fit_mode": "contain",
                            "semantic_role": node.semantic_role or "drawing",
                        }
                    )
                )
            else:
                nodes.append(node)
        return scene.model_copy(update={"nodes": nodes})


class PhotoEvidenceGridCompiler(_SpecializedCompilerBase):
    block_type = SemanticBlockType.PHOTO_EVIDENCE_GRID
    compiler_id = "photo_evidence_grid"


class BeforeAfterCompiler(_SpecializedCompilerBase):
    block_type = SemanticBlockType.BEFORE_AFTER
    compiler_id = "before_after"


class MetricCompiler(_SpecializedCompilerBase):
    block_type = SemanticBlockType.METRIC
    compiler_id = "metric"


class DecisionCompiler(_SpecializedCompilerBase):
    block_type = SemanticBlockType.DECISION
    compiler_id = "decision"

    def supports(self, context: SceneCompileContext) -> bool:
        if context.semantic_block_type == SemanticBlockType.DECISION:
            return True
        schema = context.content_schema
        if schema is None:
            return False
        return any(req.role.value == "decision_request" for req in schema.required_content)

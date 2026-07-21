"""Scene compiler protocol and compile context.

Specialized compilers first, generic fallback — selected by
``ArchitecturalContentSchema`` / ``SemanticBlockType`` / ``VisualIntent``,
not by JSON shape or magic strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from archium.domain.reference_style import ReferenceStyleProfile
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene
from archium.domain.visual.semantic_block import (
    SemanticBlockType,
    resolve_semantic_block_type,
)
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle


@dataclass(frozen=True)
class SceneCompileContext:
    """Inputs for one page's RenderScene compilation."""

    slide: SlideSpec
    layout_plan: LayoutPlan
    design_system: DesignSystem
    content_bundle: SlideContentBundle = field(default_factory=SlideContentBundle)
    visual_intent: VisualIntent | None = None
    content_schema: ArchitecturalContentSchema | None = None
    art_direction: ArtDirection | None = None
    reference_style: ReferenceStyleProfile | None = None
    presentation_id: UUID | None = None

    @property
    def semantic_block_type(self) -> SemanticBlockType:
        return resolve_semantic_block_type(
            schema=self.content_schema,
            visual_intent=self.visual_intent,
            layout_plan=self.layout_plan,
        )


@dataclass(frozen=True)
class SceneCompileResult:
    scene: RenderScene
    compiler_id: str
    semantic_block_type: SemanticBlockType


class SceneCompiler(Protocol):
    """One specialized (or generic) page compiler in the chain."""

    @property
    def compiler_id(self) -> str: ...

    def supports(self, context: SceneCompileContext) -> bool: ...

    def compile(self, context: SceneCompileContext) -> RenderScene: ...

"""Unit tests for SemanticBlockType resolution and SceneCompilerChain."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.scene_compilers import (
    DrawingFocusCompiler,
    GenericContentCompiler,
    SceneCompileContext,
    SceneCompilerChain,
    default_scene_compilers,
)
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    ContentRequirement,
    ContentRole,
)
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import LayoutFamily, VisualContentType
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.semantic_block import (
    SemanticBlockType,
    resolve_semantic_block_type,
)
from archium.domain.visual.template_induction import ArchitecturalContentType
from archium.domain.visual.visual_intent import VisualIntent


def _slide() -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="标题",
        message="核心观点",
    )


def _plan(*, family: LayoutFamily = LayoutFamily.TEXTUAL_ARGUMENT) -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        layout_family=family,
        layout_variant="default",
        page_width=10.0,
        page_height=5.625,
        elements=[],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )


def _intent(*, content: VisualContentType) -> VisualIntent:
    return VisualIntent(
        slide_id=uuid4(),
        communication_goal="说明",
        audience_takeaway="记住要点",
        visual_priority="主图",
        dominant_content_type=content,
    )


def _schema(
    *,
    content_type: ArchitecturalContentType,
    required_content: list[ContentRequirement] | None = None,
) -> ArchitecturalContentSchema:
    return ArchitecturalContentSchema(
        name="schema",
        page_purpose="测试页目的",
        content_type=content_type,
        required_content=list(required_content or []),
    )


def test_resolve_block_type_prefers_schema() -> None:
    schema = _schema(content_type=ArchitecturalContentType.DRAWING_FOCUS)
    intent = _intent(content=VisualContentType.METRICS)
    plan = _plan(family=LayoutFamily.METRIC_DASHBOARD)
    assert (
        resolve_semantic_block_type(schema=schema, visual_intent=intent, layout_plan=plan)
        == SemanticBlockType.DRAWING_FOCUS
    )


def test_resolve_block_type_from_visual_intent() -> None:
    assert (
        resolve_semantic_block_type(
            visual_intent=_intent(content=VisualContentType.PHOTO_EVIDENCE)
        )
        == SemanticBlockType.PHOTO_EVIDENCE_GRID
    )


def test_resolve_block_type_from_layout_family() -> None:
    assert (
        resolve_semantic_block_type(layout_plan=_plan(family=LayoutFamily.COMPARATIVE_MATRIX))
        == SemanticBlockType.BEFORE_AFTER
    )


def test_chain_order_specialized_before_generic() -> None:
    ids = [c.compiler_id for c in default_scene_compilers()]
    assert ids[-1] == "generic_content"
    assert ids.index("drawing_focus") < ids.index("generic_content")
    assert ids.index("decision") < ids.index("generic_content")


def test_chain_selects_drawing_focus_compiler() -> None:
    chain = SceneCompilerChain()
    context = SceneCompileContext(
        slide=_slide(),
        layout_plan=_plan(family=LayoutFamily.DRAWING_FOCUS),
        design_system=default_presentation_design_system(),
        content_schema=_schema(content_type=ArchitecturalContentType.DRAWING_FOCUS),
    )
    result = chain.compile(context)
    assert result.compiler_id == "drawing_focus"
    assert result.semantic_block_type == SemanticBlockType.DRAWING_FOCUS
    assert any("scene_compiler:drawing_focus" in w for w in result.scene.warnings)


def test_chain_falls_back_to_generic() -> None:
    chain = SceneCompilerChain()
    context = SceneCompileContext(
        slide=_slide(),
        layout_plan=_plan(family=LayoutFamily.TEXTUAL_ARGUMENT),
        design_system=default_presentation_design_system(),
    )
    result = chain.compile(context)
    assert result.compiler_id == "generic_content"
    assert result.semantic_block_type == SemanticBlockType.GENERIC


def test_decision_compiler_supports_decision_request_role() -> None:
    chain = SceneCompilerChain()
    schema = _schema(
        content_type=ArchitecturalContentType.TEXT_ARGUMENT,
        required_content=[
            ContentRequirement(role=ContentRole.DECISION_REQUEST, required=True),
        ],
    )
    context = SceneCompileContext(
        slide=_slide(),
        layout_plan=_plan(),
        design_system=default_presentation_design_system(),
        content_schema=schema,
    )
    decision = next(c for c in chain.compilers if c.compiler_id == "decision")
    assert decision.supports(context) is True
    result = chain.compile(context)
    assert result.compiler_id == "decision"


def test_drawing_focus_compiler_supports_only_matching_block() -> None:
    compiler = DrawingFocusCompiler(GenericContentCompiler())
    matching = SceneCompileContext(
        slide=_slide(),
        layout_plan=_plan(family=LayoutFamily.DRAWING_FOCUS),
        design_system=default_presentation_design_system(),
    )
    other = SceneCompileContext(
        slide=_slide(),
        layout_plan=_plan(family=LayoutFamily.TEXTUAL_ARGUMENT),
        design_system=default_presentation_design_system(),
    )
    assert compiler.supports(matching) is True
    assert compiler.supports(other) is False

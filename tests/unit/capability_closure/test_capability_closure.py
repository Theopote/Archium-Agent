"""Tests for Scene Repair, Deck Coherence, Context Budget, and co-plan warnings."""

from __future__ import annotations

from uuid import uuid4

from archium.application.context_budget_manager import ContextBudgetManager
from archium.application.deck_coherence_qa_service import DeckCoherenceQAService
from archium.application.outline_templates import renovation_outline_sections
from archium.application.visual.outline_template_co_planning_service import (
    OutlineTemplateCoPlanningService,
)
from archium.application.visual.scene_repair_service import SceneRepairService
from archium.domain.visual.scene_repair import SceneRepairApplyMode
from archium.application.visual.schema_usage_validator import validate_schema_length_bounds
from archium.domain.outline import OutlinePlan
from archium.domain.presentation_manuscript import ManuscriptFact
from archium.domain.slide import SlideSpec
from archium.domain.slide_generation_context import SlideGenerationContext
from archium.domain.slide_semantic_qa import SlideSemanticFinding
from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    ContentRequirement,
    ContentRole,
)
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
)


def _text_node(*, node_id: str, text: str, overflow: str = "error") -> TextNode:
    return TextNode(
        id=node_id,
        x=0.5,
        y=1.0,
        width=2.0,
        height=0.4,
        z_index=1,
        text=text,
        font_family="Arial",
        font_size=12,
        color="#000000",
        line_height=1.2,
        overflow_policy=overflow,
    )


def test_scene_repair_shortens_overflow_text() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            _text_node(
                node_id="body_1",
                text="这是一段非常长的说明文字" * 20,
            )
        ],
    )
    finding = SlideSemanticFinding(
        check_code=SceneSemanticCheckCode.TEXT_OVERFLOW,
        slide_order=0,
        slide_id=scene.slide_id,
        severity="medium",
        title="overflow",
        description="overflow",
        evidence_refs=["body_1"],
    )
    result = SceneRepairService().repair_scene(
        scene,
        [finding],
        apply_mode=SceneRepairApplyMode.ALL_REPAIRABLE,
    )
    text_node = next(node for node in result.scene.nodes if isinstance(node, TextNode))
    assert len(text_node.text) < len("这是一段非常长的说明文字" * 20)
    assert result.applied_count >= 1


def test_deck_coherence_detects_duplicate_messages() -> None:
    presentation_id = uuid4()
    message = "人车混行是当前院区最核心的交通组织问题，需要优先治理。"
    slides = [
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="problem",
            order=0,
            title="现状一",
            message=message,
        ),
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="problem",
            order=1,
            title="现状二",
            message=message,
        ),
    ]
    report = DeckCoherenceQAService().evaluate(slides)
    assert any("DUPLICATE_MESSAGE" in finding.rule_code for finding in report.findings)


def test_context_budget_manager_trims_large_context() -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="标题",
        message="核心观点",
    )
    context = SlideGenerationContext(
        slide_spec=slide,
        section_summary="章节背景" * 200,
        verified_facts=[
            ManuscriptFact(
                statement=f"事实 {index}",
                source_id=f"f-{index}",
                verified=True,
            )
            for index in range(20)
        ],
    )
    manager = ContextBudgetManager({"slide_generate": 400})
    trimmed = manager.trim_slide_context(context, stage="slide_generate")
    assert trimmed.estimated_char_count() <= 450


def test_co_plan_emits_capacity_warnings() -> None:
    sections = renovation_outline_sections()[:1]
    problem = sections[0].model_copy(
        update={
            "estimated_slide_count": 3,
            "evidence_requirements": ["证据1", "证据2", "证据3", "证据4", "证据5"],
            "key_message": "X" * 300,
        }
    )
    outline = OutlinePlan(
        presentation_id=uuid4(),
        title="改造汇报",
        thesis="t",
        audience="a",
        purpose="p",
        sections=[problem],
    )
    schema = ArchitecturalContentSchema(
        name="content/photo",
        cluster_id="c1",
        representative_slide_id="slide_001",
        content_type=ArchitecturalContentType.PHOTO_ANALYSIS,
        functional_type=FunctionalSlideType.CONTENT,
        page_purpose="证明现场问题",
        max_text_length=120,
        evidence_items=[
            ContentRequirement(
                role=ContentRole.EVIDENCE,
                required=True,
                min_count=1,
                max_count=2,
            )
        ],
    )
    co_plan = OutlineTemplateCoPlanningService().plan(outline, [schema])
    assert co_plan.capacity_warnings


def test_validate_schema_length_bounds_blocks_invalid_ranges() -> None:
    schema = ArchitecturalContentSchema(
        name="content/bad",
        page_purpose="测试",
        min_text_length=500,
        max_text_length=100,
    )
    blockers = validate_schema_length_bounds(schema)
    assert blockers

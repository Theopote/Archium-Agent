"""Unit tests for archetype-aware layout generator variants."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.visual_grammar_recognition import recognize_page_archetype
from archium.domain.citation import Citation
from archium.domain.enums import SlideType, VisualType
from archium.domain.slide import SlideSpec, SlideVisualRequirement
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import (
    LayoutElementRole,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.visual_grammar import PageArchetype
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.generators.base import LayoutGeneratorContext, content_from_slide
from archium.infrastructure.layout.layout_solver import LayoutSolver

DOCUMENT_ID = uuid4()


def _intent(
    *,
    slide_id=None,
    archetype: PageArchetype,
    content_type: VisualContentType,
    hero: str | None = None,
    supporting: list[str] | None = None,
) -> VisualIntent:
    return VisualIntent(
        slide_id=slide_id or uuid4(),
        presentation_id=uuid4(),
        page_archetype=archetype,
        communication_goal="test",
        audience_takeaway="test",
        visual_priority="hero",
        dominant_content_type=content_type,
        hero_asset_id=uuid4() if hero == "set" else None,
        supporting_asset_ids=[uuid4() for _ in range(2)],
        preferred_layout_families=[LayoutFamily.EVIDENCE_BOARD],
    )


def _generate(
    slide: SlideSpec,
    intent: VisualIntent,
    family: LayoutFamily,
    variant: str,
):
    design = default_presentation_design_system()
    hero_id = intent.hero_asset_id
    if hero_id is not None:
        intent = intent.model_copy(update={"hero_asset_id": hero_id})
    content = content_from_slide(slide, intent)
    if content.hero_asset_ref is None and slide.visual_requirements:
        primary = slide.visual_requirements[0].primary_asset_id
        if primary is not None:
            content = content.model_copy(update={"hero_asset_ref": str(primary)})
    if not content.supporting_asset_refs and len(slide.visual_requirements) > 1:
        content = content.model_copy(
            update={
                "supporting_asset_refs": [
                    str(req.primary_asset_id)
                    for req in slide.visual_requirements[1:]
                    if req.primary_asset_id is not None
                ]
            }
        )
    context = LayoutGeneratorContext(
        slide=slide,
        visual_intent=intent,
        art_direction=None,
        design_system=design,
        content=content,
        variant=variant,
    )
    plan = LayoutSolver().generate(family, context)
    report = LayoutValidationService().validate(plan, design)
    return plan, report


def test_diagnosis_split_layout_roles() -> None:
    photos = [uuid4() for _ in range(2)]
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="problem",
        order=3,
        title="现状问题诊断",
        message="结构老化与空间不足并存，需优先解决安全与流线。",
        slide_type=SlideType.IMAGE,
        key_points=["结构老化", "空间不足", "流线混乱"],
        visual_requirements=[
            SlideVisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="现场1",
                preferred_asset_ids=[photos[0]],
            ),
            SlideVisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="现场2",
                preferred_asset_ids=[photos[1]],
            ),
        ],
    )
    recognition = recognize_page_archetype(slide)
    assert recognition.archetype == PageArchetype.SITE_PROBLEM_DIAGNOSIS

    intent = _intent(
        archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS,
        content_type=VisualContentType.PHOTO_EVIDENCE,
    )
    plan, report = _generate(
        slide,
        intent,
        LayoutFamily.EVIDENCE_BOARD,
        "diagnosis_split",
    )
    assert plan.layout_variant == "diagnosis_split"
    assert plan.balance_strategy == "diagnosis_split"
    roles = {element.role for element in plan.elements}
    assert LayoutElementRole.SUPPORTING_VISUAL in roles
    assert LayoutElementRole.BODY_TEXT in roles
    assert LayoutElementRole.LEAD_STATEMENT in roles
    assert any(element.id == "problem_tags" for element in plan.elements)
    assert report.valid


def test_narrative_opening_hybrid_layout() -> None:
    photo_id = uuid4()
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="opening",
        order=0,
        title="老院区更新汇报开篇",
        message="历史院区面临流线交叉与空间矛盾，更新目标是可持续运营。",
        key_points=["流线交叉拥堵", "后勤空间老化", "可持续运营"],
        visual_requirements=[
            SlideVisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="历史院区照片",
                preferred_asset_ids=[photo_id],
            ),
        ],
    )
    recognition = recognize_page_archetype(slide)
    assert recognition.archetype == PageArchetype.NARRATIVE_OPENING

    intent = VisualIntent(
        slide_id=slide.id,
        presentation_id=slide.presentation_id,
        page_archetype=PageArchetype.NARRATIVE_OPENING,
        communication_goal="建立叙事张力",
        audience_takeaway=slide.message,
        visual_priority="photo",
        dominant_content_type=VisualContentType.MIXED,
        hero_asset_id=photo_id,
        preferred_layout_families=[LayoutFamily.HYBRID_CANVAS],
    )
    plan, report = _generate(
        slide, intent, LayoutFamily.HYBRID_CANVAS, "narrative_opening"
    )
    assert plan.layout_variant == "narrative_opening"
    assert plan.balance_strategy == "narrative_opening_split"
    hero = next(el for el in plan.elements if el.id == "historic_photo")
    assert hero.role == LayoutElementRole.HERO_VISUAL
    assert hero.content_ref == str(photo_id)
    assert {el.id for el in plan.elements} >= {
        "historic_photo",
        "problem_tension",
        "spatial_contradiction",
        "renewal_goal",
    }
    assert plan.reading_order[:2] == ["title", "historic_photo"]
    assert report.valid


def test_narrative_opening_placeholder_when_photo_missing() -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="opening",
        order=0,
        title="开篇：更新课题",
        message="历史矛盾与更新目标并置。",
        key_points=["现状矛盾", "空间问题", "更新目标"],
        page_archetype=PageArchetype.NARRATIVE_OPENING,
        visual_requirements=[
            SlideVisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="[grammar:historic_or_context_photo] 历史照片",
            ),
        ],
    )
    intent = VisualIntent(
        slide_id=slide.id,
        presentation_id=slide.presentation_id,
        page_archetype=PageArchetype.NARRATIVE_OPENING,
        communication_goal="开篇",
        audience_takeaway=slide.message,
        visual_priority="photo",
        dominant_content_type=VisualContentType.MIXED,
        preferred_layout_families=[LayoutFamily.HYBRID_CANVAS],
    )
    plan, report = _generate(
        slide, intent, LayoutFamily.HYBRID_CANVAS, "narrative_opening"
    )
    hero = next(el for el in plan.elements if el.id == "historic_photo")
    assert hero.content_ref == "grammar:historic_or_context_photo"
    assert report.valid


def test_site_context_hybrid_layout() -> None:
    map_id = uuid4()
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="context",
        order=1,
        title="区位与交通分析",
        message="基地位于轨道站点 800m 辐射圈，主干道可达性良好。",
        key_points=["地铁 800m", "主干道贯通", "服务半径 500m"],
        visual_requirements=[
            SlideVisualRequirement(
                type=VisualType.MAP,
                description="区位地图",
                preferred_asset_ids=[map_id],
            ),
        ],
        source_citations=[
            Citation(document_id=DOCUMENT_ID, document_name="区位分析.pdf", page_number=2),
        ],
    )
    recognition = recognize_page_archetype(slide)
    assert recognition.archetype == PageArchetype.SITE_CONTEXT_ANALYSIS

    intent = VisualIntent(
        slide_id=slide.id,
        presentation_id=slide.presentation_id,
        page_archetype=PageArchetype.SITE_CONTEXT_ANALYSIS,
        communication_goal="理解区位",
        audience_takeaway=slide.message,
        visual_priority="map",
        dominant_content_type=VisualContentType.SITE_PLAN,
        hero_asset_id=map_id,
        preferred_layout_families=[LayoutFamily.HYBRID_CANVAS],
    )
    plan, report = _generate(slide, intent, LayoutFamily.HYBRID_CANVAS, "site_context")
    assert plan.layout_variant == "site_context"
    assert plan.balance_strategy == "site_context_split"
    assert any(element.id == "hero" for element in plan.elements)
    assert any(element.id == "conclusion" for element in plan.elements)
    assert report.valid


def test_before_after_variant_two_columns() -> None:
    before_id, after_id = uuid4(), uuid4()
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="transform",
        order=2,
        title="改造前后对比",
        message="改造后公共界面与可达性显著提升。",
        slide_type=SlideType.COMPARISON,
        visual_requirements=[
            SlideVisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="改造前",
                preferred_asset_ids=[before_id],
            ),
            SlideVisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="改造后",
                preferred_asset_ids=[after_id],
            ),
        ],
    )
    intent = VisualIntent(
        slide_id=slide.id,
        presentation_id=slide.presentation_id,
        page_archetype=PageArchetype.BEFORE_AFTER_TRANSFORMATION,
        communication_goal="展示变化",
        audience_takeaway=slide.message,
        visual_priority="cases",
        dominant_content_type=VisualContentType.COMPARISON,
        hero_asset_id=before_id,
        supporting_asset_ids=[after_id],
        preferred_layout_families=[LayoutFamily.COMPARATIVE_MATRIX],
    )
    plan, _report = _generate(
        slide, intent, LayoutFamily.COMPARATIVE_MATRIX, "before_after"
    )
    assert plan.layout_variant == "before_after"
    assert plan.balance_strategy == "before_after"
    visuals = [el for el in plan.elements if el.role == LayoutElementRole.SUPPORTING_VISUAL]
    assert len(visuals) == 2
    labels = [el for el in plan.elements if el.id.startswith("case_label_")]
    assert len(labels) == 2
    assert "改造前" in labels[0].text_content or "改造" in labels[0].text_content


def test_strategy_concept_variant() -> None:
    concept_id = uuid4()
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="strategy",
        order=3,
        title="设计策略与原则",
        message="以开放院落串联历史肌理与现代功能。",
        key_points=["开放公共", "历史肌理", "现代功能", "空间渗透", "慢行系统"],
        visual_requirements=[
            SlideVisualRequirement(
                type=VisualType.DIAGRAM,
                description="概念示意",
                preferred_asset_ids=[concept_id],
            ),
        ],
    )
    intent = VisualIntent(
        slide_id=slide.id,
        presentation_id=slide.presentation_id,
        page_archetype=PageArchetype.DESIGN_STRATEGY,
        communication_goal="传达策略",
        audience_takeaway=slide.message,
        visual_priority="concept",
        dominant_content_type=VisualContentType.TEXT_ARGUMENT,
        hero_asset_id=concept_id,
        preferred_layout_families=[LayoutFamily.STRATEGY_CARDS],
    )
    plan, report = _generate(
        slide, intent, LayoutFamily.STRATEGY_CARDS, "strategy_concept"
    )
    assert plan.layout_variant == "strategy_concept"
    assert any(element.id == "concept" for element in plan.elements)
    assert any(element.id == "spatial_change" for element in plan.elements)
    cards = [el for el in plan.elements if el.id.startswith("card_")]
    assert len(cards) == 3
    assert report.valid


def test_drawing_with_annotations_variant() -> None:
    drawing_id = uuid4()
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="context",
        order=1,
        title="区位分析图",
        message="轨道站点与主干道构成双轴牵引。",
        key_points=["地铁站点", "主干道", "服务半径", "开放空间"],
        visual_requirements=[
            SlideVisualRequirement(
                type=VisualType.SITE_PLAN,
                description="区位总图",
                preferred_asset_ids=[drawing_id],
            ),
        ],
    )
    intent = VisualIntent(
        slide_id=slide.id,
        presentation_id=slide.presentation_id,
        page_archetype=PageArchetype.SITE_CONTEXT_ANALYSIS,
        communication_goal="读图",
        audience_takeaway=slide.message,
        visual_priority="drawing",
        dominant_content_type=VisualContentType.SITE_PLAN,
        hero_asset_id=drawing_id,
        preferred_layout_families=[LayoutFamily.DRAWING_FOCUS],
    )
    plan, report = _generate(
        slide, intent, LayoutFamily.DRAWING_FOCUS, "drawing_with_annotations"
    )
    assert plan.layout_variant == "drawing_with_annotations"
    assert plan.balance_strategy == "drawing_annotated"
    annotations = [
        el for el in plan.elements if el.role == LayoutElementRole.ANNOTATION
    ]
    assert len(annotations) >= 2
    assert report.valid

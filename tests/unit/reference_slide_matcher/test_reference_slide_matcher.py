"""Tests for ReferenceSlideMatcher (WP I)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.visual.induction_architectural_template_publisher import (
    InductionArchitecturalTemplatePublisher,
)
from archium.application.visual.reference_slide_matcher import ReferenceSlideMatcher
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplatePageType,
    TemplateSlot,
    TemplateSlotRole,
    TemplateStatus,
)
from archium.domain.visual.reference_slide_matching import DeckContext
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
    TemplateInductionStatus,
)

from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


def _sample_template() -> ArchitecturalTemplate:
    schema_photo = ArchitecturalContentSchema(
        name="content/photo_analysis",
        cluster_id="c1",
        representative_slide_id="slide_002",
        content_type=ArchitecturalContentType.PHOTO_ANALYSIS,
        functional_type=FunctionalSlideType.CONTENT,
        page_purpose="证明现场问题",
        supports_drawing=False,
        min_asset_count=2,
        max_asset_count=4,
        min_text_length=20,
        max_text_length=500,
        forbidden_asset_origins=["reference_template"],
    )
    schema_draw = ArchitecturalContentSchema(
        name="content/drawing_focus",
        cluster_id="c2",
        representative_slide_id="slide_003",
        content_type=ArchitecturalContentType.DRAWING_FOCUS,
        functional_type=FunctionalSlideType.CONTENT,
        page_purpose="解释总平面",
        supports_drawing=True,
        min_asset_count=1,
        max_asset_count=2,
        forbidden_asset_origins=["reference_template"],
    )
    layout_photo = ArchitecturalTemplateLayout(
        name="photo",
        page_index=0,
        page_type=TemplatePageType.PHOTO_GRID,
        suitable_content_types=["photo_analysis"],
        slots=[
            TemplateSlot(
                id="s1",
                role=TemplateSlotRole.TITLE,
                x=0.5,
                y=0.3,
                width=8,
                height=0.6,
            )
        ],
        supports_photo=True,
        content_schema_id=schema_photo.id,
        representative_slide_id="slide_002",
        cluster_id="c1",
    )
    layout_draw = ArchitecturalTemplateLayout(
        name="drawing",
        page_index=1,
        page_type=TemplatePageType.DRAWING_FOCUS,
        suitable_content_types=["drawing_focus"],
        slots=[
            TemplateSlot(
                id="s1",
                role=TemplateSlotRole.DRAWING,
                x=1,
                y=1,
                width=6,
                height=4,
            )
        ],
        supports_drawing=True,
        content_schema_id=schema_draw.id,
        representative_slide_id="slide_003",
        cluster_id="c2",
    )
    return ArchitecturalTemplate(
        id=uuid4(),
        name="test-template",
        layouts=[layout_photo, layout_draw],
        content_schemas=[schema_photo, schema_draw],
        status=TemplateStatus.PUBLISHED,
    )


def test_rank_prefers_schema_linked_layout() -> None:
    template = _sample_template()
    schema = template.content_schemas[0]
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="problem",
        order=0,
        title="入口交通问题",
        message="现场照片显示入口区域人车冲突严重，需要优化流线组织。",
        slide_type=SlideType.IMAGE,
    )
    assets = [
        Asset(
            id=uuid4(),
            project_id=uuid4(),
            filename="a.jpg",
            path="project://a.jpg",
            asset_type=AssetType.PHOTO,
        ),
        Asset(
            id=uuid4(),
            project_id=uuid4(),
            filename="b.jpg",
            path="project://b.jpg",
            asset_type=AssetType.PHOTO,
        ),
    ]
    results = ReferenceSlideMatcher().rank(
        slide_spec=slide,
        content_schema=schema,
        assets=assets,
        template=template,
    )
    assert results
    assert results[0].candidate_kind == "recommended"
    assert results[0].layout_id == template.layouts[0].id
    assert results[0].representative_slide_id == "slide_002"


def test_rank_penalizes_reused_layout() -> None:
    template = _sample_template()
    schema = template.content_schemas[0]
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="problem",
        order=1,
        title="重复页",
        message="第二页仍讨论现场问题。",
        slide_type=SlideType.IMAGE,
    )
    ctx = DeckContext(
        used_layout_ids=[template.layouts[0].id],
        used_representative_slide_ids=["slide_002"],
    )
    results = ReferenceSlideMatcher().rank(
        slide_spec=slide,
        content_schema=schema,
        assets=[],
        template=template,
        deck_context=ctx,
    )
    assert any("reused" in " ".join(c.reasons) for c in results if c.layout_id)


def test_rank_includes_free_composition_when_no_layouts() -> None:
    template = _sample_template()
    template = template.model_copy(update={"layouts": []})
    schema = template.content_schemas[0]
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="misc",
        order=0,
        title="杂项",
        message="短",
        slide_type=SlideType.CONTENT,
    )
    results = ReferenceSlideMatcher().rank(
        slide_spec=slide,
        content_schema=schema,
        assets=[],
        template=template,
        limit=2,
    )
    assert any(c.candidate_kind == "free_composition" for c in results)


def test_matcher_works_on_materialized_induction_template(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    from archium.application.visual.template_induction_service import TemplateInductionService

    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
    result.induction.status = TemplateInductionStatus.PUBLISHED
    template = InductionArchitecturalTemplatePublisher().build(
        induction=result.induction,
        presentation=result.presentation,
        schemas=list(result.schemas),
        workspace=result.workspace,
    )
    schema = template.content_schemas[0]
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="测试页",
        message="用于验证归纳模板上的参考页匹配。",
        slide_type=SlideType.CONTENT,
    )
    ranked = ReferenceSlideMatcher().rank(
        slide_spec=slide,
        content_schema=schema,
        assets=[],
        template=template,
    )
    assert ranked
    assert ranked[0].template_id == template.id

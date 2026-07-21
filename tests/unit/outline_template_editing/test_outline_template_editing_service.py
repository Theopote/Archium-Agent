"""Integration tests for co-plan template_editing route execution."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from archium.application.outline_templates import renovation_outline_sections
from archium.application.visual.induction_architectural_template_publisher import (
    InductionArchitecturalTemplatePublisher,
)
from archium.application.visual.outline_template_co_planning_service import (
    OutlineTemplateCoPlanningService,
)
from archium.application.visual.outline_template_editing_service import (
    OutlineTemplateEditingService,
)
from archium.application.visual.semantic_content_plan import schema_uses_semantic_contract
from archium.application.visual.template_induction_service import TemplateInductionService
from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.outline import OutlinePlan
from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema
from archium.domain.visual.template_induction import TemplateInductionStatus
from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


def _outline() -> OutlinePlan:
    sections = renovation_outline_sections()[:2]
    return OutlinePlan(
        presentation_id=uuid4(),
        title="改造汇报",
        thesis="以证据支持改造决策",
        audience="主管部门",
        purpose="汇报改造方案",
        sections=sections,
        target_slide_count=max(1, sum(s.estimated_slide_count for s in sections)),
    )


def test_execute_generates_scenes_for_template_editing_pages(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    run = service.induce(pptx, capture_screenshots=False)
    run.induction.status = TemplateInductionStatus.PUBLISHED
    schemas = list(run.schemas)
    template = InductionArchitecturalTemplatePublisher().build(
        induction=run.induction,
        presentation=run.presentation,
        schemas=schemas,
        workspace=run.workspace,
    )
    outline = _outline()
    co_plan = OutlineTemplateCoPlanningService().plan(
        outline,
        schemas,
        template=template,
        induction_id=run.induction.id,
    )
    assert co_plan.template_editing_page_ids

    project_asset = Asset(
        id=uuid4(),
        project_id=uuid4(),
        filename="site.jpg",
        path="project://site.jpg",
        asset_type=AssetType.PHOTO,
    )
    batch, updated = OutlineTemplateEditingService().execute(
        co_plan=co_plan,
        outline=outline,
        presentation=run.presentation,
        schemas=schemas,
        template=template,
        assets=[project_asset],
        workspace=tmp_path / "edit_out",
    )

    assert batch.generated_count >= 1
    assert batch.failed_count == 0
    generated_pages = [p for p in updated.page_plans if p.edit_scene_status == "generated"]
    assert generated_pages
    generated_results = [r for r in batch.page_results if r.status == "generated"]
    schema_by_id = {schema.id: schema for schema in schemas}
    for result in generated_results:
        schema = schema_by_id.get(result.schema_id or "")
        if schema is not None and schema_uses_semantic_contract(schema):
            assert result.semantic_contract_active
    for page in generated_pages:
        assert page.edit_scene_relative_path
        scene_path = (tmp_path / "edit_out") / page.edit_scene_relative_path
        assert scene_path.is_file()
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        assert scene["nodes"]
        assert "参考" not in json.dumps(scene, ensure_ascii=False)


def test_template_induction_service_execute_co_plan_template_editing(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    workspace = tmp_path / "workspace"
    service.workspace_root = lambda induction_id: workspace  # type: ignore[method-assign]
    run = service.induce(pptx, capture_screenshots=False)
    run.induction.status = TemplateInductionStatus.PUBLISHED
    schemas = list(run.schemas)
    InductionArchitecturalTemplatePublisher().publish_to_workspace(
        induction=run.induction,
        presentation=run.presentation,
        schemas=schemas,
        workspace=workspace,
    )
    template = service.load_architectural_template(workspace)
    assert template is not None

    outline = _outline()
    co_plan = service.co_plan_outline(
        run.induction,
        outline,
        schemas=schemas,
        template=template,
        workspace=workspace,
    )
    assert (workspace / "outline_plan.json").is_file()

    batch, updated = service.execute_co_plan_template_editing(
        run.induction,
        outline,
        co_plan,
        run.presentation,
        template=template,
        workspace=workspace,
    )
    assert batch.generated_count >= 1
    assert (workspace / "outline_template_editing_batch.json").is_file()
    assert any(p.edit_scene_status == "generated" for p in updated.page_plans)


def test_execute_skips_when_reference_slide_missing() -> None:
    from archium.domain.outline import OutlineSection
    from archium.domain.visual.architectural_template import (
        ArchitecturalTemplate,
        ArchitecturalTemplateLayout,
        TemplatePageType,
        TemplateStatus,
    )
    from archium.domain.visual.reference_slide import ReferencePresentation
    from archium.domain.visual.template_induction import (
        ArchitecturalContentType,
        FunctionalSlideType,
        OutlineTemplateCompatibility,
        OutlineTemplateCoPlan,
    )

    schema = ArchitecturalContentSchema(
        name="content/photo",
        cluster_id="c1",
        representative_slide_id="missing_slide",
        content_type=ArchitecturalContentType.PHOTO_ANALYSIS,
        functional_type=FunctionalSlideType.CONTENT,
        page_purpose="证明现场问题",
    )
    layout = ArchitecturalTemplateLayout(
        name="photo",
        page_index=0,
        page_type=TemplatePageType.PHOTO_GRID,
        content_schema_id=schema.id,
        representative_slide_id="missing_slide",
        cluster_id="c1",
    )
    template = ArchitecturalTemplate(
        id=uuid4(),
        name="t",
        layouts=[layout],
        content_schemas=[schema],
        status=TemplateStatus.PUBLISHED,
    )
    outline = OutlinePlan(
        presentation_id=uuid4(),
        title="t",
        thesis="t",
        audience="a",
        purpose="p",
        sections=[
            OutlineSection(
                id="problem",
                title="问题",
                purpose="说明问题",
                key_message="现场问题严重。",
                order=0,
                category="problem",
            )
        ],
    )
    page = OutlineTemplateCompatibility(
        slide_id="problem__p01",
        section_id="problem",
        section_title="问题",
        schema_id=schema.id,
        representative_slide_id="missing_slide",
        preferred_layout_id=layout.id,
        fallback_mode="template_editing",
        template_affinity=0.8,
    )
    co_plan = OutlineTemplateCoPlan(
        outline_id=str(outline.id),
        page_plans=[page],
        template_editing_page_ids=[page.slide_id],
    )
    batch, updated = OutlineTemplateEditingService().execute(
        co_plan=co_plan,
        outline=outline,
        presentation=ReferencePresentation(name="empty", slides=[]),
        schemas=[schema],
        template=template,
    )
    assert batch.skipped_count == 1
    assert updated.page_plans[0].edit_scene_status == "skipped"


def test_execute_marks_semantic_contract_for_strategy_schema() -> None:
    from archium.domain.outline import OutlineSection
    from archium.domain.visual.architectural_content_schema import ContentRequirement, ContentRole
    from archium.domain.visual.architectural_template import (
        ArchitecturalTemplate,
        ArchitecturalTemplateLayout,
        TemplatePageType,
        TemplateStatus,
    )
    from archium.domain.visual.reference_slide import (
        REFERENCE_TEMPLATE_ASSET_ORIGIN,
        ReferenceAsset,
        ReferenceElement,
        ReferenceElementType,
        ReferencePresentation,
        ReferenceSlideSnapshot,
    )
    from archium.domain.visual.template_induction import (
        ArchitecturalContentType,
        FunctionalSlideType,
        OutlineTemplateCompatibility,
        OutlineTemplateCoPlan,
    )

    schema = ArchitecturalContentSchema(
        name="content/strategy",
        cluster_id="c1",
        representative_slide_id="slide_001",
        content_type=ArchitecturalContentType.STRATEGY,
        functional_type=FunctionalSlideType.CONTENT,
        page_purpose="提出策略",
        central_claim=ContentRequirement(role=ContentRole.CENTRAL_CLAIM, required=True, max_count=1),
        evidence_items=[
            ContentRequirement(role=ContentRole.EVIDENCE, required=True, min_count=1, max_count=3),
        ],
    )
    layout = ArchitecturalTemplateLayout(
        name="strategy",
        page_index=0,
        page_type=TemplatePageType.TEXT_ARGUMENT,
        content_schema_id=schema.id,
        representative_slide_id="slide_001",
        cluster_id="c1",
    )
    template = ArchitecturalTemplate(
        id=uuid4(),
        name="t",
        layouts=[layout],
        content_schemas=[schema],
        status=TemplateStatus.PUBLISHED,
    )
    reference_slide = ReferenceSlideSnapshot(
        slide_index=0,
        slide_id="slide_001",
        elements=[
            ReferenceElement(
                id="title_1",
                element_type=ReferenceElementType.TEXT,
                x=0.5,
                y=0.3,
                width=8,
                height=0.6,
                text="参考标题",
                semantic_role="title",
            ),
            ReferenceElement(
                id="body_1",
                element_type=ReferenceElementType.TEXT,
                x=0.5,
                y=1.0,
                width=8,
                height=1.0,
                text="参考判断",
                semantic_role="body",
            ),
        ],
        text_content=["参考标题", "参考判断"],
    )
    outline = OutlinePlan(
        presentation_id=uuid4(),
        title="t",
        thesis="t",
        audience="a",
        purpose="p",
        sections=[
            OutlineSection(
                id="strategy",
                title="策略",
                purpose="说明策略方向",
                key_message="以慢行优先组织空间",
                order=0,
                category="strategy",
                evidence_requirements=["保留历史街巷肌理"],
            )
        ],
    )
    page = OutlineTemplateCompatibility(
        slide_id="strategy__p01",
        section_id="strategy",
        section_title="策略",
        schema_id=schema.id,
        representative_slide_id="slide_001",
        preferred_layout_id=layout.id,
        fallback_mode="template_editing",
        template_affinity=0.9,
    )
    co_plan = OutlineTemplateCoPlan(
        outline_id=str(outline.id),
        page_plans=[page],
        template_editing_page_ids=[page.slide_id],
    )
    batch, _ = OutlineTemplateEditingService().execute(
        co_plan=co_plan,
        outline=outline,
        presentation=ReferencePresentation(name="ref", slides=[reference_slide]),
        schemas=[schema],
        template=template,
    )
    assert batch.generated_count == 1
    assert batch.page_results[0].semantic_contract_active

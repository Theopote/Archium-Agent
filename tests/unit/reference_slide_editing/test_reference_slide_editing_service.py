"""Tests for ReferenceSlideEditingService (Phase 6 skeleton)."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.reference_slide_editing_service import ReferenceSlideEditingService
from archium.domain.asset import Asset
from archium.domain.citation import Citation
from archium.domain.enums import AssetType
from archium.domain.presentation_manuscript import ManuscriptFact
from archium.domain.slide import SlideSpec
from archium.domain.slide_generation_context import SlideGenerationContext
from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    ContentRequirement,
    ContentRole,
    VisualRequirement,
)
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplatePageType,
    TemplateStatus,
)
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.reference_slide import (
    REFERENCE_TEMPLATE_ASSET_ORIGIN,
    ReferenceAsset,
    ReferenceElement,
    ReferenceElementType,
    ReferenceSlideSnapshot,
)
from archium.domain.visual.render_scene import DrawingNode, ImageNode, ShapeNode, TextNode
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
)


def _schema() -> ArchitecturalContentSchema:
    return ArchitecturalContentSchema(
        name="content/photo_analysis",
        cluster_id="c1",
        representative_slide_id="slide_001",
        content_type=ArchitecturalContentType.PHOTO_ANALYSIS,
        functional_type=FunctionalSlideType.CONTENT,
        page_purpose="证明现场问题",
        forbidden_asset_origins=["reference_template"],
    )


def _template(schema: ArchitecturalContentSchema) -> ArchitecturalTemplate:
    layout = ArchitecturalTemplateLayout(
        name="photo",
        page_index=0,
        page_type=TemplatePageType.PHOTO_GRID,
        suitable_content_types=["photo_analysis"],
        content_schema_id=schema.id,
        representative_slide_id="slide_001",
        cluster_id="c1",
    )
    return ArchitecturalTemplate(
        id=uuid4(),
        name="test-template",
        layouts=[layout],
        content_schemas=[schema],
        status=TemplateStatus.PUBLISHED,
    )


def _reference_slide() -> ReferenceSlideSnapshot:
    ref_asset = ReferenceAsset(
        id="asset_ref_1",
        asset_origin=REFERENCE_TEMPLATE_ASSET_ORIGIN,
        relative_path="assets/slide_001/image_001.png",
    )
    return ReferenceSlideSnapshot(
        slide_index=0,
        slide_id="slide_001",
        elements=[
            ReferenceElement(
                id="deco_1",
                element_type=ReferenceElementType.DECORATION,
                x=0,
                y=0,
                width=10,
                height=5.625,
                z_index=0,
                fill_color="#EEEEEE",
            ),
            ReferenceElement(
                id="title_1",
                element_type=ReferenceElementType.TEXT,
                x=0.5,
                y=0.3,
                width=8,
                height=0.6,
                z_index=1,
                text="参考模板标题",
                semantic_role="title",
                font_size_pt=32,
            ),
            ReferenceElement(
                id="img_1",
                element_type=ReferenceElementType.IMAGE,
                x=1,
                y=1.2,
                width=4,
                height=3,
                z_index=2,
                asset_id="asset_ref_1",
            ),
            ReferenceElement(
                id="body_1",
                element_type=ReferenceElementType.TEXT,
                x=5.5,
                y=1.2,
                width=3.5,
                height=2,
                z_index=3,
                text="参考案例说明文字",
                semantic_role="body",
            ),
        ],
        text_content=["参考模板标题", "参考案例说明文字"],
        image_assets=[ref_asset],
    )


def _slide_spec() -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="problem",
        order=0,
        title="项目现场问题",
        message="人车冲突严重，需要优化入口流线。",
        key_points=["高峰时段拥堵", "消防通道被占用"],
        speaker_notes="图1为工作日高峰拍摄。",
        source_citations=[
            Citation(
                document_id=uuid4(),
                document_name="现场调研报告",
                page_number=12,
            )
        ],
    )


def test_generate_scene_strips_reference_text_and_uses_slide_spec() -> None:
    schema = _schema()
    template = _template(schema)
    slide = _slide_spec()
    result = ReferenceSlideEditingService().generate_scene(
        reference_slide=_reference_slide(),
        content_schema=schema,
        slide_spec=slide,
        assets=[],
        design_system=default_presentation_design_system(),
        template=template,
    )
    assert result.reference_content_stripped
    assert result.stripped_text_count >= 2
    text_nodes = [n for n in result.scene.nodes if isinstance(n, TextNode)]
    texts = {n.text for n in text_nodes}
    assert slide.title in texts
    assert slide.key_points[0] in texts
    assert "参考模板标题" not in texts
    assert "参考案例说明文字" not in texts
    assert any(a.action_type == "replace_text" for a in result.actions)


def test_generate_scene_never_persists_reference_template_assets() -> None:
    schema = _schema()
    template = _template(schema)
    project_asset = Asset(
        id=uuid4(),
        project_id=uuid4(),
        filename="site.jpg",
        path="project://site.jpg",
        asset_type=AssetType.PHOTO,
    )
    result = ReferenceSlideEditingService().generate_scene(
        reference_slide=_reference_slide(),
        content_schema=schema,
        slide_spec=_slide_spec(),
        assets=[project_asset],
        design_system=default_presentation_design_system(),
        template=template,
    )
    assert result.stripped_asset_count >= 1
    assert any(a.action_type == "remove_reference_asset" for a in result.actions)
    for node in result.scene.nodes:
        if isinstance(node, (ImageNode, DrawingNode)):
            assert "assets/slide_001" not in (node.storage_uri or "")
            assert node.asset_origin != "reference_template" if hasattr(node, "asset_origin") else True
    manifest_uris = {ref.storage_uri for ref in result.scene.asset_manifest}
    assert "assets/slide_001/image_001.png" not in manifest_uris
    assert "project://site.jpg" in manifest_uris


def test_generate_scene_binds_project_photo_asset() -> None:
    schema = _schema()
    template = _template(schema)
    project_asset = Asset(
        id=uuid4(),
        project_id=uuid4(),
        filename="site.jpg",
        path="project://site.jpg",
        asset_type=AssetType.PHOTO,
    )
    result = ReferenceSlideEditingService().generate_scene(
        reference_slide=_reference_slide(),
        content_schema=schema,
        slide_spec=_slide_spec(),
        assets=[project_asset],
        design_system=default_presentation_design_system(),
        template=template,
    )
    image_nodes = [n for n in result.scene.nodes if isinstance(n, ImageNode)]
    assert image_nodes
    assert image_nodes[0].asset_id == project_asset.id
    assert image_nodes[0].asset_unresolved is False
    assert any(a.action_type == "replace_asset" for a in result.actions)


def test_generate_scene_marks_unresolved_when_no_project_assets() -> None:
    schema = _schema()
    template = _template(schema)
    result = ReferenceSlideEditingService().generate_scene(
        reference_slide=_reference_slide(),
        content_schema=schema,
        slide_spec=_slide_spec(),
        assets=[],
        design_system=default_presentation_design_system(),
        template=template,
    )
    image_nodes = [n for n in result.scene.nodes if isinstance(n, ImageNode)]
    assert image_nodes
    assert image_nodes[0].asset_unresolved is True
    assert any("no project asset" in w for w in result.warnings)


def test_generate_scene_preserves_decoration_as_locked_shape() -> None:
    schema = _schema()
    template = _template(schema)
    result = ReferenceSlideEditingService().generate_scene(
        reference_slide=_reference_slide(),
        content_schema=schema,
        slide_spec=_slide_spec(),
        assets=[],
        design_system=default_presentation_design_system(),
        template=template,
    )
    deco_nodes = [n for n in result.scene.nodes if isinstance(n, ShapeNode) and n.id == "deco_1"]
    assert deco_nodes
    assert deco_nodes[0].locked is True
    assert any(a.action_type == "preserve_decoration" for a in result.actions)


def _semantic_schema() -> ArchitecturalContentSchema:
    return ArchitecturalContentSchema(
        name="content/photo_analysis",
        cluster_id="c1",
        representative_slide_id="slide_001",
        content_type=ArchitecturalContentType.PHOTO_ANALYSIS,
        functional_type=FunctionalSlideType.CONTENT,
        page_purpose="证明现场问题",
        forbidden_asset_origins=["reference_template"],
        central_claim=ContentRequirement(
            role=ContentRole.CENTRAL_CLAIM,
            required=True,
            max_count=1,
        ),
        evidence_items=[
            ContentRequirement(
                role=ContentRole.EVIDENCE,
                required=True,
                min_count=1,
                max_count=4,
            ),
        ],
        visual_evidence=[
            VisualRequirement(
                role="hero_image",
                required=True,
                min_count=1,
                max_count=1,
            ),
        ],
    )


def _semantic_reference_slide() -> ReferenceSlideSnapshot:
    ref_asset = ReferenceAsset(
        id="asset_ref_1",
        asset_origin=REFERENCE_TEMPLATE_ASSET_ORIGIN,
        relative_path="assets/slide_001/image_001.png",
    )
    return ReferenceSlideSnapshot(
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
                z_index=1,
                text="参考标题",
                semantic_role="title",
                font_size_pt=32,
            ),
            ReferenceElement(
                id="claim_1",
                element_type=ReferenceElementType.TEXT,
                x=0.5,
                y=1.0,
                width=8,
                height=0.8,
                z_index=2,
                text="参考核心判断",
                semantic_role="body",
            ),
            ReferenceElement(
                id="evidence_1",
                element_type=ReferenceElementType.TEXT,
                x=0.5,
                y=2.0,
                width=8,
                height=0.6,
                z_index=3,
                text="参考证据一",
                semantic_role="body",
            ),
            ReferenceElement(
                id="img_1",
                element_type=ReferenceElementType.IMAGE,
                x=1,
                y=3.0,
                width=4,
                height=3,
                z_index=4,
                asset_id="asset_ref_1",
            ),
        ],
        text_content=["参考标题", "参考核心判断", "参考证据一"],
        image_assets=[ref_asset],
    )


def test_generate_scene_uses_semantic_contract_for_text_fill() -> None:
    schema = _semantic_schema()
    template = _template(schema)
    slide = _slide_spec()
    result = ReferenceSlideEditingService().generate_scene(
        reference_slide=_semantic_reference_slide(),
        content_schema=schema,
        slide_spec=slide,
        assets=[],
        design_system=default_presentation_design_system(),
        template=template,
    )
    assert any("semantic_content_contract active" in w for w in result.warnings)
    texts = {n.text for n in result.scene.nodes if isinstance(n, TextNode)}
    assert slide.title in texts
    assert slide.message in texts
    assert slide.key_points[0] in texts
    replace_actions = [a for a in result.actions if a.action_type == "replace_text"]
    assert any(a.reason == "semantic contract fill" for a in replace_actions)


def test_generate_scene_uses_visual_evidence_roles_for_images() -> None:
    schema = _semantic_schema()
    template = _template(schema)
    project_asset = Asset(
        id=uuid4(),
        project_id=uuid4(),
        filename="site.jpg",
        path="project://site.jpg",
        asset_type=AssetType.PHOTO,
    )
    result = ReferenceSlideEditingService().generate_scene(
        reference_slide=_semantic_reference_slide(),
        content_schema=schema,
        slide_spec=_slide_spec(),
        assets=[project_asset],
        design_system=default_presentation_design_system(),
        template=template,
    )
    image_nodes = [n for n in result.scene.nodes if isinstance(n, ImageNode)]
    assert image_nodes
    assert image_nodes[0].semantic_role == "hero_image"
    replace_asset = [a for a in result.actions if a.action_type == "replace_asset"]
    assert any(a.reason == "semantic visual_evidence bind" for a in replace_asset)


def test_generate_scene_maps_multiple_image_slots_to_evidence_depth() -> None:
    schema = ArchitecturalContentSchema(
        name="content/photo_analysis",
        cluster_id="c1",
        representative_slide_id="slide_multi",
        content_type=ArchitecturalContentType.PHOTO_ANALYSIS,
        functional_type=FunctionalSlideType.CONTENT,
        page_purpose="证明多图现场问题",
        forbidden_asset_origins=["reference_template"],
        evidence_items=[
            ContentRequirement(
                role=ContentRole.EVIDENCE,
                required=True,
                min_count=3,
                max_count=4,
            ),
        ],
        visual_evidence=[
            VisualRequirement(
                role="hero_image",
                required=True,
                min_count=1,
                max_count=1,
            ),
        ],
    )
    template = _template(schema)
    ref_assets = [
        ReferenceAsset(
            id=f"asset_ref_{idx}",
            asset_origin=REFERENCE_TEMPLATE_ASSET_ORIGIN,
            relative_path=f"assets/slide_multi/image_{idx:03d}.png",
        )
        for idx in range(1, 4)
    ]
    reference_slide = ReferenceSlideSnapshot(
        slide_index=0,
        slide_id="slide_multi",
        elements=[
            ReferenceElement(
                id=f"img_{idx}",
                element_type=ReferenceElementType.IMAGE,
                x=float(idx),
                y=1.0,
                width=2.5,
                height=2.0,
                z_index=idx,
                asset_id=ref_assets[idx - 1].id,
            )
            for idx in range(1, 4)
        ],
        image_assets=ref_assets,
    )
    project_assets = [
        Asset(
            id=uuid4(),
            project_id=uuid4(),
            filename=f"site_{idx}.jpg",
            path=f"project://site_{idx}.jpg",
            asset_type=AssetType.PHOTO,
        )
        for idx in range(1, 4)
    ]
    result = ReferenceSlideEditingService().generate_scene(
        reference_slide=reference_slide,
        content_schema=schema,
        slide_spec=_slide_spec(),
        assets=project_assets,
        design_system=default_presentation_design_system(),
        template=template,
    )
    image_nodes = [n for n in result.scene.nodes if isinstance(n, ImageNode)]
    assert len(image_nodes) == 3
    assert [n.semantic_role for n in image_nodes] == [
        "hero_image",
        "supporting_image",
        "supporting_image",
    ]
    assert len({n.asset_id for n in image_nodes}) == 3


def test_generate_scene_uses_generation_context_assets_and_warnings() -> None:
    schema = _semantic_schema()
    template = _template(schema)
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="problem",
        order=0,
        title="项目现场问题",
        message="人车冲突严重，需要优化入口流线。",
        key_points=[],
        speaker_notes="图1为工作日高峰拍摄。",
    )
    context_asset = Asset(
        id=uuid4(),
        project_id=uuid4(),
        filename="context_site.jpg",
        path="project://context_site.jpg",
        asset_type=AssetType.PHOTO,
        description="现场入口拥堵",
    )
    generation_context = SlideGenerationContext(
        slide_spec=slide,
        section_summary="现状分析：入口人车交织严重。",
        verified_facts=[
            ManuscriptFact(
                statement="高峰时段入口排队超过 80 米",
                source_id="fact-ctx",
                verified=True,
            )
        ],
        relevant_assets=[context_asset],
    )
    result = ReferenceSlideEditingService().generate_scene(
        reference_slide=_semantic_reference_slide(),
        content_schema=schema,
        slide_spec=slide,
        assets=[],
        design_system=default_presentation_design_system(),
        template=template,
        generation_context=generation_context,
    )
    assert any("slide_generation_context active" in w for w in result.warnings)
    image_nodes = [n for n in result.scene.nodes if isinstance(n, ImageNode)]
    assert image_nodes
    assert image_nodes[0].asset_id == context_asset.id
    texts = {n.text for n in result.scene.nodes if isinstance(n, TextNode)}
    assert "高峰时段入口排队超过 80 米" in texts

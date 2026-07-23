"""Unit tests for Schema Test Fill render validation path."""

from __future__ import annotations

from archium.application.visual.architectural_content_schema_test_fill import (
    ArchitecturalContentSchemaTestFillService,
    build_test_fill_assets,
    build_test_fill_slide_spec,
)
from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    ContentRequirement,
    ContentRole,
    SchemaVisualRequirement,
)
from archium.domain.visual.reference_slide import (
    REFERENCE_TEMPLATE_ASSET_ORIGIN,
    ReferenceAsset,
    ReferenceElement,
    ReferenceElementType,
    ReferenceSlideSnapshot,
)
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
)


def _schema(*, with_visual: bool = True) -> ArchitecturalContentSchema:
    schema = ArchitecturalContentSchema(
        name="content/photo_analysis",
        cluster_id="c1",
        representative_slide_id="slide_001",
        content_type=ArchitecturalContentType.PHOTO_ANALYSIS,
        functional_type=FunctionalSlideType.CONTENT,
        page_purpose="证明现场问题",
        forbidden_asset_origins=["reference_template"],
        required_content=[
            ContentRequirement(role=ContentRole.TITLE, required=True, min_count=1, max_count=1),
            ContentRequirement(
                role=ContentRole.BODY,
                required=True,
                min_count=1,
                max_count=1,
                min_length=8,
                max_length=120,
            ),
        ],
    )
    if with_visual:
        schema.visual_requirements = [
            SchemaVisualRequirement(role="hero_image", required=True, min_count=1, max_count=1),
        ]
    return schema


def _drawing_schema() -> ArchitecturalContentSchema:
    return ArchitecturalContentSchema(
        name="content/drawing_focus",
        cluster_id="c2",
        representative_slide_id="slide_drawing",
        content_type=ArchitecturalContentType.DRAWING_FOCUS,
        functional_type=FunctionalSlideType.CONTENT,
        page_purpose="展示总平面",
        forbidden_asset_origins=["reference_template"],
        required_content=[
            ContentRequirement(role=ContentRole.TITLE, required=True, min_count=1, max_count=1),
            ContentRequirement(
                role=ContentRole.BODY,
                required=True,
                min_count=1,
                max_count=1,
                min_length=8,
                max_length=120,
            ),
        ],
        visual_requirements=[
            SchemaVisualRequirement(role="drawing", required=True, min_count=1, max_count=1, fit_mode="contain"),
        ],
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
                semantic_role="hero_image",
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


def _drawing_reference_slide() -> ReferenceSlideSnapshot:
    return ReferenceSlideSnapshot(
        slide_index=0,
        slide_id="slide_drawing",
        elements=[
            ReferenceElement(
                id="title_1",
                element_type=ReferenceElementType.TEXT,
                x=0.5,
                y=0.3,
                width=8,
                height=0.6,
                z_index=1,
                text="总平面",
                semantic_role="title",
                font_size_pt=28,
            ),
            ReferenceElement(
                id="drawing_1",
                element_type=ReferenceElementType.DRAWING,
                x=1,
                y=1.2,
                width=6,
                height=4,
                z_index=2,
                semantic_role="drawing",
            ),
            ReferenceElement(
                id="body_1",
                element_type=ReferenceElementType.TEXT,
                x=7.2,
                y=1.2,
                width=2.2,
                height=2,
                z_index=3,
                text="图纸说明文字内容",
                semantic_role="body",
            ),
        ],
        text_content=["总平面", "图纸说明文字内容"],
    )


def test_build_test_fill_slide_spec_respects_schema_bounds() -> None:
    schema = _schema()
    slide_spec = build_test_fill_slide_spec(schema)
    assert slide_spec.title
    assert 8 <= len(slide_spec.message) <= 120
    assert slide_spec.key_points


def test_build_test_fill_assets_for_visual_schema() -> None:
    schema = _schema()
    assets = build_test_fill_assets(schema)
    assert assets
    assert all(asset.path.startswith("benchmark://") for asset in assets)


def test_validate_compiles_render_scene_and_passes_qa() -> None:
    schema = _schema()
    slide = _reference_slide()
    result = ArchitecturalContentSchemaTestFillService().validate(schema, slide)
    assert result.required_slots_filled
    assert result.scene_compiled
    assert result.scene_role_coverage_ok
    assert result.render_valid
    assert result.scene_id
    assert result.scene_hash
    assert result.node_count >= 2
    assert "semantic" in result.qa_layer_issue_counts
    assert "geometry" in result.qa_layer_issue_counts
    assert "asset" in result.qa_layer_issue_counts
    assert "drawing" in result.qa_layer_issue_counts
    assert not result.reference_leakage
    assert not result.missing_assets


def test_validate_drawing_focus_compiles_drawing_node() -> None:
    schema = _drawing_schema()
    slide = _drawing_reference_slide()
    result = ArchitecturalContentSchemaTestFillService().validate(schema, slide)
    assert result.required_slots_filled
    assert result.scene_compiled
    assert result.scene_role_coverage_ok
    assert result.render_valid
    assert result.node_count >= 2


def test_validate_render_path_can_be_disabled() -> None:
    schema = _schema()
    slide = _reference_slide()
    result = ArchitecturalContentSchemaTestFillService(render_validate=False).validate(schema, slide)
    assert result.required_slots_filled
    assert not result.scene_compiled
    assert not result.scene_hash


def test_validate_fails_when_structural_slots_missing() -> None:
    schema = _schema()
    slide = ReferenceSlideSnapshot(
        slide_index=0,
        slide_id="slide_empty",
        elements=[],
    )
    result = ArchitecturalContentSchemaTestFillService().validate(schema, slide)
    assert not result.required_slots_filled
    assert not result.scene_compiled
    assert not result.render_valid

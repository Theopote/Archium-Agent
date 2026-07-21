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
    VisualRequirement,
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
            VisualRequirement(role="hero_image", required=True, min_count=1, max_count=1),
        ]
    return schema


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
    assert result.render_valid
    assert not result.reference_leakage
    assert not result.missing_assets


def test_validate_render_path_can_be_disabled() -> None:
    schema = _schema()
    slide = _reference_slide()
    result = ArchitecturalContentSchemaTestFillService(render_validate=False).validate(schema, slide)
    assert result.required_slots_filled
    assert not result.scene_compiled


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

"""case_a hospital: real on-disk photos through Grammar → binding → layout (E2E)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from PIL import Image, ImageDraw
from archium.application.slide_asset_binding_service import apply_slide_asset_bindings
from archium.application.visual.asset_reference import AssetReferenceContext
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.visual_grammar_assets import (
    grammar_role_from_requirement,
    resolve_grammar_hero_asset_id,
)
from archium.application.visual.visual_grammar_intent import preferred_variant_for_intent
from archium.application.visual.visual_grammar_recognition import recognize_page_archetype
from archium.application.visual.visual_grammar_slots import ensure_evidence_slots_on_slide
from archium.domain.asset import Asset
from archium.domain.citation import Citation
from archium.domain.enums import AssetType, SlideAssetBindingRole, SlideType, VisualType
from archium.domain.slide import SlideSpec, SlideVisualRequirement
from archium.domain.slide_asset_binding import SlideAssetBinding
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import LayoutContentType, LayoutFamily, VisualContentType
from archium.domain.visual.validation import (
    LAYOUT_HERO_ASSET_MISSING,
    LAYOUT_MISSING_ASSET_REFERENCE,
    LAYOUT_UNRESOLVED_ASSET_PATH,
)
from archium.domain.visual.visual_grammar import PageArchetype
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.generators.base import LayoutGeneratorContext, content_from_slide
from archium.infrastructure.layout.layout_solver import LayoutSolver
from archium.infrastructure.visual.layout_preview_renderer import render_layout_preview_png

pytestmark = pytest.mark.regression

_CASE_A = Path(__file__).resolve().parents[1] / "regression" / "cases" / "case_a_hospital.json"
_DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")

# Stable IDs so assertions stay readable across the pipeline.
HISTORIC_PHOTO_ID = UUID("ca0a0001-0001-4001-8001-000000000001")
SITE_PHOTO_1_ID = UUID("ca0a0002-0001-4001-8001-000000000002")
SITE_PHOTO_2_ID = UUID("ca0a0003-0001-4001-8001-000000000003")


def _write_photo(
    path: Path,
    *,
    color: tuple[int, int, int],
    label: str,
    size: tuple[int, int] = (1200, 800),
) -> Path:
    """Write a resolvable JPEG that passes layout image QA size heuristics."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color=color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, size[0] - 40, size[1] - 40), outline=(255, 255, 255), width=4)
    draw.text((60, 60), label, fill=(255, 255, 255))
    image.save(path, format="JPEG", quality=90)
    assert path.is_file()
    assert path.stat().st_size > 1000
    return path


def _asset(
    *,
    asset_id: UUID,
    project_id: UUID,
    path: Path,
    filename: str,
    description: str,
    tags: list[str],
) -> Asset:
    return Asset(
        id=asset_id,
        project_id=project_id,
        filename=filename,
        path=str(path.resolve()),
        asset_type=AssetType.PHOTO,
        width=1200,
        height=800,
        description=description,
        tags=tags,
        quality_score=0.9,
        metadata={"origin": "project_upload", "purpose": "site_evidence"},
    )


def _asset_context(assets: list[Asset]) -> AssetReferenceContext:
    known = frozenset(str(asset.id) for asset in assets)
    paths = {str(asset.id): asset.path for asset in assets}
    return AssetReferenceContext(
        known_asset_ids=known,
        resolved_paths=dict(paths),
        absolute_paths=dict(paths),
        asset_types={str(asset.id): asset.asset_type.value for asset in assets},
        asset_origins={str(asset.id): "project_upload" for asset in assets},
    )


def _generate_plan(
    slide: SlideSpec,
    intent: VisualIntent,
    family: LayoutFamily,
    variant: str,
):
    design = default_presentation_design_system()
    content = content_from_slide(slide, intent)
    context = LayoutGeneratorContext(
        slide=slide,
        visual_intent=intent,
        art_direction=None,
        design_system=design,
        content=content,
        variant=variant,
    )
    plan = LayoutSolver().generate(family, context)
    return plan, design, content


def test_case_a_real_photos_opening_and_diagnosis_e2e(tmp_path: Path) -> None:
    """Disk photos → grammar slots → bindings → layout with resolvable content_refs."""
    assert _CASE_A.is_file()

    project_id = uuid4()
    presentation_id = uuid4()
    photo_dir = tmp_path / "case_a_hospital" / "photos"

    historic_path = _write_photo(
        photo_dir / "historic_courtyard.jpg",
        color=(92, 74, 58),
        label="HISTORIC / 历史院区",
    )
    site1_path = _write_photo(
        photo_dir / "entrance_conflict.jpg",
        color=(70, 90, 110),
        label="SITE 1 / 入口交织",
    )
    site2_path = _write_photo(
        photo_dir / "service_corridor.jpg",
        color=(80, 70, 70),
        label="SITE 2 / 后勤老化",
    )

    historic = _asset(
        asset_id=HISTORIC_PHOTO_ID,
        project_id=project_id,
        path=historic_path,
        filename="historic_courtyard.jpg",
        description="历史院区老照片 / historic courtyard",
        tags=["historic", "历史", "开篇"],
    )
    site1 = _asset(
        asset_id=SITE_PHOTO_1_ID,
        project_id=project_id,
        path=site1_path,
        filename="entrance_conflict.jpg",
        description="入口广场人车交织现场照片",
        tags=["现场", "问题", "site"],
    )
    site2 = _asset(
        asset_id=SITE_PHOTO_2_ID,
        project_id=project_id,
        path=site2_path,
        filename="service_corridor.jpg",
        description="后勤通道老化现场照片",
        tags=["现场", "问题", "site"],
    )
    assets_by_id = {historic.id: historic, site1.id: site1, site2.id: site2}
    ctx = _asset_context([historic, site1, site2])

    # --- Opening: narrative_opening with historic photo bound to grammar slot ---
    opening = SlideSpec(
        presentation_id=presentation_id,
        chapter_id="ch1",
        order=0,
        title="医院老院区更新开篇",
        message="历史院区面临流线交叉与空间矛盾，更新目标是可持续运营。",
        slide_type=SlideType.CONTENT,
        key_points=["流线交叉拥堵", "后勤空间老化", "可持续运营"],
        visual_requirements=[
            SlideVisualRequirement(type=VisualType.SITE_PHOTO, description="历史照片"),
        ],
        source_citations=[
            Citation(document_id=_DOCUMENT_ID, document_name="院史资料.pdf", page_number=1),
        ],
    )
    opening_rec = recognize_page_archetype(opening)
    assert opening_rec.archetype == PageArchetype.NARRATIVE_OPENING
    opening = ensure_evidence_slots_on_slide(
        opening,
        archetype=opening_rec.archetype,
        recipe=opening_rec.recipe,
    )
    assert "historic_or_context_photo" in opening.required_evidence_slots

    opening_slides, _, applied = apply_slide_asset_bindings(
        [opening],
        [
            SlideAssetBinding(
                page_order=0,
                asset_id=historic.id,
                binding_role=SlideAssetBindingRole.PROJECT_PHOTO,
                user_description="院史老照片（项目上传）",
            )
        ],
        assets_by_id=assets_by_id,
    )
    opening = opening_slides[0]
    assert applied == 1
    historic_req = next(
        req
        for req in opening.visual_requirements
        if grammar_role_from_requirement(req) == "historic_or_context_photo"
    )
    assert historic_req.preferred_asset_ids == [historic.id]
    assert historic_req.confirmed is True
    assert resolve_grammar_hero_asset_id(opening) == historic.id

    opening_intent = VisualIntent(
        slide_id=opening.id,
        presentation_id=presentation_id,
        page_archetype=PageArchetype.NARRATIVE_OPENING,
        communication_goal="建立叙事张力",
        audience_takeaway=opening.message,
        visual_priority="photo",
        dominant_content_type=VisualContentType.MIXED,
        hero_asset_id=resolve_grammar_hero_asset_id(opening),
        preferred_layout_families=[LayoutFamily.HYBRID_CANVAS],
    )
    opening_variant = (
        preferred_variant_for_intent(opening_intent, LayoutFamily.HYBRID_CANVAS)
        or "narrative_opening"
    )
    assert opening_variant == "narrative_opening"

    opening_plan, opening_design, opening_content = _generate_plan(
        opening,
        opening_intent,
        LayoutFamily.HYBRID_CANVAS,
        opening_variant,
    )
    assert opening_content.hero_asset_ref == str(historic.id)
    hero = opening_plan.element_by_id("historic_photo")
    assert hero is not None
    assert hero.content_type == LayoutContentType.IMAGE
    assert hero.content_ref == str(historic.id)
    assert not str(hero.content_ref).startswith("grammar:")

    opening_report = LayoutValidationService().validate(
        opening_plan,
        opening_design,
        require_source=True,
        asset_context=ctx,
    )
    blocking = {
        LAYOUT_MISSING_ASSET_REFERENCE,
        LAYOUT_HERO_ASSET_MISSING,
        LAYOUT_UNRESOLVED_ASSET_PATH,
    }
    assert not any(issue.rule_code in blocking for issue in opening_report.issues)
    assert not opening_report.has_critical()

    preview = render_layout_preview_png(
        opening_plan,
        tmp_path / "case_a_opening_preview.png",
    )
    assert preview.is_file() and preview.stat().st_size > 500

    # --- Diagnosis: evidence_board with two site photos ---
    diagnosis = SlideSpec(
        presentation_id=presentation_id,
        chapter_id="ch1",
        order=3,
        title="现状问题诊断",
        message="急诊流线交叉导致拥堵，后勤通道老化。",
        slide_type=SlideType.IMAGE,
        key_points=["问题1：流线交叉", "问题2：后勤老化"],
        visual_requirements=[
            SlideVisualRequirement(type=VisualType.SITE_PHOTO, description="现场照片1"),
            SlideVisualRequirement(type=VisualType.SITE_PHOTO, description="现场照片2"),
        ],
        source_citations=[
            Citation(document_id=_DOCUMENT_ID, document_name="现场踏勘.pdf", page_number=5),
        ],
    )
    diagnosis_rec = recognize_page_archetype(diagnosis)
    assert diagnosis_rec.archetype == PageArchetype.SITE_PROBLEM_DIAGNOSIS
    diagnosis = ensure_evidence_slots_on_slide(
        diagnosis,
        archetype=diagnosis_rec.archetype,
        recipe=diagnosis_rec.recipe,
    )

    diagnosis_slides, _, diag_applied = apply_slide_asset_bindings(
        [diagnosis],
        [
            SlideAssetBinding(
                page_order=3,
                asset_id=site1.id,
                binding_role=SlideAssetBindingRole.PROJECT_PHOTO,
                user_description="入口交织现场",
            ),
            SlideAssetBinding(
                page_order=3,
                asset_id=site2.id,
                binding_role=SlideAssetBindingRole.SUPPORTING_PHOTO,
                user_description="后勤老化现场",
            ),
        ],
        assets_by_id=assets_by_id,
    )
    diagnosis = diagnosis_slides[0]
    assert diag_applied == 2
    bound_ids = {
        aid
        for req in diagnosis.visual_requirements
        for aid in req.preferred_asset_ids
    }
    assert site1.id in bound_ids and site2.id in bound_ids

    diagnosis_intent = VisualIntent(
        slide_id=diagnosis.id,
        presentation_id=presentation_id,
        page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS,
        communication_goal="诊断现状问题",
        audience_takeaway=diagnosis.message,
        visual_priority="photos",
        dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
        hero_asset_id=site1.id,
        supporting_asset_ids=[site2.id],
        preferred_layout_families=[LayoutFamily.EVIDENCE_BOARD],
    )
    diagnosis_variant = (
        preferred_variant_for_intent(diagnosis_intent, LayoutFamily.EVIDENCE_BOARD)
        or "diagnosis_split"
    )
    assert diagnosis_variant == "diagnosis_split"

    diagnosis_plan, diagnosis_design, diagnosis_content = _generate_plan(
        diagnosis,
        diagnosis_intent,
        LayoutFamily.EVIDENCE_BOARD,
        diagnosis_variant,
    )
    assert diagnosis_content.hero_asset_ref == str(site1.id)
    assert str(site2.id) in diagnosis_content.supporting_asset_refs

    photo_refs = {
        el.content_ref
        for el in diagnosis_plan.elements
        if el.content_type == LayoutContentType.IMAGE and el.content_ref
    }
    assert str(site1.id) in photo_refs
    assert str(site2.id) in photo_refs
    assert not any(str(ref).startswith("grammar:") for ref in photo_refs)

    diagnosis_report = LayoutValidationService().validate(
        diagnosis_plan,
        diagnosis_design,
        require_source=True,
        asset_context=ctx,
    )
    assert not any(issue.rule_code in blocking for issue in diagnosis_report.issues)
    assert not diagnosis_report.has_critical()

    diag_preview = render_layout_preview_png(
        diagnosis_plan,
        tmp_path / "case_a_diagnosis_preview.png",
    )
    assert diag_preview.is_file()


def test_case_a_opening_without_photo_keeps_grammar_placeholder(tmp_path: Path) -> None:
    """Missing historic asset still reserves the hero slot with grammar placeholder."""
    opening = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="医院老院区更新开篇",
        message="历史院区面临流线交叉与空间矛盾，更新目标是可持续运营。",
        key_points=["流线交叉拥堵", "后勤空间老化", "可持续运营"],
        page_archetype=PageArchetype.NARRATIVE_OPENING,
        visual_requirements=[
            SlideVisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="[grammar:historic_or_context_photo] 历史照片",
            ),
        ],
    )
    intent = VisualIntent(
        slide_id=opening.id,
        presentation_id=opening.presentation_id,
        page_archetype=PageArchetype.NARRATIVE_OPENING,
        communication_goal="开篇",
        audience_takeaway=opening.message,
        visual_priority="photo",
        dominant_content_type=VisualContentType.MIXED,
        preferred_layout_families=[LayoutFamily.HYBRID_CANVAS],
    )
    plan, design, content = _generate_plan(
        opening, intent, LayoutFamily.HYBRID_CANVAS, "narrative_opening"
    )
    assert content.hero_asset_ref is None
    hero = plan.element_by_id("historic_photo")
    assert hero is not None
    assert hero.content_ref == "grammar:historic_or_context_photo"

    empty_ctx = AssetReferenceContext(known_asset_ids=frozenset(), resolved_paths={})
    report = LayoutValidationService().validate(
        plan, design, require_source=False, asset_context=empty_ctx
    )
    assert any(
        issue.rule_code in {LAYOUT_MISSING_ASSET_REFERENCE, LAYOUT_HERO_ASSET_MISSING}
        for issue in report.issues
    )

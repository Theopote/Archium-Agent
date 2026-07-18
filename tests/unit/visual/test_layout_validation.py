"""Tests for LayoutValidationService rule coverage."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.asset_reference import AssetReferenceContext
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.domain.visual import (
    LAYOUT_DRAWING_CROPPED,
    LAYOUT_ELEMENT_OUTSIDE_PAGE,
    LAYOUT_ELEMENT_OVERLAP,
    LAYOUT_FONT_TOO_SMALL,
    LAYOUT_HERO_ASSET_MISSING,
    LAYOUT_HERO_NOT_DOMINANT,
    LAYOUT_IMAGE_DISTORTION,
    LAYOUT_MISSING_ASSET_REFERENCE,
    LAYOUT_TECHNICAL_DRAWING_MISSING,
    LAYOUT_TEXT_OVERFLOW,
    LAYOUT_UNRESOLVED_ASSET_PATH,
    LAYOUT_UNSUPPORTED_IMAGE_FORMAT,
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
    default_presentation_design_system,
)
from archium.domain.visual.enums import CropPolicy, ImageFit, LayoutContentType, LayoutIssueSeverity
from archium.domain.enums import AssetType


def _base_plan(*elements: LayoutElement, family: LayoutFamily = LayoutFamily.HERO) -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        layout_family=family,
        layout_variant="split",
        page_width=10,
        page_height=5.625,
        hero_element_id="hero" if any(el.id == "hero" for el in elements) else None,
        reading_order=[el.id for el in elements],
        whitespace_ratio=0.3,
        elements=list(elements),
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )


class TestLayoutValidationService:
    def test_outside_page(self) -> None:
        plan = _base_plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=9.5,
                y=0.4,
                width=2.0,
                height=0.5,
                style_token="title",
            )
        )
        report = LayoutValidationService().validate(plan, default_presentation_design_system())
        assert report.issues_for(LAYOUT_ELEMENT_OUTSIDE_PAGE)

    def test_overlap(self) -> None:
        plan = _base_plan(
            LayoutElement(
                id="a",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="A",
                x=1,
                y=1,
                width=3,
                height=2,
                style_token="body",
            ),
            LayoutElement(
                id="b",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="B",
                x=2,
                y=1.5,
                width=3,
                height=2,
                style_token="body",
            ),
        )
        report = LayoutValidationService().validate(plan, default_presentation_design_system())
        assert report.issues_for(LAYOUT_ELEMENT_OVERLAP)

    def test_drawing_crop_forbidden(self) -> None:
        plan = _base_plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="总图",
                x=0.7,
                y=0.45,
                width=8,
                height=0.5,
                style_token="title",
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                x=0.7,
                y=1.2,
                width=8,
                height=3.5,
                fit_mode=ImageFit.COVER,
                crop_policy=CropPolicy.COVER_CROP,
            ),
            family=LayoutFamily.DRAWING_FOCUS,
        )
        report = LayoutValidationService().validate(
            plan, default_presentation_design_system(), drawing_hero=True
        )
        assert report.issues_for(LAYOUT_DRAWING_CROPPED)

    def test_image_distortion(self) -> None:
        plan = _base_plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=1,
                y=1,
                width=4,
                height=3,
                fit_mode=ImageFit.FILL,
            )
        )
        report = LayoutValidationService().validate(plan, default_presentation_design_system())
        assert report.issues_for(LAYOUT_IMAGE_DISTORTION)

    def test_text_overflow_and_font(self) -> None:
        design = default_presentation_design_system()
        tiny = design.typography.source.model_copy(update={"font_size": 6})
        design = design.model_copy(
            update={"typography": design.typography.model_copy(update={"source": tiny})}
        )
        plan = _base_plan(
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="这是一段非常长的正文" * 40,
                x=0.7,
                y=1.0,
                width=2.0,
                height=0.4,
                style_token="body",
            ),
            LayoutElement(
                id="source",
                role=LayoutElementRole.SOURCE,
                content_type=LayoutContentType.TEXT,
                text_content="来源",
                x=0.7,
                y=5.2,
                width=3,
                height=0.2,
                style_token="source",
            ),
        )
        report = LayoutValidationService().validate(plan, design, require_source=True)
        assert report.issues_for(LAYOUT_TEXT_OVERFLOW)
        assert report.issues_for(LAYOUT_FONT_TOO_SMALL)

    def test_hero_not_dominant(self) -> None:
        plan = _base_plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=0.7,
                y=0.45,
                width=8,
                height=0.5,
                style_token="title",
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                x=0.7,
                y=1.2,
                width=2.0,
                height=1.0,
                fit_mode=ImageFit.CONTAIN,
                crop_policy=CropPolicy.FORBIDDEN,
            ),
            family=LayoutFamily.DRAWING_FOCUS,
        )
        report = LayoutValidationService().validate(
            plan, default_presentation_design_system(), drawing_hero=True
        )
        assert report.issues_for(LAYOUT_HERO_NOT_DOMINANT)

    def test_hero_asset_missing_is_error(self) -> None:
        plan = _base_plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                x=0.7,
                y=1.0,
                width=8,
                height=3.5,
                fit_mode=ImageFit.CONTAIN,
                crop_policy=CropPolicy.FORBIDDEN,
            ),
            family=LayoutFamily.DRAWING_FOCUS,
        )
        ctx = AssetReferenceContext(known_asset_ids=frozenset(), resolved_paths={})
        report = LayoutValidationService().validate(
            plan,
            default_presentation_design_system(),
            require_source=False,
            drawing_hero=True,
            asset_context=ctx,
        )
        hero_issues = report.issues_for(LAYOUT_HERO_ASSET_MISSING)
        assert hero_issues
        assert hero_issues[0].severity == LayoutIssueSeverity.ERROR
        assert report.issues_for(LAYOUT_TECHNICAL_DRAWING_MISSING)
        assert not report.valid

    def test_missing_asset_reference_severity_by_role(self) -> None:
        missing_id = str(uuid4())
        plan = _base_plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                content_ref=missing_id,
                x=0.7,
                y=1.0,
                width=5,
                height=3,
            ),
            LayoutElement(
                id="support",
                role=LayoutElementRole.SUPPORTING_VISUAL,
                content_type=LayoutContentType.IMAGE,
                content_ref=str(uuid4()),
                x=6.0,
                y=1.0,
                width=3,
                height=2,
            ),
        )
        ctx = AssetReferenceContext(known_asset_ids=frozenset(), resolved_paths={})
        report = LayoutValidationService().validate(
            plan,
            default_presentation_design_system(),
            require_source=False,
            asset_context=ctx,
        )
        missing = report.issues_for(LAYOUT_MISSING_ASSET_REFERENCE)
        assert len(missing) >= 2
        by_el = {issue.element_ids[0]: issue.severity for issue in missing}
        assert by_el["hero"] == LayoutIssueSeverity.ERROR
        assert by_el["support"] == LayoutIssueSeverity.WARNING
        assert report.issues_for(LAYOUT_HERO_ASSET_MISSING)

    def test_unresolved_asset_path(self, tmp_path) -> None:  # noqa: ANN001
        asset_id = str(uuid4())
        # Known in catalog but file path missing / not a file.
        ctx = AssetReferenceContext(
            known_asset_ids=frozenset({asset_id}),
            resolved_paths={asset_id: str(tmp_path / "does-not-exist.png")},
        )
        plan = _base_plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                content_ref=asset_id,
                x=0.7,
                y=1.0,
                width=8,
                height=3.5,
                fit_mode=ImageFit.CONTAIN,
                crop_policy=CropPolicy.FORBIDDEN,
            ),
            family=LayoutFamily.DRAWING_FOCUS,
        )
        report = LayoutValidationService().validate(
            plan,
            default_presentation_design_system(),
            require_source=False,
            drawing_hero=True,
            asset_context=ctx,
        )
        unresolved = report.issues_for(LAYOUT_UNRESOLVED_ASSET_PATH)
        assert unresolved
        assert unresolved[0].severity == LayoutIssueSeverity.ERROR
        assert report.issues_for(LAYOUT_HERO_ASSET_MISSING)
        assert report.issues_for(LAYOUT_TECHNICAL_DRAWING_MISSING)

    def test_technical_drawing_missing_when_bound_photo(self, tmp_path) -> None:  # noqa: ANN001
        asset_id = str(uuid4())
        photo = tmp_path / "site.jpg"
        photo.write_bytes(b"fake")
        ctx = AssetReferenceContext(
            known_asset_ids=frozenset({asset_id}),
            resolved_paths={asset_id: str(photo)},
            asset_types={asset_id: AssetType.PHOTO.value},
        )
        plan = _base_plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                content_ref=asset_id,
                x=0.7,
                y=1.0,
                width=8,
                height=3.5,
                fit_mode=ImageFit.CONTAIN,
                crop_policy=CropPolicy.FORBIDDEN,
            ),
            family=LayoutFamily.DRAWING_FOCUS,
        )
        report = LayoutValidationService().validate(
            plan,
            default_presentation_design_system(),
            require_source=False,
            drawing_hero=True,
            asset_context=ctx,
        )
        drawing_issues = report.issues_for(LAYOUT_TECHNICAL_DRAWING_MISSING)
        assert drawing_issues
        assert drawing_issues[0].severity == LayoutIssueSeverity.ERROR
        assert not report.valid

    def test_unsupported_image_format_blocks_hero(self, tmp_path) -> None:  # noqa: ANN001
        asset_id = str(uuid4())
        tiff = tmp_path / "plan.tiff"
        tiff.write_bytes(b"fake")
        ctx = AssetReferenceContext(
            known_asset_ids=frozenset({asset_id}),
            resolved_paths={asset_id: str(tiff)},
            asset_types={asset_id: AssetType.DRAWING.value},
        )
        plan = _base_plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                content_ref=asset_id,
                x=0.7,
                y=1.0,
                width=5,
                height=3,
            ),
        )
        report = LayoutValidationService().validate(
            plan,
            default_presentation_design_system(),
            require_source=False,
            asset_context=ctx,
        )
        fmt_issues = report.issues_for(LAYOUT_UNSUPPORTED_IMAGE_FORMAT)
        assert fmt_issues
        assert fmt_issues[0].severity == LayoutIssueSeverity.ERROR
        assert not report.valid

    def test_unsupported_format_warning_for_supporting(self, tmp_path) -> None:  # noqa: ANN001
        asset_id = str(uuid4())
        bmp = tmp_path / "detail.bmp"
        bmp.write_bytes(b"fake")
        ctx = AssetReferenceContext(
            known_asset_ids=frozenset({asset_id}),
            resolved_paths={asset_id: str(bmp)},
            asset_types={asset_id: AssetType.IMAGE.value},
        )
        plan = _base_plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=0.7,
                y=0.45,
                width=8,
                height=0.7,
                style_token="title",
            ),
            LayoutElement(
                id="support",
                role=LayoutElementRole.SUPPORTING_VISUAL,
                content_type=LayoutContentType.IMAGE,
                content_ref=asset_id,
                x=6.0,
                y=1.5,
                width=3,
                height=2,
            ),
        )
        report = LayoutValidationService().validate(
            plan,
            default_presentation_design_system(),
            require_source=False,
            asset_context=ctx,
        )
        fmt_issues = report.issues_for(LAYOUT_UNSUPPORTED_IMAGE_FORMAT)
        assert fmt_issues
        assert fmt_issues[0].severity == LayoutIssueSeverity.WARNING
        assert not any(
            issue.rule_code == LAYOUT_UNSUPPORTED_IMAGE_FORMAT
            and issue.severity
            in {LayoutIssueSeverity.ERROR, LayoutIssueSeverity.CRITICAL}
            for issue in report.issues
        )

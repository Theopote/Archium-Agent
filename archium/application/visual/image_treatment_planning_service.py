"""Image / drawing **layout** treatment planning from DesignSystem + TemplateUsageBrief.

This service only decides fit/crop *policy* and drawing chrome flags for layout.
It is **not** the pixel ImageDerivative pipeline (EXIF/sRGB, focal crop, soft
vignette). That lives in ``ImageTreatmentSpecPlanner`` +
``ImageDerivativeExecutor`` (Pillow V2; Sharp still pending).
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

from archium.application.visual.template_usage_brief_context import (
    TemplateUsageConstraints,
    constraints_from_brief,
)
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import ImageFit, PhotoTreatment, VisualContentType
from archium.domain.visual.template_usage_brief import TemplateUsageBrief


@dataclass(frozen=True)
class ImageTreatmentPlan:
    content_kind: str
    fit_mode: ImageFit
    photo_treatment: PhotoTreatment
    preserve_aspect_ratio: bool
    forbid_cover_crop: bool
    show_legend: bool
    show_north_arrow: bool
    show_scale_bar: bool
    template_usage_brief_id: str | None = None
    template_usage_brief_version: int | None = None
    rationale: str = ""


class ImageTreatmentPlanningService:
    """Decide photo/drawing treatment before layout — brief overrides brand defaults."""

    def plan(
        self,
        *,
        content_type: VisualContentType | str,
        design_system: DesignSystem | None = None,
        brief: TemplateUsageBrief | None = None,
        constraints: TemplateUsageConstraints | None = None,
    ) -> ImageTreatmentPlan:
        resolved = constraints
        if resolved is None and brief is not None:
            resolved = constraints_from_brief(brief)

        kind = (
            content_type.value
            if isinstance(content_type, VisualContentType)
            else str(content_type)
        )
        drawing_kinds = {
            VisualContentType.SITE_PLAN.value,
            VisualContentType.FLOOR_PLAN.value,
            VisualContentType.SECTION.value,
            VisualContentType.ELEVATION.value,
            "drawing",
            "drawing_focus",
        }
        is_drawing = kind in drawing_kinds

        photo_treatment = PhotoTreatment.SUBTLE_UNIFY
        if design_system is not None:
            photo_treatment = design_system.image_style.photo_treatment
        if resolved is not None:
            with contextlib.suppress(ValueError):
                photo_treatment = PhotoTreatment(resolved.photo_treatment_policy)

        if is_drawing:
            fit = ImageFit.CONTAIN
            forbid_cover = True
            if resolved is not None:
                forbid_cover = resolved.forbid_drawing_cover_crop
                if resolved.drawing_fit_must_contain:
                    fit = ImageFit.CONTAIN
            rationale = "图纸处理遵循 TemplateUsageBrief：contain + 禁止 cover/crop"
            return ImageTreatmentPlan(
                content_kind=kind,
                fit_mode=fit,
                photo_treatment=PhotoTreatment.NONE,
                preserve_aspect_ratio=True,
                forbid_cover_crop=forbid_cover,
                show_legend=True,
                show_north_arrow=True,
                show_scale_bar=True,
                template_usage_brief_id=(
                    str(brief.id)
                    if brief is not None
                    else (str(resolved.brief_id) if resolved is not None else None)
                ),
                template_usage_brief_version=(
                    brief.version
                    if brief is not None
                    else (resolved.brief_version if resolved is not None else None)
                ),
                rationale=rationale,
            )

        fit = ImageFit.COVER
        if design_system is not None:
            fit = design_system.image_style.default_fit
        return ImageTreatmentPlan(
            content_kind=kind,
            fit_mode=fit,
            photo_treatment=photo_treatment,
            preserve_aspect_ratio=True,
            forbid_cover_crop=False,
            show_legend=False,
            show_north_arrow=False,
            show_scale_bar=False,
            template_usage_brief_id=(
                str(brief.id)
                if brief is not None
                else (str(resolved.brief_id) if resolved is not None else None)
            ),
            template_usage_brief_version=(
                brief.version
                if brief is not None
                else (resolved.brief_version if resolved is not None else None)
            ),
            rationale="照片处理遵循 DesignSystem / TemplateUsageBrief photo_treatment_policy",
        )

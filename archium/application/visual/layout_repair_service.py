"""Basic layout repair for first-edition validation issues."""

from __future__ import annotations

from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import ImageFit, LayoutValidationStatus
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.validation import (
    LAYOUT_DRAWING_CROPPED,
    LAYOUT_ELEMENT_OUTSIDE_PAGE,
    LAYOUT_ELEMENT_OUTSIDE_SAFE_AREA,
    LAYOUT_IMAGE_DISTORTION,
    LayoutValidationReport,
)
from archium.infrastructure.layout.geometry import safe_area


class LayoutRepairService:
    """Apply conservative geometric repairs — no content deletion or rewrite."""

    def repair(
        self,
        layout_plan: LayoutPlan,
        report: LayoutValidationReport,
        design_system: DesignSystem,
    ) -> LayoutPlan:
        elements = [el.model_copy(deep=True) for el in layout_plan.elements]
        by_id = {el.id: el for el in elements}
        page_w = layout_plan.page_width
        page_h = layout_plan.page_height
        safe = safe_area(design_system)

        for issue in report.issues:
            if not issue.auto_repairable:
                continue
            if issue.rule_code in {
                LAYOUT_ELEMENT_OUTSIDE_PAGE,
                LAYOUT_ELEMENT_OUTSIDE_SAFE_AREA,
            }:
                for element_id in issue.element_ids:
                    element = by_id.get(element_id)
                    if element is None:
                        continue
                    self._clamp_to_rect(
                        element,
                        max_w=page_w if issue.rule_code == LAYOUT_ELEMENT_OUTSIDE_PAGE else safe.width,
                        max_h=page_h if issue.rule_code == LAYOUT_ELEMENT_OUTSIDE_PAGE else safe.height,
                        origin_x=0.0 if issue.rule_code == LAYOUT_ELEMENT_OUTSIDE_PAGE else safe.x,
                        origin_y=0.0 if issue.rule_code == LAYOUT_ELEMENT_OUTSIDE_PAGE else safe.y,
                        page_w=page_w,
                        page_h=page_h,
                    )
            elif issue.rule_code == LAYOUT_IMAGE_DISTORTION:
                for element_id in issue.element_ids:
                    element = by_id.get(element_id)
                    if element is not None:
                        element.fit_mode = ImageFit.CONTAIN
            elif issue.rule_code == LAYOUT_DRAWING_CROPPED:
                for element_id in issue.element_ids:
                    element = by_id.get(element_id)
                    if element is not None:
                        element.fit_mode = ImageFit.CONTAIN
                        from archium.domain.visual.enums import CropPolicy

                        element.crop_policy = CropPolicy.FORBIDDEN

        repaired = layout_plan.model_copy(
            update={
                "elements": list(by_id.values()),
                "validation_status": LayoutValidationStatus.REPAIRED,
                "version": layout_plan.version + 1,
            }
        )
        repaired.touch()
        return repaired

    @staticmethod
    def _clamp_to_rect(
        element: LayoutElement,
        *,
        max_w: float,
        max_h: float,
        origin_x: float,
        origin_y: float,
        page_w: float,
        page_h: float,
    ) -> None:
        element.width = min(element.width, max_w)
        element.height = min(element.height, max_h)
        element.x = min(max(element.x, origin_x), origin_x + max_w - element.width)
        element.y = min(max(element.y, origin_y), origin_y + max_h - element.height)
        element.x = min(max(0.0, element.x), max(0.0, page_w - element.width))
        element.y = min(max(0.0, element.y), max(0.0, page_h - element.height))

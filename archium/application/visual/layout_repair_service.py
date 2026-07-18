"""Conservative layout repair for auto-repairable validation issues."""

from __future__ import annotations

from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import (
    CropPolicy,
    ImageFit,
    LayoutElementRole,
    LayoutValidationStatus,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.validation import (
    LAYOUT_DRAWING_CROPPED,
    LAYOUT_ELEMENT_OUTSIDE_PAGE,
    LAYOUT_ELEMENT_OUTSIDE_SAFE_AREA,
    LAYOUT_ELEMENT_OVERLAP,
    LAYOUT_FONT_TOO_SMALL,
    LAYOUT_HERO_NOT_DOMINANT,
    LAYOUT_IMAGE_DISTORTION,
    LAYOUT_INCONSISTENT_ALIGNMENT,
    LAYOUT_TEXT_OVERFLOW,
    LayoutValidationReport,
)
from archium.infrastructure.layout.geometry import Rect, occupied_area, safe_area, whitespace_ratio
from archium.infrastructure.layout.text_measurement import TextMeasurementService

# Prefer larger readable tokens when repairing FONT_TOO_SMALL.
_STYLE_UPGRADE: dict[str, str] = {
    "footnote": "source",
    "source": "caption",
    "caption": "body",
    "body": "subtitle",
    "subtitle": "heading",
    "heading": "title",
    "metric": "heading",
}

_GAP = 0.08


class LayoutRepairService:
    """Apply geometric / token repairs — no content deletion or copy rewrite."""

    def __init__(self, text_measurement: TextMeasurementService | None = None) -> None:
        self._text = text_measurement or TextMeasurementService()

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
            code = issue.rule_code
            if code in {LAYOUT_ELEMENT_OUTSIDE_PAGE, LAYOUT_ELEMENT_OUTSIDE_SAFE_AREA}:
                use_page = code == LAYOUT_ELEMENT_OUTSIDE_PAGE
                for element_id in issue.element_ids:
                    element = by_id.get(element_id)
                    if element is None:
                        continue
                    self._clamp_to_rect(
                        element,
                        max_w=page_w if use_page else safe.width,
                        max_h=page_h if use_page else safe.height,
                        origin_x=0.0 if use_page else safe.x,
                        origin_y=0.0 if use_page else safe.y,
                        page_w=page_w,
                        page_h=page_h,
                    )
            elif code == LAYOUT_ELEMENT_OVERLAP:
                self._repair_overlap(issue.element_ids, by_id, safe=safe, page_w=page_w, page_h=page_h)
            elif code == LAYOUT_IMAGE_DISTORTION:
                for element_id in issue.element_ids:
                    element = by_id.get(element_id)
                    if element is not None:
                        element.fit_mode = ImageFit.CONTAIN
            elif code == LAYOUT_DRAWING_CROPPED:
                for element_id in issue.element_ids:
                    element = by_id.get(element_id)
                    if element is not None:
                        element.fit_mode = ImageFit.CONTAIN
                        element.crop_policy = CropPolicy.FORBIDDEN
            elif code == LAYOUT_FONT_TOO_SMALL:
                for element_id in issue.element_ids:
                    element = by_id.get(element_id)
                    if element is not None:
                        self._upgrade_style_token(element)
            elif code == LAYOUT_TEXT_OVERFLOW:
                for element_id in issue.element_ids:
                    element = by_id.get(element_id)
                    if element is None or element.locked:
                        continue
                    self._expand_text_box(
                        element,
                        design_system=design_system,
                        safe=safe,
                        page_w=page_w,
                        page_h=page_h,
                        others=list(by_id.values()),
                    )
            elif code == LAYOUT_HERO_NOT_DOMINANT:
                for element_id in issue.element_ids:
                    element = by_id.get(element_id)
                    if element is None:
                        continue
                    self._enlarge_hero(
                        element,
                        plan=layout_plan,
                        design_system=design_system,
                        safe=safe,
                        by_id=by_id,
                    )
            elif code == LAYOUT_INCONSISTENT_ALIGNMENT:
                self._align_group(issue.element_ids, by_id)

        ordered = [by_id[el.id] for el in layout_plan.elements if el.id in by_id]
        occupied = occupied_area([Rect(el.x, el.y, el.width, el.height) for el in ordered])
        repaired = layout_plan.model_copy(
            update={
                "elements": ordered,
                "whitespace_ratio": whitespace_ratio(design_system.page, occupied),
                "validation_status": LayoutValidationStatus.REPAIRED,
                "version": layout_plan.version + 1,
            }
        )
        repaired.touch()
        return repaired

    def _repair_overlap(
        self,
        element_ids: list[str],
        by_id: dict[str, LayoutElement],
        *,
        safe: Rect,
        page_w: float,
        page_h: float,
    ) -> None:
        if len(element_ids) < 2:
            return
        left = by_id.get(element_ids[0])
        right = by_id.get(element_ids[1])
        if left is None or right is None:
            return
        mover, anchor = self._pick_mover(left, right)
        if mover is None:
            # Both locked — shrink the second slightly if possible.
            target = right if not right.locked else left
            if target.locked:
                return
            target.height = max(0.2, target.height * 0.85)
            target.width = max(0.2, target.width * 0.95)
            self._clamp_to_rect(
                target,
                max_w=safe.width,
                max_h=safe.height,
                origin_x=safe.x,
                origin_y=safe.y,
                page_w=page_w,
                page_h=page_h,
            )
            return

        overlap_y = min(mover.bottom, anchor.bottom) - max(mover.y, anchor.y)
        overlap_x = min(mover.right, anchor.right) - max(mover.x, anchor.x)
        if overlap_y <= 0 or overlap_x <= 0:
            return

        min_h = 0.25
        min_w = 0.35
        proposed_y = anchor.bottom + _GAP
        room_below = safe.bottom - proposed_y
        proposed_x = anchor.right + _GAP
        room_right = safe.right - proposed_x

        if room_below >= min_h:
            mover.y = proposed_y
            mover.height = min(mover.height, room_below)
        elif room_right >= min_w:
            mover.x = proposed_x
            mover.width = min(mover.width, room_right)
        else:
            # Shrink into the non-overlapping slice above/ beside the anchor.
            if mover.y < anchor.y:
                mover.height = max(min_h, anchor.y - _GAP - mover.y)
            else:
                mover.height = max(min_h, mover.height - overlap_y - _GAP)
                mover.width = max(min_w, mover.width * 0.9)

        self._clamp_to_rect(
            mover,
            max_w=safe.width,
            max_h=safe.height,
            origin_x=safe.x,
            origin_y=safe.y,
            page_w=page_w,
            page_h=page_h,
        )

    @staticmethod
    def _pick_mover(
        left: LayoutElement, right: LayoutElement
    ) -> tuple[LayoutElement | None, LayoutElement]:
        if left.locked and right.locked:
            return None, left
        if left.locked:
            return right, left
        if right.locked:
            return left, right
        # Move the lower / later element to preserve hierarchy at top.
        if right.y >= left.y:
            return right, left
        return left, right

    def _upgrade_style_token(self, element: LayoutElement) -> None:
        current = element.style_token or "body"
        element.style_token = _STYLE_UPGRADE.get(current, "body")

    def _expand_text_box(
        self,
        element: LayoutElement,
        *,
        design_system: DesignSystem,
        safe: Rect,
        page_w: float,
        page_h: float,
        others: list[LayoutElement],
    ) -> None:
        if not element.text_content:
            return
        token_name = element.style_token or "body"
        style = getattr(design_system.typography, token_name, design_system.typography.body)

        # Prefer expanding within the remaining safe area under the current top.
        candidates = [
            (element.x, element.y, min(safe.right - element.x, safe.width), safe.bottom - element.y),
            (safe.x, element.y, safe.width, safe.bottom - element.y),
            (safe.x, safe.y, safe.width, safe.height),
        ]
        for x, y, width, height in candidates:
            if width < 0.3 or height < 0.2:
                continue
            if self._text.fits(
                element.text_content,
                box_width_in=width,
                box_height_in=height,
                style=style,
            ):
                element.x = x
                element.y = y
                element.width = width
                element.height = height
                break
        else:
            # Nothing fits — take the largest safe box as best effort.
            element.x = safe.x
            element.y = safe.y
            element.width = safe.width
            element.height = safe.height

        self._clamp_to_rect(
            element,
            max_w=safe.width,
            max_h=safe.height,
            origin_x=safe.x,
            origin_y=safe.y,
            page_w=page_w,
            page_h=page_h,
        )
        # Avoid introducing overlap with locked neighbors when expanding.
        for other in others:
            if other.id == element.id or not other.locked:
                continue
            if Rect(element.x, element.y, element.width, element.height).overlaps(
                Rect(other.x, other.y, other.width, other.height),
                tolerance=0.0,
            ):
                element.height = max(0.2, other.y - _GAP - element.y)

    def _enlarge_hero(
        self,
        hero: LayoutElement,
        *,
        plan: LayoutPlan,
        design_system: DesignSystem,
        safe: Rect,
        by_id: dict[str, LayoutElement],
    ) -> None:
        min_ratio = design_system.thresholds.min_hero_area_ratio
        target_area = min_ratio * safe.area * 1.02
        if hero.area + 1e-6 >= target_area:
            return

        # Keep clear of title strip when present.
        top = safe.y
        titles = [el for el in by_id.values() if el.role == LayoutElementRole.TITLE]
        if titles:
            top = max(top, max(t.bottom for t in titles) + _GAP)

        available = Rect(safe.x, top, safe.width, max(0.5, safe.bottom - top))
        scale = (target_area / max(hero.area, 1e-6)) ** 0.5
        new_w = min(available.width, max(hero.width * scale, hero.width))
        new_h = min(available.height, max(hero.height * scale, hero.height))
        # Prefer expanding within available rect from current top-left, clamped.
        hero.width = new_w
        hero.height = new_h
        hero.x = min(max(hero.x, available.x), available.right - hero.width)
        hero.y = min(max(hero.y, available.y), available.bottom - hero.height)
        # If still short, fill available box.
        if hero.area + 1e-6 < target_area:
            hero.x = available.x
            hero.y = available.y
            hero.width = available.width
            hero.height = available.height

    def _align_group(self, element_ids: list[str], by_id: dict[str, LayoutElement]) -> None:
        group = [by_id[eid] for eid in element_ids if eid in by_id and not by_id[eid].locked]
        if len(group) < 2:
            return
        widths = sorted(el.width for el in group)
        median_w = widths[len(widths) // 2]
        for element in group:
            element.width = median_w
        # If mostly a single row, equalize tops; if mostly a column, equalize lefts.
        ys = [el.y for el in group]
        xs = [el.x for el in group]
        if max(ys) - min(ys) <= max(xs) - min(xs):
            top = min(ys)
            for element in group:
                element.y = top
        else:
            left = min(xs)
            for element in group:
                element.x = left

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
        element.width = min(max(element.width, 0.05), max_w)
        element.height = min(max(element.height, 0.05), max_h)
        element.x = min(max(element.x, origin_x), origin_x + max_w - element.width)
        element.y = min(max(element.y, origin_y), origin_y + max_h - element.height)
        element.x = min(max(0.0, element.x), max(0.0, page_w - element.width))
        element.y = min(max(0.0, element.y), max(0.0, page_h - element.height))

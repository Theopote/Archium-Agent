"""Conservative layout repair for auto-repairable validation issues."""

from __future__ import annotations

from archium.domain.visual.design_system import DesignSystem, TextStyleToken
from archium.domain.visual.enums import (
    CropPolicy,
    ImageFit,
    LayoutElementRole,
    LayoutValidationStatus,
    OverflowPolicy,
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
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
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

# Prefer more compact tokens when repairing TEXT_OVERFLOW (still threshold-checked).
_STYLE_COMPACT: dict[str, str] = {
    "display": "title",
    "title": "heading",
    "heading": "subtitle",
    "subtitle": "body",
    "body": "caption",
    "metric": "body",
    "caption": "source",
}

_GAP = 0.08
_MIN_TEXT_W = 0.35
_MIN_TEXT_H = 0.2


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
        overflow_policy = layout_plan.overflow_policy
        layout_variant = layout_plan.layout_variant
        unresolved_overflow_ids: list[str] = []

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
                    fixed = self._repair_text_overflow(
                        element,
                        design_system=design_system,
                        safe=safe,
                        page_w=page_w,
                        page_h=page_h,
                        others=list(by_id.values()),
                    )
                    if not fixed:
                        unresolved_overflow_ids.append(element_id)
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

        if unresolved_overflow_ids:
            # Escalate: try another family variant next cycle, and flag split.
            layout_variant = self._next_layout_variant(
                layout_plan.layout_family, layout_variant
            )
            overflow_policy = OverflowPolicy.SPLIT

        ordered = [by_id[el.id] for el in layout_plan.elements if el.id in by_id]
        occupied = occupied_area([Rect(el.x, el.y, el.width, el.height) for el in ordered])
        repaired = layout_plan.model_copy(
            update={
                "elements": ordered,
                "whitespace_ratio": whitespace_ratio(design_system.page, occupied),
                "validation_status": LayoutValidationStatus.REPAIRED,
                "version": layout_plan.version + 1,
                "overflow_policy": overflow_policy,
                "layout_variant": layout_variant,
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

    def _repair_text_overflow(
        self,
        element: LayoutElement,
        *,
        design_system: DesignSystem,
        safe: Rect,
        page_w: float,
        page_h: float,
        others: list[LayoutElement],
    ) -> bool:
        """Fix text overflow without claiming the whole safe area.

        Priority:
        1. Expand into adjacent free space (avoid *all* neighbors)
        2. Reduce inter-element padding (tighter gap)
        3. Fine-tune box to the minimum height/width that fits
        4. Switch to a more compact but still compliant style token
        5–6. Caller escalates to variant change + split suggestion
        """
        if not element.text_content:
            return True

        neighbors = [el for el in others if el.id != element.id]
        original = (
            element.x,
            element.y,
            element.width,
            element.height,
            element.style_token,
        )

        # Gap schedules: normal spacing, then reduced padding.
        gap_schedule = (
            max(_GAP, design_system.spacing.sm),
            max(design_system.spacing.xs, _GAP * 0.5),
        )
        token_chain = self._compact_token_chain(
            element, design_system=design_system
        )

        for token_name in token_chain:
            style = getattr(
                design_system.typography, token_name, design_system.typography.body
            )
            for gap in gap_schedule:
                if self._try_fit_in_adjacent_space(
                    element,
                    text=element.text_content,
                    style=style,
                    safe=safe,
                    neighbors=neighbors,
                    gap=gap,
                ):
                    element.style_token = token_name
                    self._clamp_to_rect(
                        element,
                        max_w=safe.width,
                        max_h=safe.height,
                        origin_x=safe.x,
                        origin_y=safe.y,
                        page_w=page_w,
                        page_h=page_h,
                    )
                    # Re-check: clamp must not reintroduce overflow or overlaps.
                    if self._text_fits(element, style) and not self._overlaps_any(
                        element, neighbors, gap=0.0
                    ):
                        return True

        # Restore geometry — do not leave a half-applied full-safe takeover.
        element.x, element.y, element.width, element.height, element.style_token = (
            original
        )
        return False

    def _compact_token_chain(
        self, element: LayoutElement, *, design_system: DesignSystem
    ) -> list[str]:
        """Current token first, then progressively more compact compliant tokens."""
        start = element.style_token or "body"
        chain = [start]
        seen = {start}
        current = start
        for _ in range(6):
            nxt = _STYLE_COMPACT.get(current)
            if nxt is None or nxt in seen:
                break
            style = getattr(design_system.typography, nxt, None)
            if style is None:
                break
            if not self._token_meets_min_font(
                element, token_name=nxt, style=style, design_system=design_system
            ):
                break
            chain.append(nxt)
            seen.add(nxt)
            current = nxt
        return chain

    @staticmethod
    def _token_meets_min_font(
        element: LayoutElement,
        *,
        token_name: str,
        style: TextStyleToken,
        design_system: DesignSystem,
    ) -> bool:
        thresholds = design_system.thresholds
        minimum = thresholds.min_body_font_pt
        if element.role == LayoutElementRole.CAPTION or token_name == "caption":
            minimum = thresholds.min_caption_font_pt
        if element.role == LayoutElementRole.SOURCE or token_name in {
            "source",
            "footnote",
        }:
            minimum = thresholds.min_source_font_pt
        # Body / lead / title roles must not drop below body minimum.
        if element.role in {
            LayoutElementRole.BODY_TEXT,
            LayoutElementRole.LEAD_STATEMENT,
            LayoutElementRole.TITLE,
            LayoutElementRole.SUBTITLE,
        }:
            minimum = max(minimum, thresholds.min_body_font_pt)
        return style.font_size + 1e-6 >= minimum

    def _try_fit_in_adjacent_space(
        self,
        element: LayoutElement,
        *,
        text: str,
        style: TextStyleToken,
        safe: Rect,
        neighbors: list[LayoutElement],
        gap: float,
    ) -> bool:
        """Grow into free adjacent space, then shrink to the minimum fitting size."""
        room = self._directional_room(element, neighbors, safe=safe, gap=gap)
        # Candidate boxes ordered by invasiveness (local → wider strip, never full safe).
        candidates: list[tuple[float, float, float, float]] = []

        # 3. Fine-tune height at current width (down / up).
        need_h = self._needed_height(text, element.width, style)
        if need_h <= element.height + room["down"] + 1e-6:
            candidates.append(
                (element.x, element.y, element.width, max(element.height, need_h))
            )
        if need_h <= element.height + room["up"] + 1e-6:
            new_h = max(element.height, need_h)
            candidates.append(
                (element.x, element.y + element.height - new_h, element.width, new_h)
            )

        # 1. Expand into adjacent whitespace (width then height).
        max_w = element.width + room["left"] + room["right"]
        max_h_down = element.height + room["down"]
        max_h = element.height + room["up"] + room["down"]

        for width in self._width_steps(element.width, max_w):
            need = self._needed_height(text, width, style)
            # Prefer growing downward from the current top.
            if need <= max_h_down + 1e-6:
                x = element.x
                # Prefer expanding right first; use left only if needed.
                extra_w = width - element.width
                if extra_w > room["right"] + 1e-9:
                    x = element.x - (extra_w - room["right"])
                candidates.append((x, element.y, width, need))
            elif need <= max_h + 1e-6:
                x = element.x
                extra_w = width - element.width
                if extra_w > room["right"] + 1e-9:
                    x = element.x - (extra_w - room["right"])
                y = element.y - min(room["up"], max(0.0, need - max_h_down))
                candidates.append((x, y, width, need))

        # Also try the max free band anchored at the element (still not full safe).
        free = self._seeded_free_band(element, neighbors, safe=safe, gap=gap)
        if free.width >= _MIN_TEXT_W and free.height >= _MIN_TEXT_H:
            need = self._needed_height(text, free.width, style)
            if need <= free.height + 1e-6:
                candidates.append((free.x, free.y, free.width, need))
            # Slightly narrower than full free width can still help wrapping.
            for width in self._width_steps(element.width, free.width):
                need = self._needed_height(text, width, style)
                if need <= free.height + 1e-6:
                    candidates.append((free.x, free.y, width, need))

        # Prefer smaller area growth.
        candidates.sort(
            key=lambda box: (box[2] * box[3], box[2] - element.width, box[3] - element.height)
        )

        for x, y, width, height in candidates:
            if width < _MIN_TEXT_W or height < _MIN_TEXT_H:
                continue
            probe = element.model_copy(
                update={"x": x, "y": y, "width": width, "height": height}
            )
            if not self._text_fits(probe, style):
                continue
            if self._overlaps_any(probe, neighbors, gap=gap):
                continue
            if not self._within_safe(probe, safe):
                continue
            element.x = x
            element.y = y
            element.width = width
            element.height = height
            return True
        return False

    def _directional_room(
        self,
        element: LayoutElement,
        neighbors: list[LayoutElement],
        *,
        safe: Rect,
        gap: float,
    ) -> dict[str, float]:
        room = {
            "left": max(0.0, element.x - safe.x),
            "right": max(0.0, safe.right - element.right),
            "up": max(0.0, element.y - safe.y),
            "down": max(0.0, safe.bottom - element.bottom),
        }
        for other in neighbors:
            vert_overlap = not (
                element.bottom <= other.y + 1e-9 or other.bottom <= element.y + 1e-9
            )
            horiz_overlap = not (
                element.right <= other.x + 1e-9 or other.right <= element.x + 1e-9
            )
            if vert_overlap:
                if other.right <= element.x + 1e-9:
                    room["left"] = min(
                        room["left"], max(0.0, element.x - other.right - gap)
                    )
                elif other.x >= element.right - 1e-9:
                    room["right"] = min(
                        room["right"], max(0.0, other.x - element.right - gap)
                    )
                else:
                    # Already colliding in this band — no lateral expansion.
                    room["left"] = 0.0
                    room["right"] = 0.0
            if horiz_overlap:
                if other.bottom <= element.y + 1e-9:
                    room["up"] = min(
                        room["up"], max(0.0, element.y - other.bottom - gap)
                    )
                elif other.y >= element.bottom - 1e-9:
                    room["down"] = min(
                        room["down"], max(0.0, other.y - element.bottom - gap)
                    )
                else:
                    room["up"] = 0.0
                    room["down"] = 0.0
        return room

    def _seeded_free_band(
        self,
        element: LayoutElement,
        neighbors: list[LayoutElement],
        *,
        safe: Rect,
        gap: float,
    ) -> Rect:
        """Largest axis-aligned free band that still contains the element seed."""
        room = self._directional_room(element, neighbors, safe=safe, gap=gap)
        return Rect(
            x=element.x - room["left"],
            y=element.y - room["up"],
            width=element.width + room["left"] + room["right"],
            height=element.height + room["up"] + room["down"],
        )

    @staticmethod
    def _width_steps(current: float, maximum: float) -> list[float]:
        if maximum <= current + 1e-9:
            return [current]
        steps = [current]
        # Grow gradually — never jump straight to the max free width first.
        cursor = current
        while cursor < maximum - 1e-9:
            cursor = min(maximum, cursor + max(0.25, (maximum - current) / 4))
            steps.append(cursor)
        if steps[-1] < maximum - 1e-9:
            steps.append(maximum)
        # De-dupe while preserving order.
        out: list[float] = []
        for value in steps:
            if not out or abs(out[-1] - value) > 1e-9:
                out.append(value)
        return out

    def _needed_height(self, text: str, width: float, style: TextStyleToken) -> float:
        lines = self._text.estimate_lines(text, box_width_in=width, style=style)
        return max(_MIN_TEXT_H, lines * (style.line_height / 72.0))

    def _text_fits(self, element: LayoutElement, style: TextStyleToken) -> bool:
        if not element.text_content:
            return True
        return self._text.fits(
            element.text_content,
            box_width_in=element.width,
            box_height_in=element.height,
            style=style,
        )

    @staticmethod
    def _overlaps_any(
        element: LayoutElement, neighbors: list[LayoutElement], *, gap: float
    ) -> bool:
        probe = Rect(element.x, element.y, element.width, element.height)
        for other in neighbors:
            other_rect = Rect(other.x, other.y, other.width, other.height)
            # Enforce gap by inflating the other rect slightly.
            padded = Rect(
                other_rect.x - gap,
                other_rect.y - gap,
                other_rect.width + 2 * gap,
                other_rect.height + 2 * gap,
            )
            if probe.overlaps(padded, tolerance=0.0):
                return True
        return False

    @staticmethod
    def _within_safe(element: LayoutElement, safe: Rect) -> bool:
        return (
            element.x + 1e-6 >= safe.x
            and element.y + 1e-6 >= safe.y
            and element.right <= safe.right + 1e-6
            and element.bottom <= safe.bottom + 1e-6
        )

    @staticmethod
    def _next_layout_variant(family, current: str) -> str:
        variants = list(get_layout_family_registry().get(family).supported_variants)
        if len(variants) < 2:
            return current
        try:
            idx = variants.index(current)
        except ValueError:
            return variants[0]
        return variants[(idx + 1) % len(variants)]

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

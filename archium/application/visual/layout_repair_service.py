"""Conservative layout repair for auto-repairable validation issues."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from archium.domain.visual.design_system import DesignSystem, TextStyleToken
from archium.domain.visual.enums import (
    CropPolicy,
    ImageFit,
    LayoutElementRole,
    LayoutValidationStatus,
    OverflowPolicy,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.text_style import (
    clamp_font_size_override,
    next_larger_token,
    resolve_text_style,
    role_min_font_pt,
    smaller_compliant_tokens,
    typography_tokens_by_size,
)
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

_GAP = 0.08
_MIN_TEXT_W = 0.35
_MIN_TEXT_H = 0.2
_SNAPSHOT_KEYS = (
    "x",
    "y",
    "width",
    "height",
    "style_token",
    "font_size_override",
    "fit_mode",
    "crop_policy",
)
_HERO_REFLOW_ROLES = frozenset(
    {
        LayoutElementRole.BODY_TEXT,
        LayoutElementRole.SUPPORTING_VISUAL,
        LayoutElementRole.ANNOTATION,
        LayoutElementRole.CAPTION,
        LayoutElementRole.METRIC,
    }
)


@dataclass
class ElementRepairDiff:
    """Before/after snapshot for one repaired element."""

    element_id: str
    before: dict[str, Any]
    after: dict[str, Any]

    @property
    def changed_fields(self) -> list[str]:
        return sorted(
            key for key in _SNAPSHOT_KEYS if self.before.get(key) != self.after.get(key)
        )


@dataclass
class LayoutRepairResult:
    """Repair output with plan + per-element diffs (repair contract)."""

    plan: LayoutPlan
    diffs: list[ElementRepairDiff] = field(default_factory=list)
    reading_order_preserved: bool = True

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "layout_plan_id": str(self.plan.id),
            "version": self.plan.version,
            "reading_order_preserved": self.reading_order_preserved,
            "diff_count": len(self.diffs),
            "diffs": [
                {
                    "element_id": item.element_id,
                    "changed_fields": item.changed_fields,
                    "before": item.before,
                    "after": item.after,
                }
                for item in self.diffs
            ],
        }


class LayoutRepairService:
    """Apply geometric / token repairs — no content deletion or copy rewrite."""

    def __init__(self, text_measurement: TextMeasurementService | None = None) -> None:
        self._text = text_measurement or TextMeasurementService()

    def repair(
        self,
        layout_plan: LayoutPlan,
        report: LayoutValidationReport,
        design_system: DesignSystem,
    ) -> LayoutRepairResult:
        elements = [el.model_copy(deep=True) for el in layout_plan.elements]
        by_id = {el.id: el for el in elements}
        page_w = layout_plan.page_width
        page_h = layout_plan.page_height
        safe = safe_area(design_system)
        overflow_policy = layout_plan.overflow_policy
        layout_variant = layout_plan.layout_variant
        unresolved_overflow_ids: list[str] = []
        reading_order = list(layout_plan.reading_order)
        before_snapshots = {el.id: self._snapshot_element(el) for el in elements}

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
                self._repair_overlap(
                    issue.element_ids,
                    by_id,
                    safe=safe,
                    page_w=page_w,
                    page_h=page_h,
                    reading_order=reading_order,
                )
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
                        self._upgrade_font_size(element, design_system)
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
                        page_w=page_w,
                        page_h=page_h,
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
                "reading_order": reading_order,
                "whitespace_ratio": whitespace_ratio(design_system.page, occupied),
                "validation_status": LayoutValidationStatus.REPAIRED,
                "version": layout_plan.version + 1,
                "overflow_policy": overflow_policy,
                "layout_variant": layout_variant,
            }
        )
        repaired.touch()

        diffs: list[ElementRepairDiff] = []
        for element in ordered:
            after = self._snapshot_element(element)
            before = before_snapshots.get(element.id, {})
            if after != before:
                diffs.append(
                    ElementRepairDiff(
                        element_id=element.id, before=before, after=after
                    )
                )

        return LayoutRepairResult(
            plan=repaired,
            diffs=diffs,
            reading_order_preserved=list(repaired.reading_order) == reading_order,
        )

    @staticmethod
    def _snapshot_element(element: LayoutElement) -> dict[str, Any]:
        return {
            "x": round(element.x, 4),
            "y": round(element.y, 4),
            "width": round(element.width, 4),
            "height": round(element.height, 4),
            "style_token": element.style_token,
            "font_size_override": element.font_size_override,
            "fit_mode": element.fit_mode.value if element.fit_mode else None,
            "crop_policy": element.crop_policy.value if element.crop_policy else None,
        }

    def _repair_overlap(
        self,
        element_ids: list[str],
        by_id: dict[str, LayoutElement],
        *,
        safe: Rect,
        page_w: float,
        page_h: float,
        reading_order: list[str],
    ) -> None:
        if len(element_ids) < 2:
            return
        left = by_id.get(element_ids[0])
        right = by_id.get(element_ids[1])
        if left is None or right is None:
            return
        mover, anchor = self._pick_mover(left, right, reading_order=reading_order)
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
        left: LayoutElement,
        right: LayoutElement,
        *,
        reading_order: list[str],
    ) -> tuple[LayoutElement | None, LayoutElement]:
        """Choose which element to move — prefer later reading_order, never locked."""
        if left.locked and right.locked:
            return None, left
        if left.locked:
            return right, left
        if right.locked:
            return left, right

        try:
            left_rank = reading_order.index(left.id)
            right_rank = reading_order.index(right.id)
        except ValueError:
            left_rank = right_rank = -1

        if left_rank >= 0 and right_rank >= 0:
            # Move the later reader so earlier hierarchy stays put.
            if right_rank >= left_rank:
                return right, left
            return left, right

        # Fallback: move the lower / later element on the page.
        if right.y >= left.y:
            return right, left
        return left, right

    def _upgrade_font_size(
        self, element: LayoutElement, design_system: DesignSystem
    ) -> None:
        """Raise font size using real DesignSystem sizes — never token-name guesses.

        1. Pick the smallest named token larger than the current effective size
           that still meets the role minimum.
        2. If none exists, set ``font_size_override`` to the role minimum
           (clamped by the largest available token size).
        """
        minimum = role_min_font_pt(element.role, design_system.thresholds)
        larger = next_larger_token(
            element, typography=design_system.typography, minimum_pt=minimum
        )
        if larger is not None:
            element.style_token = larger
            element.font_size_override = None
            return

        # No larger named token — bump override to the legal floor.
        # Thresholds win over the largest named token when the design system is
        # inconsistent (all tokens below the role minimum).
        tokens = typography_tokens_by_size(design_system.typography)
        max_named = tokens[-1][1].font_size if tokens else minimum
        element.font_size_override = clamp_font_size_override(
            minimum,
            minimum_pt=minimum,
            maximum_pt=max(max_named, minimum),
        )

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
        4. Switch to a more compact but still compliant style token (by real size)
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
            element.font_size_override,
        )

        # Gap schedules: normal spacing, then reduced padding.
        gap_schedule = (
            max(_GAP, design_system.spacing.sm),
            max(design_system.spacing.xs, _GAP * 0.5),
        )
        token_chain = self._compact_token_chain(element, design_system=design_system)

        for token_name in token_chain:
            # Compact steps use the named token size (clear any prior override).
            probe = element.model_copy(
                update={"style_token": token_name, "font_size_override": None}
            )
            style = resolve_text_style(probe, design_system.typography)
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
                    element.font_size_override = None
                    self._clamp_to_rect(
                        element,
                        max_w=safe.width,
                        max_h=safe.height,
                        origin_x=safe.x,
                        origin_y=safe.y,
                        page_w=page_w,
                        page_h=page_h,
                    )
                    if self._text_fits(element, style) and not self._overlaps_any(
                        element, neighbors, gap=0.0
                    ):
                        return True

        # Restore geometry — do not leave a half-applied full-safe takeover.
        (
            element.x,
            element.y,
            element.width,
            element.height,
            element.style_token,
            element.font_size_override,
        ) = original
        return False

    def _compact_token_chain(
        self, element: LayoutElement, *, design_system: DesignSystem
    ) -> list[str]:
        """Current token first, then progressively smaller compliant tokens by size."""
        start = element.style_token or "body"
        minimum = role_min_font_pt(element.role, design_system.thresholds)
        smaller = smaller_compliant_tokens(
            element,
            typography=design_system.typography,
            minimum_pt=minimum,
        )
        chain = [start]
        for name in smaller:
            if name not in chain:
                chain.append(name)
        return chain

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
        page_w: float,
        page_h: float,
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

        # Contract: enlarging hero must reflow supporting content out of the hero rect.
        self._reflow_supporting_after_hero(
            hero,
            by_id=by_id,
            reading_order=list(plan.reading_order),
            safe=safe,
            page_w=page_w,
            page_h=page_h,
        )

    def _reflow_supporting_after_hero(
        self,
        hero: LayoutElement,
        *,
        by_id: dict[str, LayoutElement],
        reading_order: list[str],
        safe: Rect,
        page_w: float,
        page_h: float,
    ) -> None:
        """Push unlocked supporting elements clear of the enlarged hero.

        Order follows ``reading_order`` so earlier hierarchy is placed first;
        later elements cascade below/right of both hero and already-moved peers.
        """
        ordered_ids = list(reading_order)
        for element_id in by_id:
            if element_id not in ordered_ids:
                ordered_ids.append(element_id)

        for element_id in ordered_ids:
            element = by_id.get(element_id)
            if element is None or element.id == hero.id or element.locked:
                continue
            if element.role not in _HERO_REFLOW_ROLES:
                continue
            if not self._rects_overlap(element, hero, gap=_GAP):
                continue

            room_below = safe.bottom - (hero.bottom + _GAP)
            room_right = safe.right - (hero.right + _GAP)
            placed = False

            if room_below >= _MIN_TEXT_H:
                element.y = hero.bottom + _GAP
                element.height = min(element.height, room_below)
                placed = True
            elif room_right >= _MIN_TEXT_W:
                element.x = hero.right + _GAP
                element.width = min(element.width, room_right)
                placed = True
            else:
                # Compact into remaining strip below the title / above page bottom.
                element.y = min(element.y, safe.bottom - _MIN_TEXT_H)
                element.height = max(_MIN_TEXT_H, min(element.height, room_below or _MIN_TEXT_H))
                element.width = max(_MIN_TEXT_W, min(element.width, safe.width * 0.45))
                element.x = max(safe.x, min(element.x, safe.right - element.width))
                placed = True

            if placed:
                # Avoid stacking on peers already reflowed in reading order.
                peers = [
                    by_id[peer_id]
                    for peer_id in ordered_ids
                    if peer_id in by_id
                    and peer_id not in {element.id, hero.id}
                    and ordered_ids.index(peer_id) < ordered_ids.index(element_id)
                ]
                for peer in peers:
                    if peer.locked or peer.role not in _HERO_REFLOW_ROLES:
                        continue
                    if not self._rects_overlap(element, peer, gap=_GAP):
                        continue
                    element.y = peer.bottom + _GAP
                    element.height = min(
                        element.height, max(_MIN_TEXT_H, safe.bottom - element.y)
                    )

                self._clamp_to_rect(
                    element,
                    max_w=safe.width,
                    max_h=safe.height,
                    origin_x=safe.x,
                    origin_y=safe.y,
                    page_w=page_w,
                    page_h=page_h,
                )

    @staticmethod
    def _rects_overlap(
        left: LayoutElement, right: LayoutElement, *, gap: float = 0.0
    ) -> bool:
        probe = Rect(left.x, left.y, left.width, left.height)
        other = Rect(
            right.x - gap,
            right.y - gap,
            right.width + 2 * gap,
            right.height + 2 * gap,
        )
        return probe.overlaps(other, tolerance=0.0)

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

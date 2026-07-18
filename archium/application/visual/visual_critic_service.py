"""Read-only Visual Critic — Visual Quality heuristics (no auto-repair).

v0 evaluates composed pages using LayoutPlan geometry as a soft prior, and
optionally a screenshot PNG when available. Findings are advisory only and
must never mutate layouts or unlock/block formal PPTX export.
"""

from __future__ import annotations

import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from archium.domain.visual.critic import (
    CRITIC_COLOR_CHAOS,
    CRITIC_FOCUS_UNCLEAR,
    CRITIC_HERO_WEAK,
    CRITIC_MECHANICAL,
    CRITIC_PAGE_REPETITION,
    CRITIC_READING_ORDER_AWKWARD,
    VisualCriticDimensions,
    VisualCriticFinding,
    VisualCriticReport,
)
from archium.domain.visual.enums import LayoutElementRole, LayoutIssueSeverity
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.infrastructure.layout.geometry import Rect

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment, misc]


_METHOD = "heuristic_v0"


class VisualCriticService:
    """Evaluate Visual Quality — never calls LayoutRepairService."""

    def evaluate_plan(
        self,
        plan: LayoutPlan,
        *,
        image_path: str | Path | None = None,
        page_area: float | None = None,
        peer_plans: list[LayoutPlan] | None = None,
    ) -> VisualCriticReport:
        """Critique one layout (geometry prior + optional screenshot)."""
        findings: list[VisualCriticFinding] = []
        notes: list[str] = []
        safe = Rect(0.0, 0.0, plan.page_width, plan.page_height)
        area = page_area or max(safe.area, 1e-6)

        focus = self._score_focus(plan, area)
        reading = self._score_reading_order(plan)
        hero = self._score_hero(plan, area)
        mechanical = self._score_mechanical(plan)
        color = None
        repetition = self._score_repetition(plan, peer_plans or [])

        if focus < 0.55:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_FOCUS_UNCLEAR,
                    severity=LayoutIssueSeverity.WARNING,
                    message="Page visual focus / hierarchy looks unclear.",
                    suggestion="Strengthen title/hero contrast or reduce competing equal-weight boxes.",
                    evidence={"focus_hierarchy_clarity": focus},
                )
            )
        if reading < 0.55:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_READING_ORDER_AWKWARD,
                    severity=LayoutIssueSeverity.WARNING,
                    message="Reading order jumps against typical top-to-bottom flow.",
                    suggestion="Reorder or reposition elements to follow a natural scan path.",
                    evidence={"reading_order_naturalness": reading},
                )
            )
        if hero is not None and hero < 0.5:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_HERO_WEAK,
                    severity=LayoutIssueSeverity.WARNING,
                    message="Hero visual does not dominate the page enough.",
                    suggestion="Enlarge the hero or reduce competing supporting visuals.",
                    evidence={"hero_prominence": hero},
                )
            )
        if mechanical < 0.45:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_MECHANICAL,
                    severity=LayoutIssueSeverity.INFO,
                    message="Layout reads as mechanically regular / template-like.",
                    suggestion="Vary block sizes or introduce intentional asymmetry.",
                    evidence={"mechanical_feel": mechanical},
                )
            )
        if repetition is not None and repetition < 0.4:
            findings.append(
                VisualCriticFinding(
                    rule_code=CRITIC_PAGE_REPETITION,
                    severity=LayoutIssueSeverity.WARNING,
                    message="Page geometry closely repeats another slide in the deck.",
                    suggestion="Vary family/variant or supporting content across similar pages.",
                    evidence={"multi_page_repetition": repetition},
                )
            )

        source: str | None = None
        if image_path is not None:
            path = Path(image_path)
            if path.is_file():
                source = str(path)
                color = self._score_color_calm(path)
                if color is not None and color < 0.45:
                    findings.append(
                        VisualCriticFinding(
                            rule_code=CRITIC_COLOR_CHAOS,
                            severity=LayoutIssueSeverity.WARNING,
                            message="Screenshot palette looks noisy / over-saturated.",
                            suggestion="Reduce accent variety; prefer restrained presentation colors.",
                            evidence={"color_calm": color},
                        )
                    )
            else:
                notes.append(f"Screenshot not found: {path}")
        else:
            notes.append("No screenshot provided; color_chaos skipped (geometry-only critic).")

        dimensions = VisualCriticDimensions(
            focus_hierarchy_clarity=round(focus, 3),
            reading_order_naturalness=round(reading, 3),
            hero_prominence=None if hero is None else round(hero, 3),
            color_chaos=None if color is None else round(color, 3),
            mechanical_feel=round(mechanical, 3),
            multi_page_repetition=(
                None if repetition is None else round(repetition, 3)
            ),
        )
        total = self._aggregate(dimensions)
        return VisualCriticReport(
            score_kind="visual_quality",
            method=_METHOD,
            layout_plan_id=str(plan.id),
            slide_id=str(plan.slide_id),
            source_image=source,
            dimensions=dimensions,
            findings=findings,
            total_score=total,
            notes=notes,
        )

    def evaluate_deck(
        self,
        plans: list[LayoutPlan],
        *,
        image_paths: dict[str, str | Path] | None = None,
    ) -> list[VisualCriticReport]:
        """Critique every plan; peer plans feed the repetition dimension."""
        paths = image_paths or {}
        reports: list[VisualCriticReport] = []
        for plan in plans:
            key = str(plan.id)
            reports.append(
                self.evaluate_plan(
                    plan,
                    image_path=paths.get(key) or paths.get(str(plan.slide_id)),
                    peer_plans=[p for p in plans if p.id != plan.id],
                )
            )
        return reports

    @staticmethod
    def _aggregate(dimensions: VisualCriticDimensions) -> float | None:
        values = [
            value
            for value in (
                dimensions.focus_hierarchy_clarity,
                dimensions.reading_order_naturalness,
                dimensions.hero_prominence,
                dimensions.color_chaos,
                dimensions.mechanical_feel,
                dimensions.multi_page_repetition,
            )
            if value is not None
        ]
        if not values:
            return None
        return round(sum(values) / len(values), 3)

    def _score_focus(self, plan: LayoutPlan, page_area: float) -> float:
        areas = sorted((el.area for el in plan.elements), reverse=True)
        if not areas:
            return 0.2
        top = areas[0]
        second = areas[1] if len(areas) > 1 else 0.0
        dominance = top / page_area
        gap = (top - second) / max(top, 1e-6)
        has_title = bool(plan.elements_by_role(LayoutElementRole.TITLE))
        score = 0.45 * min(1.0, dominance * 2.2) + 0.35 * gap + (0.2 if has_title else 0.0)
        return max(0.0, min(1.0, score))

    def _score_reading_order(self, plan: LayoutPlan) -> float:
        by_id = {el.id: el for el in plan.elements}
        ordered: list[LayoutElement] = []
        for element_id in plan.reading_order:
            element = by_id.get(element_id)
            if element is not None:
                ordered.append(element)
        if len(ordered) < 2:
            return 1.0
        inversions = 0
        pairs = 0
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                pairs += 1
                # Prefer earlier readers above later ones (smaller y).
                if left.y - right.y > 0.35:
                    inversions += 1
                elif abs(left.y - right.y) <= 0.15 and left.x - right.x > 0.5:
                    inversions += 1
        if pairs == 0:
            return 1.0
        return max(0.0, 1.0 - inversions / pairs)

    def _score_hero(self, plan: LayoutPlan, page_area: float) -> float | None:
        hero = None
        if plan.hero_element_id:
            hero = plan.element_by_id(plan.hero_element_id)
        if hero is None:
            heroes = plan.elements_by_role(LayoutElementRole.HERO_VISUAL)
            hero = heroes[0] if heroes else None
        if hero is None:
            return None
        ratio = hero.area / page_area
        # Map ~0.15→0.4, ~0.35→0.85, ≥0.5→1.0
        return max(0.0, min(1.0, (ratio - 0.08) / 0.42))

    def _score_mechanical(self, plan: LayoutPlan) -> float:
        """Lower when many similar-sized boxes share near-identical widths/tops."""
        boxes = [el for el in plan.elements if el.role != LayoutElementRole.DECORATION]
        if len(boxes) < 3:
            return 0.85
        widths = [round(el.width, 2) for el in boxes]
        heights = [round(el.height, 2) for el in boxes]
        tops = [round(el.y, 2) for el in boxes]
        width_mode = Counter(widths).most_common(1)[0][1] / len(widths)
        height_mode = Counter(heights).most_common(1)[0][1] / len(heights)
        top_mode = Counter(tops).most_common(1)[0][1] / len(tops)
        regularity = (width_mode + height_mode + top_mode) / 3.0
        # High regularity → mechanical (low organic score).
        return max(0.0, min(1.0, 1.0 - regularity))

    def _score_repetition(
        self, plan: LayoutPlan, peers: list[LayoutPlan]
    ) -> float | None:
        if not peers:
            return None
        fingerprint = self._geometry_fingerprint(plan)
        best = 0.0
        for peer in peers:
            best = max(best, self._fingerprint_similarity(fingerprint, self._geometry_fingerprint(peer)))
        # similarity 1 → repetition score 0
        return max(0.0, min(1.0, 1.0 - best))

    @staticmethod
    def _geometry_fingerprint(plan: LayoutPlan) -> list[tuple[str, float, float, float, float]]:
        return [
            (
                el.role.value,
                round(el.x, 2),
                round(el.y, 2),
                round(el.width, 2),
                round(el.height, 2),
            )
            for el in sorted(plan.elements, key=lambda item: item.id)
        ]

    @staticmethod
    def _fingerprint_similarity(
        left: list[tuple[Any, ...]], right: list[tuple[Any, ...]]
    ) -> float:
        if not left or not right:
            return 0.0
        # Role-sequence match + mean absolute geometry delta.
        roles_l = [item[0] for item in left]
        roles_r = [item[0] for item in right]
        if roles_l != roles_r:
            shared = len(set(roles_l) & set(roles_r))
            role_score = shared / max(len(set(roles_l) | set(roles_r)), 1)
            return role_score * 0.35
        deltas: list[float] = []
        for a, b in zip(left, right, strict=False):
            deltas.append(
                abs(a[1] - b[1])
                + abs(a[2] - b[2])
                + abs(a[3] - b[3])
                + abs(a[4] - b[4])
            )
        mean_delta = statistics.fmean(deltas) if deltas else 0.0
        return max(0.0, min(1.0, 1.0 - mean_delta / 4.0))

    def _score_color_calm(self, path: Path) -> float | None:
        if Image is None:
            return None
        try:
            with Image.open(path) as image:
                rgb = image.convert("RGB")
                rgb.thumbnail((160, 90))
                if hasattr(rgb, "get_flattened_data"):
                    pixels = list(rgb.get_flattened_data())  # type: ignore[attr-defined]
                else:
                    pixels = list(rgb.getdata())
        except OSError:
            return None
        if not pixels:
            return None
        # Sample unique-ish quantized colors; many bins → chaos.
        buckets = Counter(
            ((r // 32), (g // 32), (b // 32)) for r, g, b in pixels
        )
        unique = len(buckets)
        # Also penalize very high saturation variance.
        sats: list[float] = []
        for r, g, b in pixels[:: max(1, len(pixels) // 200)]:
            mx = max(r, g, b)
            mn = min(r, g, b)
            sats.append(0.0 if mx == 0 else (mx - mn) / mx)
        sat_mean = statistics.fmean(sats) if sats else 0.0
        diversity_penalty = min(1.0, unique / 48.0)
        sat_penalty = min(1.0, sat_mean / 0.65)
        chaos = 0.6 * diversity_penalty + 0.4 * sat_penalty
        return max(0.0, min(1.0, 1.0 - chaos))

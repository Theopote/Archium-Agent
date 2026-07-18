"""Read-only deck-level consistency QA across LayoutPlans.

Checks consecutive family repetition, footer/chrome alignment, typography
token consistency, hero image scale, and weak cover/section transitions.
Never mutates layouts or participates in the PPTX export gate.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from uuid import UUID

from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.deck_qa import (
    DECK_CHROME_INCONSISTENT,
    DECK_FOOTER_INCONSISTENT,
    DECK_IMAGE_SCALE_INCONSISTENT,
    DECK_REPEATED_LAYOUT_FAMILY,
    DECK_TYPOGRAPHY_INCONSISTENT,
    DECK_WEAK_SECTION_TRANSITION,
    DeckQADimensions,
    DeckQAFinding,
    DeckQAReport,
)
from archium.domain.visual.enums import LayoutElementRole, LayoutFamily, LayoutIssueSeverity
from archium.domain.visual.layout import LayoutElement, LayoutPlan

_METHOD = "deck_heuristic_v0"
_CHROME_ROLES = frozenset(
    {
        LayoutElementRole.FOOTER,
        LayoutElementRole.PAGE_NUMBER,
        LayoutElementRole.SOURCE,
    }
)
_SECTION_TYPES = frozenset(
    {
        SlideType.TITLE,
        SlideType.SECTION,
        SlideType.CLOSING,
        SlideType.SUMMARY,
    }
)


class DeckQAService:
    """Evaluate cross-page consistency for a visual composition deck."""

    def evaluate(
        self,
        plans: Sequence[LayoutPlan],
        *,
        slides: Sequence[SlideSpec] | None = None,
    ) -> DeckQAReport:
        ordered = list(plans)
        notes: list[str] = []
        if len(ordered) < 2:
            notes.append("Deck QA skipped: fewer than 2 layout plans.")
            return DeckQAReport(
                method=_METHOD,
                slide_count=len(ordered),
                notes=notes,
                total_score=1.0 if ordered else None,
            )

        slides_by_id = {slide.id: slide for slide in slides or []}
        findings: list[DeckQAFinding] = []

        layout_variety, family_findings = self._check_family_repetition(ordered)
        findings.extend(family_findings)

        footer_score, footer_findings = self._check_footer_consistency(ordered)
        findings.extend(footer_findings)

        type_score, type_findings = self._check_typography_consistency(ordered)
        findings.extend(type_findings)

        transition_score, transition_findings = self._check_section_transitions(
            ordered, slides_by_id
        )
        findings.extend(transition_findings)

        image_score, image_findings = self._check_image_scale(ordered)
        findings.extend(image_findings)

        chrome_score, chrome_findings = self._check_chrome_consistency(ordered)
        findings.extend(chrome_findings)

        dimensions = DeckQADimensions(
            layout_variety=round(layout_variety, 3),
            footer_consistency=round(footer_score, 3),
            typography_consistency=round(type_score, 3),
            section_transition=(
                None if transition_score is None else round(transition_score, 3)
            ),
            image_scale_consistency=round(image_score, 3),
            chrome_consistency=round(chrome_score, 3),
        )
        total = self._aggregate(dimensions)
        return DeckQAReport(
            score_kind="deck_consistency",
            method=_METHOD,
            slide_count=len(ordered),
            dimensions=dimensions,
            findings=findings,
            total_score=total,
            notes=notes,
        )

    @staticmethod
    def _aggregate(dimensions: DeckQADimensions) -> float | None:
        values = [
            value
            for value in (
                dimensions.layout_variety,
                dimensions.footer_consistency,
                dimensions.typography_consistency,
                dimensions.section_transition,
                dimensions.image_scale_consistency,
                dimensions.chrome_consistency,
            )
            if value is not None
        ]
        if not values:
            return None
        return round(sum(values) / len(values), 3)

    def _check_family_repetition(
        self, plans: list[LayoutPlan]
    ) -> tuple[float, list[DeckQAFinding]]:
        findings: list[DeckQAFinding] = []
        worst_run = 1
        run_slides: list[str] = []
        run_family: str | None = None

        index = 0
        while index < len(plans):
            end = index + 1
            while (
                end < len(plans)
                and plans[end].layout_family == plans[index].layout_family
            ):
                end += 1
            run_len = end - index
            if run_len > worst_run:
                worst_run = run_len
                run_slides = [str(plan.slide_id) for plan in plans[index:end]]
                run_family = plans[index].layout_family.value
            index = end

        if worst_run >= 3:
            score = max(0.0, 1.0 - (worst_run - 1) * 0.25)
            findings.append(
                DeckQAFinding(
                    rule_code=DECK_REPEATED_LAYOUT_FAMILY,
                    severity=LayoutIssueSeverity.WARNING,
                    message=(
                        f"{worst_run} consecutive slides share the same LayoutFamily."
                    ),
                    suggestion="Alternate families/variants for adjacent content pages.",
                    slide_ids=run_slides,
                    evidence={
                        "consecutive_same_family": worst_run,
                        "family": run_family,
                    },
                )
            )
        elif worst_run == 2:
            score = 0.7
            findings.append(
                DeckQAFinding(
                    rule_code=DECK_REPEATED_LAYOUT_FAMILY,
                    severity=LayoutIssueSeverity.INFO,
                    message="Two consecutive slides use the same LayoutFamily.",
                    suggestion="Consider a variant change if the pages feel identical.",
                    slide_ids=run_slides,
                    evidence={
                        "consecutive_same_family": worst_run,
                        "family": run_family,
                    },
                )
            )
        else:
            score = 1.0
        return score, findings

    def _check_footer_consistency(
        self, plans: list[LayoutPlan]
    ) -> tuple[float, list[DeckQAFinding]]:
        findings: list[DeckQAFinding] = []
        footers: list[tuple[str, LayoutElement]] = []
        for plan in plans:
            for role in (LayoutElementRole.FOOTER, LayoutElementRole.SOURCE):
                for element in plan.elements_by_role(role):
                    footers.append((str(plan.slide_id), element))
                    break
                else:
                    continue
                break

        if len(footers) < 2:
            return 1.0, findings

        ys = [el.y for _, el in footers]
        heights = [el.height for _, el in footers]
        y_span = max(ys) - min(ys)
        h_span = max(heights) - min(heights)
        if y_span > 0.2 or h_span > 0.15:
            score = max(0.0, 1.0 - y_span - h_span)
            findings.append(
                DeckQAFinding(
                    rule_code=DECK_FOOTER_INCONSISTENT,
                    severity=LayoutIssueSeverity.WARNING,
                    message="Footer / source band position or height drifts across slides.",
                    suggestion="Align footer/source y and height to a shared chrome band.",
                    slide_ids=[sid for sid, _ in footers],
                    evidence={
                        "y_span": round(y_span, 3),
                        "height_span": round(h_span, 3),
                    },
                )
            )
            return score, findings
        return 1.0, findings

    def _check_typography_consistency(
        self, plans: list[LayoutPlan]
    ) -> tuple[float, list[DeckQAFinding]]:
        findings: list[DeckQAFinding] = []
        # Same role should prefer the same style_token across content pages.
        by_role: dict[str, Counter[str]] = {}
        for plan in plans:
            for element in plan.elements:
                if element.role not in {
                    LayoutElementRole.TITLE,
                    LayoutElementRole.BODY_TEXT,
                    LayoutElementRole.CAPTION,
                    LayoutElementRole.SOURCE,
                }:
                    continue
                token = element.style_token or "(none)"
                by_role.setdefault(element.role.value, Counter())[token] += 1

        inconsistent_roles: list[str] = []
        for role, counter in by_role.items():
            if len(counter) <= 1:
                continue
            total = sum(counter.values())
            dominant = counter.most_common(1)[0][1]
            if dominant / total < 0.75:
                inconsistent_roles.append(role)

        if inconsistent_roles:
            score = max(0.0, 1.0 - 0.2 * len(inconsistent_roles))
            findings.append(
                DeckQAFinding(
                    rule_code=DECK_TYPOGRAPHY_INCONSISTENT,
                    severity=LayoutIssueSeverity.WARNING,
                    message=(
                        "Same-level text roles use inconsistent style tokens across the deck: "
                        + ", ".join(inconsistent_roles)
                    ),
                    suggestion="Normalize title/body/caption/source tokens across slides.",
                    evidence={"roles": inconsistent_roles},
                )
            )
            return score, findings
        return 1.0, findings

    def _check_section_transitions(
        self,
        plans: list[LayoutPlan],
        slides_by_id: dict[UUID, SlideSpec],
    ) -> tuple[float | None, list[DeckQAFinding]]:
        findings: list[DeckQAFinding] = []
        if not slides_by_id:
            return None, findings

        weak: list[str] = []
        for plan in plans:
            slide = slides_by_id.get(plan.slide_id)
            if slide is None or slide.slide_type not in _SECTION_TYPES:
                continue
            # Cover/section/closing should not look like dense content families.
            if plan.layout_family in {
                LayoutFamily.EVIDENCE_BOARD,
                LayoutFamily.COMPARATIVE_MATRIX,
                LayoutFamily.METRIC_DASHBOARD,
                LayoutFamily.ANALYTICAL_DIAGRAM,
            }:
                weak.append(str(plan.slide_id))

        if weak:
            score = max(0.0, 1.0 - 0.25 * len(weak))
            findings.append(
                DeckQAFinding(
                    rule_code=DECK_WEAK_SECTION_TRANSITION,
                    severity=LayoutIssueSeverity.WARNING,
                    message=(
                        "Cover/section/closing slides use dense content LayoutFamilies "
                        "with weak transitional presence."
                    ),
                    suggestion="Prefer hero / textual_argument / strategy families for section beats.",
                    slide_ids=weak,
                    evidence={"weak_section_slides": weak},
                )
            )
            return score, findings
        return 1.0, findings

    def _check_image_scale(
        self, plans: list[LayoutPlan]
    ) -> tuple[float, list[DeckQAFinding]]:
        findings: list[DeckQAFinding] = []
        hero_widths: list[float] = []
        slide_ids: list[str] = []
        for plan in plans:
            hero = None
            if plan.hero_element_id:
                hero = plan.element_by_id(plan.hero_element_id)
            if hero is None:
                heroes = plan.elements_by_role(LayoutElementRole.HERO_VISUAL)
                hero = heroes[0] if heroes else None
            if hero is None:
                continue
            hero_widths.append(hero.width / max(plan.page_width, 1e-6))
            slide_ids.append(str(plan.slide_id))

        if len(hero_widths) < 2:
            return 1.0, findings

        span = max(hero_widths) - min(hero_widths)
        if span > 0.35:
            score = max(0.0, 1.0 - span)
            findings.append(
                DeckQAFinding(
                    rule_code=DECK_IMAGE_SCALE_INCONSISTENT,
                    severity=LayoutIssueSeverity.WARNING,
                    message="Hero visual widths vary sharply across slides.",
                    suggestion="Keep hero scale closer across content pages for a unified deck feel.",
                    slide_ids=slide_ids,
                    evidence={
                        "width_ratio_span": round(span, 3),
                        "ratios": [round(value, 3) for value in hero_widths],
                    },
                )
            )
            return score, findings
        return 1.0, findings

    def _check_chrome_consistency(
        self, plans: list[LayoutPlan]
    ) -> tuple[float, list[DeckQAFinding]]:
        findings: list[DeckQAFinding] = []
        presence: dict[str, list[bool]] = {
            role.value: [] for role in _CHROME_ROLES
        }
        page_number_boxes: list[tuple[float, float]] = []

        for plan in plans:
            roles_present = {el.role for el in plan.elements}
            for role in _CHROME_ROLES:
                presence[role.value].append(role in roles_present)
            for element in plan.elements_by_role(LayoutElementRole.PAGE_NUMBER):
                page_number_boxes.append((element.x, element.y))
                break

        missing_roles: list[str] = []
        for role, flags in presence.items():
            if not flags:
                continue
            if any(flags) and not all(flags):
                missing_roles.append(role)

        position_drift = False
        if len(page_number_boxes) >= 2:
            xs = [box[0] for box in page_number_boxes]
            ys = [box[1] for box in page_number_boxes]
            if max(xs) - min(xs) > 0.35 or max(ys) - min(ys) > 0.2:
                position_drift = True

        if missing_roles or position_drift:
            penalty = 0.2 * len(missing_roles) + (0.25 if position_drift else 0.0)
            score = max(0.0, 1.0 - penalty)
            findings.append(
                DeckQAFinding(
                    rule_code=DECK_CHROME_INCONSISTENT,
                    severity=LayoutIssueSeverity.WARNING,
                    message="Page chrome (source / footer / page number) is inconsistent across slides.",
                    suggestion="Keep source, footer, and page-number presence and placement stable.",
                    evidence={
                        "intermittent_roles": missing_roles,
                        "page_number_position_drift": position_drift,
                    },
                )
            )
            return score, findings
        return 1.0, findings

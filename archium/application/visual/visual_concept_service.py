"""Recognize page-level VisualConcept (Architectural Presentation Grammar v1).

Not Vision image generation. No new Agent — rule catalog only.
"""

from __future__ import annotations

from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.page_direction import PageDirection
from archium.domain.visual.visual_concept import (
    FRAGMENT_TO_NETWORK_CONCEPT,
    VisualConcept,
)


class VisualConceptService:
    """Attach VisualConcept to PageDirection when grammar rules match."""

    def recognize(
        self,
        slide: SlideSpec,
        direction: PageDirection,
    ) -> VisualConcept | None:
        rule_id = direction.situation_rule_id or ""
        blob = " ".join(
            [
                slide.title or "",
                slide.message or "",
                " ".join(slide.key_points or []),
                direction.claim,
            ]
        ).lower()

        if rule_id == "site_traffic_conflict" or _looks_like_circulation_break(blob):
            return FRAGMENT_TO_NETWORK_CONCEPT.model_copy(deep=True)
        return None

    def apply(
        self,
        direction: PageDirection,
        concept: VisualConcept | None,
    ) -> PageDirection:
        """Stamp concept and bias families toward diagram/evidence when needed."""
        if concept is None:
            return direction
        evidence = list(direction.evidence)
        evidence.append(f"visual_concept:{concept.visual_metaphor.value}")
        preferred = list(direction.preferred_layout_families)
        # fragment_to_network: diagram / evidence before SaaS cards.
        if concept.visual_metaphor.value == "fragment_to_network":
            preferred = _unique(
                [
                    LayoutFamily.ANALYTICAL_DIAGRAM,
                    LayoutFamily.EVIDENCE_BOARD,
                    LayoutFamily.HYBRID_CANVAS,
                    *preferred,
                ]
            )
            forbidden = _unique(
                [
                    *direction.forbidden_layout_families,
                    LayoutFamily.STRATEGY_CARDS,
                    LayoutFamily.METRIC_DASHBOARD,
                    LayoutFamily.TEXTUAL_ARGUMENT,
                ]
            )
        else:
            forbidden = list(direction.forbidden_layout_families)
        preferred = [fam for fam in preferred if fam not in set(forbidden)]
        # Tighten whitespace hint via evidence note (thresholds applied at DesignSystem layer).
        if concept.whitespace_hint is not None:
            evidence.append(f"whitespace_hint:{concept.whitespace_hint:.2f}")
        if concept.drawing_min_area_ratio is not None:
            evidence.append(f"drawing_min_area:{concept.drawing_min_area_ratio:.2f}")
        return direction.model_copy(
            update={
                "visual_concept": concept,
                "preferred_layout_families": preferred[:3],
                "forbidden_layout_families": forbidden,
                "evidence": evidence,
            }
        )


def _looks_like_circulation_break(blob: str) -> bool:
    keys = ("流线冲突", "流线交叉", "人车混行", "交通冲突", "医患交叉", "洁污交叉")
    return any(key in blob for key in keys)


def _unique(items: list[LayoutFamily]) -> list[LayoutFamily]:
    seen: set[LayoutFamily] = set()
    out: list[LayoutFamily] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out

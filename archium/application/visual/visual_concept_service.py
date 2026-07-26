"""Recognize page-level VisualConcept (Architectural Presentation Grammar v1).

Not Vision image generation. No new Agent — rule catalog only.
"""

from __future__ import annotations

from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.page_direction import PageDirection
from archium.domain.visual.visual_concept import (
    CORE_TO_EXPANSION_CONCEPT,
    EXISTING_TO_TRANSFORMATION_CONCEPT,
    FRAGMENT_TO_NETWORK_CONCEPT,
    LAYERED_SITE_CONCEPT,
    PATH_TO_EXPERIENCE_CONCEPT,
    QUIET_ARGUMENT_CONCEPT,
    VisualConcept,
    VisualMetaphor,
)


class VisualConceptService:
    """Attach VisualConcept (+ VisualNarrative) when grammar rules match."""

    def recognize(
        self,
        slide: SlideSpec,
        direction: PageDirection,
    ) -> VisualConcept | None:
        rule_id = direction.situation_rule_id or ""
        title = (slide.title or "").strip()

        if rule_id == "site_traffic_conflict" or title in {
            "流线冲突",
            "交通冲突",
            "人车混行",
        }:
            return FRAGMENT_TO_NETWORK_CONCEPT.model_copy(deep=True)

        if title in {"流线优化", "空间序列", "参观流线"}:
            return PATH_TO_EXPERIENCE_CONCEPT.model_copy(deep=True)

        if title in {"概念生成", "空间生长", "核心拓展"}:
            return CORE_TO_EXPANSION_CONCEPT.model_copy(deep=True)

        if title in {"更新前后", "改造对比", "现状与更新", "效果表达"}:
            return EXISTING_TO_TRANSFORMATION_CONCEPT.model_copy(deep=True)

        if title in {"结论建议", "下一步", "总结"}:
            return QUIET_ARGUMENT_CONCEPT.model_copy(deep=True)

        if rule_id == "drawing_story" or title in {"区位与交通", "城市分析", "分层分析"}:
            return LAYERED_SITE_CONCEPT.model_copy(deep=True)

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
        if concept.narrative is not None:
            evidence.append(f"visual_narrative:{concept.narrative.name}")
            evidence.append(
                f"graphic:{concept.narrative.graphic_language.geometry}"
                f"/{concept.narrative.graphic_language.direction.value}"
            )
        preferred = list(direction.preferred_layout_families)
        metaphor = concept.visual_metaphor
        if metaphor == VisualMetaphor.FRAGMENT_TO_NETWORK:
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
        elif metaphor == VisualMetaphor.EXISTING_TO_TRANSFORMATION:
            preferred = _unique(
                [
                    LayoutFamily.COMPARATIVE_MATRIX,
                    LayoutFamily.HYBRID_CANVAS,
                    LayoutFamily.HERO,
                    *preferred,
                ]
            )
            forbidden = _unique(
                [
                    *direction.forbidden_layout_families,
                    LayoutFamily.METRIC_DASHBOARD,
                    LayoutFamily.TEXTUAL_ARGUMENT,
                ]
            )
        elif metaphor == VisualMetaphor.LAYERED_SITE:
            preferred = _unique(
                [
                    LayoutFamily.DRAWING_FOCUS,
                    LayoutFamily.HYBRID_CANVAS,
                    LayoutFamily.ANALYTICAL_DIAGRAM,
                    *preferred,
                ]
            )
            forbidden = _unique(
                [
                    *direction.forbidden_layout_families,
                    LayoutFamily.STRATEGY_CARDS,
                    LayoutFamily.METRIC_DASHBOARD,
                ]
            )
        elif metaphor == VisualMetaphor.PATH_TO_EXPERIENCE:
            preferred = _unique(
                [
                    LayoutFamily.PROCESS_NARRATIVE,
                    LayoutFamily.ANALYTICAL_DIAGRAM,
                    LayoutFamily.HYBRID_CANVAS,
                    *preferred,
                ]
            )
            forbidden = _unique(
                [
                    *direction.forbidden_layout_families,
                    LayoutFamily.METRIC_DASHBOARD,
                    LayoutFamily.TEXTUAL_ARGUMENT,
                ]
            )
        elif metaphor == VisualMetaphor.CORE_TO_EXPANSION:
            preferred = _unique(
                [
                    LayoutFamily.HERO,
                    LayoutFamily.HYBRID_CANVAS,
                    LayoutFamily.ANALYTICAL_DIAGRAM,
                    *preferred,
                ]
            )
            forbidden = _unique(
                [
                    *direction.forbidden_layout_families,
                    LayoutFamily.METRIC_DASHBOARD,
                    LayoutFamily.TEXTUAL_ARGUMENT,
                ]
            )
        elif metaphor == VisualMetaphor.QUIET_ARGUMENT:
            preferred = _unique(
                [
                    LayoutFamily.TEXTUAL_ARGUMENT,
                    LayoutFamily.HYBRID_CANVAS,
                    *preferred,
                ]
            )
            forbidden = _unique(
                [
                    *direction.forbidden_layout_families,
                    LayoutFamily.STRATEGY_CARDS,
                    LayoutFamily.METRIC_DASHBOARD,
                ]
            )
        else:
            forbidden = list(direction.forbidden_layout_families)
        preferred = [fam for fam in preferred if fam not in set(forbidden)]
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


def _unique(items: list[LayoutFamily]) -> list[LayoutFamily]:
    seen: set[LayoutFamily] = set()
    out: list[LayoutFamily] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out

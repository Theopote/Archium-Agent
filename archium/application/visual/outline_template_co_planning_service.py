"""Outline–Template co-planning (Phase 5).

Maps approved OutlinePlan sections onto induced ArchitecturalContentSchema /
optional ArchitecturalTemplate layouts. Routes each planned page to:

- ``template_editing`` — strong affinity, schema compatible
- ``free_composition`` — weak/no match → existing LayoutPlanningService path
- ``manual_required`` — hard blockers (e.g. drawing required, no drawing schema)

This is rule-driven V1 affinity — not edit-based generation (Phase 6).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplatePageType,
)
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
    OutlineTemplateCompatibility,
    OutlineTemplateCoPlan,
    SchemaAffinityScore,
)

# Affinity at or above this → prefer template editing.
_TEMPLATE_EDITING_MIN = 0.55
# Soft band still records affinity but falls back to free composition.
_WEAK_AFFINITY = 0.35

_CATEGORY_TO_CONTENT: dict[str, ArchitecturalContentType] = {
    "intro": ArchitecturalContentType.COVER_VISUAL,
    "context": ArchitecturalContentType.TEXT_ARGUMENT,
    "heritage": ArchitecturalContentType.DRAWING_FOCUS,
    "culture": ArchitecturalContentType.PHOTO_ANALYSIS,
    "problem": ArchitecturalContentType.PHOTO_ANALYSIS,
    "strategy": ArchitecturalContentType.STRATEGY,
    "implementation": ArchitecturalContentType.PROCESS,
    "decision": ArchitecturalContentType.CONCLUSION,
    "technical": ArchitecturalContentType.DRAWING_FOCUS,
    "general": ArchitecturalContentType.TEXT_ARGUMENT,
}

_SECTION_ID_TO_FUNCTIONAL: dict[str, FunctionalSlideType] = {
    "cover": FunctionalSlideType.COVER,
    "agenda": FunctionalSlideType.AGENDA,
    "toc": FunctionalSlideType.AGENDA,
    "summary": FunctionalSlideType.EXECUTIVE_SUMMARY,
    "executive_summary": FunctionalSlideType.EXECUTIVE_SUMMARY,
    "decision": FunctionalSlideType.DECISION,
    "closing": FunctionalSlideType.CLOSING,
    "appendix": FunctionalSlideType.APPENDIX,
}

_CONTENT_TO_PAGE: dict[ArchitecturalContentType, set[TemplatePageType]] = {
    ArchitecturalContentType.COVER_VISUAL: {TemplatePageType.COVER},
    ArchitecturalContentType.SECTION_VISUAL: {TemplatePageType.SECTION},
    ArchitecturalContentType.DRAWING_FOCUS: {TemplatePageType.DRAWING_FOCUS},
    ArchitecturalContentType.PHOTO_ANALYSIS: {TemplatePageType.PHOTO_GRID},
    ArchitecturalContentType.CASE_COMPARISON: {TemplatePageType.CASE_COMPARISON},
    ArchitecturalContentType.BEFORE_AFTER: {TemplatePageType.BEFORE_AFTER},
    ArchitecturalContentType.METRIC_SUMMARY: {TemplatePageType.METRIC},
    ArchitecturalContentType.STRATEGY: {TemplatePageType.TEXT_ARGUMENT},
    ArchitecturalContentType.PROCESS: {TemplatePageType.PROCESS},
    ArchitecturalContentType.TIMELINE: {TemplatePageType.TIMELINE},
    ArchitecturalContentType.DIAGRAM: {TemplatePageType.DRAWING_FOCUS, TemplatePageType.PROCESS},
    ArchitecturalContentType.TEXT_ARGUMENT: {TemplatePageType.TEXT_ARGUMENT, TemplatePageType.AGENDA},
    ArchitecturalContentType.IMAGE_TEXT_HYBRID: {
        TemplatePageType.PHOTO_GRID,
        TemplatePageType.TEXT_ARGUMENT,
    },
    ArchitecturalContentType.MULTI_IMAGE_GRID: {TemplatePageType.PHOTO_GRID},
    ArchitecturalContentType.CONCLUSION: {TemplatePageType.CLOSING, TemplatePageType.TEXT_ARGUMENT},
}

_DRAWING_ASSET_TOKENS = ("图纸", "总平面", "平面图", "剖面", "立面", "drawing", "plan", "section")
_PHOTO_ASSET_TOKENS = ("照片", "现场", "photo", "image", "现状")
_METRIC_TOKENS = ("指标", "面积", "㎡", "metric", "%")


class OutlineTemplateCoPlanningService:
    """Build OutlineTemplateCoPlan from outline + induced schemas (+ optional template)."""

    def plan(
        self,
        outline: OutlinePlan,
        schemas: list[ArchitecturalContentSchema],
        *,
        template: ArchitecturalTemplate | None = None,
        induction_id: UUID | str | None = None,
    ) -> OutlineTemplateCoPlan:
        page_plans: list[OutlineTemplateCompatibility] = []
        affinities: list[SchemaAffinityScore] = []
        used_schema_ids: set[str] = set()
        used_layout_ids: set[str] = set()
        warnings: list[str] = []

        if not schemas and template is None:
            warnings.append("no schemas or template — all pages free_composition")

        sections = sorted(
            [s for s in outline.sections if s.expanded],
            key=lambda s: s.order,
        )
        for section in sections:
            functional, content, infer_evidence = self._infer_types(section)
            ranked = self._rank_schemas(section, content, functional, schemas)
            affinities.extend(ranked)

            page_count = max(1, section.estimated_slide_count)
            for page_i in range(page_count):
                page_role: Literal["primary", "overflow", "section_opener"] = (
                    "primary" if page_i == 0 else "overflow"
                )
                if (
                    page_i == 0
                    and page_count >= 3
                    and functional == FunctionalSlideType.CONTENT
                    and section.category in {"heritage", "strategy", "problem"}
                ):
                    page_role = "section_opener"

                best = ranked[0] if ranked else None
                layout_ids, preferred_layout = self._match_layouts(
                    content_type=content,
                    functional_type=functional,
                    template=template,
                )
                page_plan = self._build_page_plan(
                    section=section,
                    page_index=page_i,
                    page_role=page_role,
                    functional=functional,
                    content=content,
                    infer_evidence=infer_evidence,
                    best=best,
                    schemas=schemas,
                    layout_ids=layout_ids,
                    preferred_layout=preferred_layout,
                )
                if page_plan.schema_id:
                    used_schema_ids.add(page_plan.schema_id)
                if page_plan.preferred_layout_id:
                    used_layout_ids.add(page_plan.preferred_layout_id)
                used_layout_ids.update(page_plan.compatible_layout_ids)
                page_plans.append(page_plan)

        unmatched_schemas = [s.id for s in schemas if s.id not in used_schema_ids]
        unmatched_layouts: list[str] = []
        if template is not None:
            unmatched_layouts = [
                layout.id
                for layout in template.layouts
                if layout.id not in used_layout_ids
            ]
            if unmatched_layouts:
                warnings.append(
                    f"{len(unmatched_layouts)} template layout(s) unused by outline — exposed for review"
                )
        if unmatched_schemas:
            warnings.append(
                f"{len(unmatched_schemas)} induced schema(s) unused by outline — exposed for review"
            )

        free_ids = [p.slide_id for p in page_plans if p.fallback_mode == "free_composition"]
        edit_ids = [p.slide_id for p in page_plans if p.fallback_mode == "template_editing"]
        manual_ids = [p.slide_id for p in page_plans if p.fallback_mode == "manual_required"]

        return OutlineTemplateCoPlan(
            outline_id=str(outline.id),
            outline_title=outline.title,
            induction_id=str(induction_id or ""),
            template_id=str(template.id) if template is not None else "",
            page_plans=page_plans,
            schema_affinities=affinities,
            unmatched_schema_ids=unmatched_schemas,
            unmatched_layout_ids=unmatched_layouts,
            free_composition_page_ids=free_ids,
            template_editing_page_ids=edit_ids,
            manual_required_page_ids=manual_ids,
            warnings=warnings,
        )

    def _infer_types(
        self,
        section: OutlineSection,
    ) -> tuple[FunctionalSlideType, ArchitecturalContentType, list[str]]:
        evidence: list[str] = []
        sid = section.id.strip().casefold()
        functional = _SECTION_ID_TO_FUNCTIONAL.get(sid, FunctionalSlideType.CONTENT)
        if functional != FunctionalSlideType.CONTENT:
            evidence.append(f"section_id→{functional.value}")

        content = _CATEGORY_TO_CONTENT.get(section.category, ArchitecturalContentType.UNKNOWN)
        if section.category in _CATEGORY_TO_CONTENT:
            evidence.append(f"category→{content.value}")

        blob = " ".join(
            [
                section.title,
                section.purpose,
                section.key_message,
                *section.evidence_requirements,
                *section.required_assets,
            ]
        ).casefold()

        if any(tok in blob for tok in _DRAWING_ASSET_TOKENS):
            content = ArchitecturalContentType.DRAWING_FOCUS
            evidence.append("drawing asset/evidence cues")
        elif any(tok in blob for tok in ("对比", "前后", "before", "after")):
            content = ArchitecturalContentType.BEFORE_AFTER
            evidence.append("before/after cues")
        elif any(tok in blob for tok in ("案例", "对标", "case")):
            content = ArchitecturalContentType.CASE_COMPARISON
            evidence.append("case comparison cues")
        elif any(tok in blob for tok in _METRIC_TOKENS):
            content = ArchitecturalContentType.METRIC_SUMMARY
            evidence.append("metric cues")
        elif any(tok in blob for tok in _PHOTO_ASSET_TOKENS) and content not in {
            ArchitecturalContentType.DRAWING_FOCUS,
            ArchitecturalContentType.COVER_VISUAL,
        }:
            content = ArchitecturalContentType.PHOTO_ANALYSIS
            evidence.append("photo cues")
        elif any(tok in blob for tok in ("策略", "原则", "目标", "strategy")):
            content = ArchitecturalContentType.STRATEGY
            evidence.append("strategy cues")
        elif any(tok in blob for tok in ("流程", "路径", "分期", "process")):
            content = ArchitecturalContentType.PROCESS
            evidence.append("process cues")

        if functional == FunctionalSlideType.COVER:
            content = ArchitecturalContentType.COVER_VISUAL
        elif functional == FunctionalSlideType.CLOSING:
            content = ArchitecturalContentType.CONCLUSION
        elif functional == FunctionalSlideType.AGENDA:
            content = ArchitecturalContentType.TEXT_ARGUMENT
        elif functional == FunctionalSlideType.DECISION:
            content = ArchitecturalContentType.CONCLUSION

        if content == ArchitecturalContentType.UNKNOWN:
            content = ArchitecturalContentType.TEXT_ARGUMENT
            evidence.append("default text_argument")

        return functional, content, evidence

    def _rank_schemas(
        self,
        section: OutlineSection,
        content: ArchitecturalContentType,
        functional: FunctionalSlideType,
        schemas: list[ArchitecturalContentSchema],
    ) -> list[SchemaAffinityScore]:
        scored: list[SchemaAffinityScore] = []
        for schema in schemas:
            affinity, reasons = self._score_schema(section, content, functional, schema)
            scored.append(
                SchemaAffinityScore(
                    schema_id=schema.id,
                    section_id=section.id,
                    affinity=round(affinity, 3),
                    reasons=reasons,
                )
            )
        scored.sort(key=lambda item: item.affinity, reverse=True)
        return scored

    def _score_schema(
        self,
        section: OutlineSection,
        content: ArchitecturalContentType,
        functional: FunctionalSlideType,
        schema: ArchitecturalContentSchema,
    ) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []

        if schema.content_type == content:
            score += 0.45
            reasons.append("content_type exact")
        elif schema.content_type == ArchitecturalContentType.UNKNOWN:
            score += 0.05
            reasons.append("schema content unknown")
        else:
            related = {
                ArchitecturalContentType.PHOTO_ANALYSIS: {
                    ArchitecturalContentType.IMAGE_TEXT_HYBRID,
                    ArchitecturalContentType.MULTI_IMAGE_GRID,
                },
                ArchitecturalContentType.DRAWING_FOCUS: {
                    ArchitecturalContentType.DIAGRAM,
                    ArchitecturalContentType.IMAGE_TEXT_HYBRID,
                },
                ArchitecturalContentType.STRATEGY: {
                    ArchitecturalContentType.TEXT_ARGUMENT,
                    ArchitecturalContentType.PROCESS,
                },
            }
            if schema.content_type in related.get(content, set()) or content in related.get(
                schema.content_type, set()
            ):
                score += 0.22
                reasons.append("content_type related")
            else:
                score -= 0.08
                reasons.append("content_type mismatch")

        if schema.functional_type == functional:
            score += 0.2
            reasons.append("functional_type exact")
        elif (
            functional == FunctionalSlideType.CONTENT
            and schema.functional_type == FunctionalSlideType.CONTENT
        ):
            score += 0.1
            reasons.append("both content pages")

        needs_drawing = any(
            tok in " ".join(section.required_assets + section.evidence_requirements)
            for tok in _DRAWING_ASSET_TOKENS
        ) or content == ArchitecturalContentType.DRAWING_FOCUS
        if needs_drawing and schema.supports_drawing:
            score += 0.2
            reasons.append("drawing support")
        elif needs_drawing and not schema.supports_drawing:
            score -= 0.25
            reasons.append("drawing needed but schema lacks support")

        if schema.confidence >= 0.6:
            score += 0.08
            reasons.append("schema confidence")
        if schema.needs_review:
            score -= 0.05
            reasons.append("schema needs_review")
        if schema.human_corrected:
            score += 0.05
            reasons.append("human-corrected schema")

        schema_blob = f"{schema.name} {schema.page_purpose} {schema.audience_effect}".casefold()
        section_tokens = [
            t
            for t in section.title.replace("与", " ").replace("和", " ").split()
            if len(t) >= 2
        ]
        hits = sum(1 for t in section_tokens if t.casefold() in schema_blob)
        if hits:
            score += min(0.12, 0.04 * hits)
            reasons.append(f"title token hits={hits}")

        return max(0.0, min(1.0, score)), reasons

    def _match_layouts(
        self,
        *,
        content_type: ArchitecturalContentType,
        functional_type: FunctionalSlideType,
        template: ArchitecturalTemplate | None,
    ) -> tuple[list[str], str | None]:
        if template is None:
            return [], None
        preferred_pages = set(_CONTENT_TO_PAGE.get(content_type, set()))
        if functional_type == FunctionalSlideType.COVER:
            preferred_pages.add(TemplatePageType.COVER)
        elif functional_type == FunctionalSlideType.AGENDA:
            preferred_pages.add(TemplatePageType.AGENDA)
        elif functional_type == FunctionalSlideType.CLOSING:
            preferred_pages.add(TemplatePageType.CLOSING)
        elif functional_type == FunctionalSlideType.SECTION_DIVIDER:
            preferred_pages.add(TemplatePageType.SECTION)

        compatible: list[ArchitecturalTemplateLayout] = []
        for layout in template.layouts:
            if layout.page_type in preferred_pages or content_type.value in layout.suitable_content_types:
                compatible.append(layout)
        compatible.sort(
            key=lambda layout: (layout.page_type not in preferred_pages, layout.page_index)
        )
        ids = [layout.id for layout in compatible]
        preferred = ids[0] if ids else None
        return ids, preferred

    def _build_page_plan(
        self,
        *,
        section: OutlineSection,
        page_index: int,
        page_role: Literal["primary", "overflow", "section_opener"],
        functional: FunctionalSlideType,
        content: ArchitecturalContentType,
        infer_evidence: list[str],
        best: SchemaAffinityScore | None,
        schemas: list[ArchitecturalContentSchema],
        layout_ids: list[str],
        preferred_layout: str | None,
    ) -> OutlineTemplateCompatibility:
        blockers: list[str] = []
        warnings: list[str] = []
        evidence = list(infer_evidence)
        affinity = best.affinity if best else 0.0
        schema_id = best.schema_id if best and affinity >= _WEAK_AFFINITY else None
        representative_slide_id: str | None = None
        if schema_id:
            for schema in schemas:
                if schema.id == schema_id:
                    representative_slide_id = schema.representative_slide_id or None
                    break
        if best and affinity >= _WEAK_AFFINITY:
            evidence.extend(best.reasons[:4])
        elif best:
            warnings.append(f"best schema affinity weak ({affinity:.2f})")
            evidence.extend(best.reasons[:2])
        else:
            warnings.append("no induced schema available")

        needs_drawing = content == ArchitecturalContentType.DRAWING_FOCUS or any(
            tok in " ".join(section.required_assets) for tok in _DRAWING_ASSET_TOKENS
        )
        drawing_ok = bool(best and any("drawing support" in r for r in best.reasons))

        if (
            needs_drawing
            and not drawing_ok
            and affinity < _TEMPLATE_EDITING_MIN
            and section.required
            and any(
                tok in " ".join(section.required_assets) for tok in _DRAWING_ASSET_TOKENS
            )
        ):
            blockers.append(
                "required drawing assets but no drawing-capable schema match"
            )

        if blockers:
            mode: Literal["template_editing", "free_composition", "manual_required"] = (
                "manual_required"
            )
        elif affinity >= _TEMPLATE_EDITING_MIN and schema_id:
            mode = "template_editing"
        else:
            mode = "free_composition"
            if schema_id is None:
                warnings.append("fallback=free_composition")

        slide_id = f"{section.id}__p{page_index + 1:02d}"
        return OutlineTemplateCompatibility(
            slide_id=slide_id,
            section_id=section.id,
            section_title=section.title,
            outline_purpose=section.purpose,
            planned_page_index=page_index,
            page_role=page_role,
            inferred_functional_type=functional,
            inferred_content_type=content,
            schema_id=schema_id,
            representative_slide_id=representative_slide_id,
            compatible_layout_ids=layout_ids,
            preferred_layout_id=preferred_layout,
            template_affinity=round(affinity, 3),
            compatibility_score=round(affinity, 3),
            blockers=blockers,
            warnings=warnings,
            evidence=evidence,
            fallback_mode=mode,
        )

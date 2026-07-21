"""Rank induced reference slides / template layouts for a planned SlideSpec (WP I)."""

from __future__ import annotations

from archium.domain.asset import Asset
from archium.domain.enums import AssetType, SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplatePageType,
)
from archium.domain.visual.reference_slide_matching import DeckContext, ReferenceSlideCandidate
from archium.domain.visual.template_induction import ArchitecturalContentType

_PATTERN_PAGE_BOOST: dict[str, set[TemplatePageType]] = {
    "hero_image": {TemplatePageType.COVER, TemplatePageType.PHOTO_GRID},
    "image_grid": {TemplatePageType.PHOTO_GRID},
    "full_bleed_drawing": {TemplatePageType.DRAWING_FOCUS},
    "two_column": {TemplatePageType.TEXT_ARGUMENT, TemplatePageType.PHOTO_GRID, TemplatePageType.CASE_COMPARISON},
    "metric_cards": {TemplatePageType.METRIC},
    "text_column": {TemplatePageType.TEXT_ARGUMENT, TemplatePageType.AGENDA},
    "section_splash": {TemplatePageType.SECTION, TemplatePageType.COVER},
}

_REUSE_PENALTY = 0.18
_WEAK_MATCH = 0.35
_FREE_COMPOSITION_SCORE = 0.12

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

_SLIDE_TYPE_TO_PAGE: dict[SlideType, set[TemplatePageType]] = {
    SlideType.TITLE: {TemplatePageType.COVER, TemplatePageType.SECTION},
    SlideType.SECTION: {TemplatePageType.SECTION},
    SlideType.CONTENT: {
        TemplatePageType.TEXT_ARGUMENT,
        TemplatePageType.PHOTO_GRID,
        TemplatePageType.DRAWING_FOCUS,
        TemplatePageType.METRIC,
    },
    SlideType.IMAGE: {TemplatePageType.PHOTO_GRID},
    SlideType.COMPARISON: {TemplatePageType.CASE_COMPARISON, TemplatePageType.BEFORE_AFTER},
    SlideType.TIMELINE: {TemplatePageType.TIMELINE, TemplatePageType.PROCESS},
    SlideType.DATA: {TemplatePageType.METRIC},
    SlideType.SUMMARY: {TemplatePageType.CLOSING, TemplatePageType.TEXT_ARGUMENT},
    SlideType.CLOSING: {TemplatePageType.CLOSING},
}


class ReferenceSlideMatcher:
    """Rule-driven V1 ranking of reference layouts for edit-based generation."""

    def rank(
        self,
        *,
        slide_spec: SlideSpec,
        content_schema: ArchitecturalContentSchema,
        assets: list[Asset],
        template: ArchitecturalTemplate,
        deck_context: DeckContext | None = None,
        limit: int = 3,
    ) -> list[ReferenceSlideCandidate]:
        ctx = deck_context or DeckContext()
        scored: list[tuple[float, ReferenceSlideCandidate]] = []

        for layout in template.layouts:
            if not layout.slots and not layout.representative_slide_id:
                continue
            score, reasons, blockers = self._score_layout(
                layout=layout,
                slide_spec=slide_spec,
                content_schema=content_schema,
                assets=assets,
                deck_context=ctx,
            )
            schema_id = layout.content_schema_id or content_schema.id
            if layout.content_schema_id and layout.content_schema_id != content_schema.id:
                score = max(0.0, score - 0.15)
                reasons.append("layout schema differs from target schema")

            scored.append(
                (
                    score,
                    ReferenceSlideCandidate(
                        template_id=template.id,
                        layout_id=layout.id,
                        layout_name=layout.name,
                        schema_id=schema_id,
                        representative_slide_id=layout.representative_slide_id
                        or content_schema.representative_slide_id,
                        page_index=layout.page_index,
                        page_type=layout.page_type.value,
                        score=round(score, 3),
                        rank=1,
                        candidate_kind="alternate",
                        reasons=reasons,
                        blockers=blockers,
                    ),
                )
            )

        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[ReferenceSlideCandidate] = []
        for index, (_score, candidate) in enumerate(scored[: max(1, limit)]):
            kind = "recommended" if index == 0 and candidate.score >= _WEAK_MATCH else "alternate"
            results.append(candidate.model_copy(update={"rank": index + 1, "candidate_kind": kind}))

        if not results or results[0].score < _WEAK_MATCH:
            results.append(
                ReferenceSlideCandidate(
                    template_id=template.id,
                    layout_id="",
                    layout_name="Free Composition",
                    schema_id=content_schema.id,
                    representative_slide_id="",
                    score=_FREE_COMPOSITION_SCORE,
                    rank=len(results) + 1,
                    candidate_kind="free_composition",
                    reasons=["no strong reference layout — use LayoutPlan / RenderScene path"],
                )
            )
        return results

    def _score_layout(
        self,
        *,
        layout: ArchitecturalTemplateLayout,
        slide_spec: SlideSpec,
        content_schema: ArchitecturalContentSchema,
        assets: list[Asset],
        deck_context: DeckContext,
    ) -> tuple[float, list[str], list[str]]:
        score = 0.55
        reasons: list[str] = []
        blockers: list[str] = []

        if layout.content_schema_id == content_schema.id:
            score += 0.22
            reasons.append("schema-linked layout")
        elif content_schema.content_type.value in layout.suitable_content_types:
            score += 0.12
            reasons.append("suitable_content_types match")

        preferred_pages = _CONTENT_TO_PAGE.get(content_schema.content_type, set())
        preferred_pages |= _SLIDE_TYPE_TO_PAGE.get(slide_spec.slide_type, set())
        if layout.page_type in preferred_pages:
            score += 0.15
            reasons.append(f"page_type {layout.page_type.value}")
        elif layout.page_type == TemplatePageType.UNKNOWN:
            score -= 0.05
            reasons.append("unknown page_type")

        text_len = len(slide_spec.message) + len(slide_spec.title)
        if content_schema.min_text_length <= text_len <= content_schema.max_text_length:
            score += 0.08
            reasons.append("text length in schema bounds")
        elif text_len > content_schema.max_text_length:
            score -= 0.1
            reasons.append("text may overflow schema max")

        drawing_assets = [a for a in assets if a.asset_type == AssetType.DRAWING]
        photo_assets = [a for a in assets if a.asset_type == AssetType.PHOTO]
        asset_count = len(assets)

        if content_schema.supports_drawing and drawing_assets:
            score += 0.12
            reasons.append("drawing assets + schema support")
        elif content_schema.supports_drawing and not drawing_assets:
            score -= 0.06
            reasons.append("schema expects drawing")

        if layout.supports_photo and photo_assets:
            score += 0.08
            reasons.append("photo assets")
        if asset_count < content_schema.min_asset_count:
            score -= 0.08
            reasons.append("fewer assets than schema minimum")
        elif asset_count > content_schema.max_asset_count:
            score -= 0.05
            reasons.append("more assets than schema maximum")

        if layout.id in deck_context.used_layout_ids:
            score -= _REUSE_PENALTY
            reasons.append("layout reused in deck")
        if layout.representative_slide_id in deck_context.used_representative_slide_ids:
            score -= _REUSE_PENALTY
            reasons.append("representative slide reused")
        if content_schema.id in deck_context.used_schema_ids:
            score -= _REUSE_PENALTY * 0.5
            reasons.append("schema reused recently")

        for asset in assets:
            origin = str(asset.metadata.get("asset_origin", "project_upload"))
            if origin in content_schema.forbidden_asset_origins:
                blockers.append(f"forbidden asset origin: {origin}")
                score -= 0.2

        if content_schema.needs_review and not content_schema.human_corrected:
            score -= 0.08
            reasons.append("schema needs_review")

        pattern = content_schema.visual_layout_pattern.value
        if pattern in _PATTERN_PAGE_BOOST and layout.page_type in _PATTERN_PAGE_BOOST[pattern]:
            score += 0.06
            reasons.append(f"visual_layout {pattern}")

        score = max(0.0, min(1.0, score))
        return score, reasons, blockers

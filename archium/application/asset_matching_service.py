"""Match project assets to slide visual requirements."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.asset_matching_visual import drawing_type_match_adjustment
from archium.application.asset_visual_utils import infer_visual_processing_flags
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual_qa import VisualQAReport
from archium.infrastructure.database.repositories import (
    AssetRepository,
    PresentationRepository,
    VisualQAReportRepository,
)

_VISUAL_ASSET_TYPES: dict[VisualType, set[AssetType]] = {
    VisualType.SITE_PLAN: {AssetType.DRAWING, AssetType.DIAGRAM, AssetType.IMAGE},
    VisualType.FLOOR_PLAN: {AssetType.DRAWING, AssetType.DIAGRAM},
    VisualType.SECTION: {AssetType.DRAWING, AssetType.DIAGRAM},
    VisualType.ELEVATION: {AssetType.DRAWING, AssetType.DIAGRAM},
    VisualType.RENDERING: {AssetType.IMAGE, AssetType.PHOTO},
    VisualType.SITE_PHOTO: {AssetType.PHOTO, AssetType.IMAGE},
    VisualType.DIAGRAM: {AssetType.DIAGRAM, AssetType.DRAWING},
    VisualType.CHART: {AssetType.CHART, AssetType.DIAGRAM, AssetType.IMAGE},
    VisualType.TABLE: {AssetType.IMAGE, AssetType.OTHER},
    VisualType.TIMELINE: {AssetType.DIAGRAM, AssetType.IMAGE},
    VisualType.COMPARISON: {AssetType.IMAGE, AssetType.DIAGRAM},
    VisualType.REFERENCE_CASE: {AssetType.IMAGE, AssetType.PHOTO},
    VisualType.ICON: {AssetType.IMAGE, AssetType.OTHER},
    VisualType.MAP: {AssetType.IMAGE, AssetType.DIAGRAM},
    VisualType.TEXT_ONLY: set(),
}


def _tokenize(text: str) -> set[str]:
    normalized = text.lower().replace("_", " ")
    return {part for part in normalized.replace("，", " ").replace("。", " ").split() if len(part) > 1}


_VISUAL_DRAWING_TYPE_HINTS: dict[VisualType, set[str]] = {
    VisualType.SITE_PLAN: {"site_plan", "map"},
    VisualType.FLOOR_PLAN: {"floor_plan"},
    VisualType.SECTION: {"section"},
    VisualType.ELEVATION: {"elevation"},
    VisualType.DIAGRAM: {"diagram", "analytical"},
    VisualType.MAP: {"site_plan", "map"},
}


def _asset_search_text(asset: Asset) -> str:
    parts = [asset.filename, asset.description or ""]
    vision = asset.metadata.get("vision_caption")
    if isinstance(vision, dict):
        summary = vision.get("summary")
        if isinstance(summary, str):
            parts.append(summary)
        for key in ("spatial_elements", "annotations", "metrics_visible"):
            values = vision.get(key)
            if isinstance(values, list):
                parts.extend(str(value) for value in values if str(value).strip())
    drawing_type = asset.metadata.get("drawing_type")
    if isinstance(drawing_type, str) and drawing_type.strip():
        parts.append(drawing_type)
    return " ".join(part for part in parts if part)


def _tokenize_asset(asset: Asset) -> set[str]:
    return _tokenize(_asset_search_text(asset)) | {tag for tag in asset.tags if tag}


def score_asset_for_requirement(
    requirement: VisualRequirement,
    asset: Asset,
    *,
    qa_report: VisualQAReport | None = None,
) -> float:
    """Score how well an asset satisfies a visual requirement."""
    if requirement.type == VisualType.TEXT_ONLY:
        return 0.0

    score = 0.0
    preferred_types = _VISUAL_ASSET_TYPES.get(requirement.type, {AssetType.IMAGE, AssetType.DRAWING})
    if asset.asset_type in preferred_types:
        score += 0.45

    requirement_tokens = _tokenize(requirement.type.value) | _tokenize(requirement.description)
    asset_tokens = _tokenize_asset(asset)

    overlap = requirement_tokens & asset_tokens
    if overlap:
        score += min(0.35, 0.1 * len(overlap))

    drawing_type = asset.metadata.get("drawing_type")
    if isinstance(drawing_type, str):
        hints = _VISUAL_DRAWING_TYPE_HINTS.get(requirement.type, set())
        if drawing_type in hints:
            score += 0.12

    if asset.quality_score is not None:
        score += 0.2 * asset.quality_score

    if asset.is_low_resolution:
        score -= 0.15

    score += drawing_type_match_adjustment(requirement, qa_report)

    from archium.application.visual.visual_grammar_assets import grammar_asset_match_bonus

    score += grammar_asset_match_bonus(
        requirement,
        asset_search_text=_asset_search_text(asset),
    )

    return max(score, 0.0)


def rank_assets_for_requirement(
    requirement: VisualRequirement,
    assets: list[Asset],
    *,
    min_score: float = 0.35,
    top_k: int = 3,
    qa_reports: dict[UUID, VisualQAReport] | None = None,
) -> list[tuple[Asset, float]]:
    reports = qa_reports or {}
    ranked = sorted(
        (
            (
                asset,
                score_asset_for_requirement(
                    requirement,
                    asset,
                    qa_report=reports.get(asset.id),
                ),
            )
            for asset in assets
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    return [(asset, score) for asset, score in ranked if score >= min_score][:top_k]


def apply_asset_match(
    requirement: VisualRequirement,
    ranked: list[tuple[Asset, float]],
    *,
    overwrite: bool = False,
) -> bool:
    """Apply ranked matches to a requirement. Returns True if changed."""
    infer_visual_processing_flags(requirement)
    requirement.candidate_asset_ids = [asset.id for asset, _score in ranked]

    if requirement.confirmed and not overwrite:
        if requirement.preferred_asset_ids:
            return bool(requirement.candidate_asset_ids)
        return False

    if requirement.type == VisualType.TEXT_ONLY:
        return False

    if not ranked:
        if overwrite and not requirement.confirmed:
            requirement.preferred_asset_ids = []
            requirement.match_score = None
            return True
        return bool(requirement.candidate_asset_ids)

    best_asset, best_score = ranked[0]
    if requirement.preferred_asset_ids and not overwrite:
        return bool(requirement.candidate_asset_ids)

    requirement.preferred_asset_ids = [best_asset.id]
    requirement.match_score = best_score
    return True


class AssetMatchingService:
    """Link slide visual requirements to project assets."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._assets = AssetRepository(session)
        self._presentations = PresentationRepository(session)
        self._qa_reports = VisualQAReportRepository(session)

    def _load_qa_reports(self, assets: list[Asset]) -> dict[UUID, VisualQAReport]:
        if not assets:
            return {}
        return self._qa_reports.get_latest_by_asset_ids({asset.id for asset in assets})

    def match_presentation_slides(
        self,
        project_id: UUID,
        presentation_id: UUID,
        *,
        min_score: float = 0.35,
        rematch: bool = False,
    ) -> tuple[list[SlideSpec], int]:
        """Populate preferred_asset_ids and return updated slides plus match count."""
        assets = self._assets.list_by_project(project_id)
        qa_reports = self._load_qa_reports(assets)
        slides = self._presentations.list_slides(presentation_id)
        if not slides:
            return [], 0

        match_count = 0
        updated: list[SlideSpec] = []
        for slide in slides:
            matched_slide, slide_matches, changed = self._match_slide(
                slide,
                assets,
                qa_reports=qa_reports,
                min_score=min_score,
                rematch=rematch,
                only_unmatched=False,
            )
            match_count += slide_matches
            updated.append(self._presentations.save_slide(matched_slide) if changed else matched_slide)

        updated, binding_count = self._apply_outline_asset_bindings(
            presentation_id,
            updated,
            assets_by_id={asset.id: asset for asset in assets},
        )
        match_count += binding_count

        self._refresh_presentation_delivery(presentation_id, updated)
        return updated, match_count

    def _refresh_presentation_delivery(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
    ) -> None:
        from archium.domain.deck_delivery import apply_deck_delivery_to_presentation

        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is None:
            return
        apply_deck_delivery_to_presentation(presentation, slides)
        self._presentations.update_presentation(presentation)
    def match_slides(
        self,
        project_id: UUID,
        slides: list[SlideSpec],
        *,
        slide_ids: set[UUID] | None = None,
        min_score: float = 0.35,
        rematch: bool = False,
        only_unmatched: bool = False,
    ) -> tuple[list[SlideSpec], int]:
        """Match visual requirements for specific slides and persist changes."""
        if not slides:
            return [], 0

        assets = self._assets.list_by_project(project_id)
        qa_reports = self._load_qa_reports(assets)
        match_count = 0
        updated_by_id: dict[UUID, SlideSpec] = {}

        for slide in slides:
            if slide_ids is not None and slide.id not in slide_ids:
                continue
            matched_slide, slide_matches, changed = self._match_slide(
                slide,
                assets,
                qa_reports=qa_reports,
                min_score=min_score,
                rematch=rematch,
                only_unmatched=only_unmatched,
            )
            match_count += slide_matches
            if changed:
                updated_by_id[slide.id] = self._presentations.save_slide(matched_slide)

        if not updated_by_id:
            return slides, match_count

        return [
            updated_by_id.get(slide.id, slide)
            for slide in slides
        ], match_count

    def rematch_slides_after_split(
        self,
        project_id: UUID,
        slides: list[SlideSpec],
        affected_slide_ids: set[UUID],
    ) -> tuple[list[SlideSpec], int]:
        """Re-run asset matching for slides created or changed by page splits."""
        if not affected_slide_ids:
            return slides, 0
        return self.match_slides(
            project_id,
            slides,
            slide_ids=affected_slide_ids,
            rematch=True,
            only_unmatched=True,
        )

    def _match_slide(
        self,
        slide: SlideSpec,
        assets: list[Asset],
        *,
        qa_reports: dict[UUID, VisualQAReport],
        min_score: float,
        rematch: bool,
        only_unmatched: bool,
    ) -> tuple[SlideSpec, int, bool]:
        if not slide.visual_requirements:
            return slide, 0, False

        changed = False
        match_count = 0
        for requirement in slide.visual_requirements:
            if requirement.type == VisualType.ICON:
                if self._match_icon_requirement(requirement):
                    changed = True
                    match_count += 1
                continue
            if requirement.confirmed:
                if requirement.preferred_asset_ids:
                    match_count += 1
                infer_visual_processing_flags(requirement)
                continue
            if only_unmatched and requirement.preferred_asset_ids:
                match_count += len(requirement.preferred_asset_ids)
                infer_visual_processing_flags(requirement)
                continue
            if requirement.preferred_asset_ids and not rematch:
                match_count += len(requirement.preferred_asset_ids)
                infer_visual_processing_flags(requirement)
                continue
            if requirement.type == VisualType.TEXT_ONLY:
                continue

            ranked = rank_assets_for_requirement(
                requirement,
                assets,
                min_score=min_score,
                qa_reports=qa_reports,
            )
            if apply_asset_match(requirement, ranked, overwrite=rematch):
                changed = True
            if requirement.preferred_asset_ids:
                match_count += 1

        slide, changed = _finalize_slide_delivery(slide, changed=changed)
        return slide, match_count, changed

    def _match_icon_requirement(self, requirement: VisualRequirement) -> bool:
        """Bind semantic icon description onto the Architectural Icon Registry."""
        from archium.application.visual.architectural_icon_registry import (
            ArchitecturalIconMatcher,
        )

        if requirement.confirmed and requirement.icon_id:
            return False
        matcher = ArchitecturalIconMatcher()
        result = matcher.match(requirement.description)
        if result is None:
            if requirement.icon_id:
                requirement.icon_id = None
                requirement.icon_canonical_name = None
                requirement.match_score = None
                return True
            return False
        changed = (
            requirement.icon_id != result.icon.id
            or requirement.icon_canonical_name != result.icon.canonical_name
            or requirement.match_score != result.score
        )
        requirement.icon_id = result.icon.id
        requirement.icon_canonical_name = result.icon.canonical_name
        requirement.match_score = result.score
        instruction = f"icon:{result.icon.canonical_name}:{result.matched_by}"
        if instruction not in requirement.processing_instructions:
            requirement.processing_instructions.append(instruction)
        return bool(changed)


    def _apply_outline_asset_bindings(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        assets_by_id: dict[UUID, Asset],
    ) -> tuple[list[SlideSpec], int]:
        """Apply OutlinePlan.page_asset_bindings after auto-match (user wins)."""
        from archium.application.slide_asset_binding_service import apply_slide_asset_bindings

        outline = None
        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is not None and presentation.current_outline_id is not None:
            outline = self._presentations.get_outline(presentation.current_outline_id)
        if outline is None:
            outlines = self._presentations.list_outlines(presentation_id)
            outline = outlines[0] if outlines else None
        if outline is None or not outline.page_asset_bindings:
            return slides, 0

        updated_slides, resolved_bindings, applied = apply_slide_asset_bindings(
            slides,
            list(outline.page_asset_bindings),
            assets_by_id=assets_by_id,
        )
        if applied <= 0 and resolved_bindings == list(outline.page_asset_bindings):
            return slides, 0

        persisted: list[SlideSpec] = []
        for slide in updated_slides:
            persisted.append(self._presentations.save_slide(slide))

        if resolved_bindings != list(outline.page_asset_bindings):
            outline.page_asset_bindings = resolved_bindings
            outline.touch()
            self._presentations.save_outline(outline)

        return persisted, applied


def _finalize_slide_delivery(slide: SlideSpec, *, changed: bool) -> tuple[SlideSpec, bool]:
    from archium.domain.deck_delivery import refresh_slide_asset_delivery

    before = slide.delivery_status
    before_detail = slide.delivery_detail
    refresh_slide_asset_delivery(slide)
    delivery_changed = (
        slide.delivery_status != before or slide.delivery_detail != before_detail
    )
    return slide, changed or delivery_changed

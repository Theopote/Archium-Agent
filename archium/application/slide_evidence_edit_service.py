"""Edit semantic ``SlideSpec.evidence_items`` and sync Studio preview."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.slide_history_service import SlideHistoryService
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource, VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual.layout_evidence_item import EvidenceItemRole, LayoutEvidenceItem
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository


@dataclass(frozen=True)
class SlideEvidenceEditResult:
    slide: SlideSpec
    scene_patched: bool


class SlideEvidenceEditService:
    """Persist evidence-item semantics and patch live photo/annotation nodes."""

    _PHOTO_TYPES = frozenset({VisualType.SITE_PHOTO, VisualType.REFERENCE_CASE})

    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._history = SlideHistoryService(session)

    def save_evidence_items(
        self,
        slide_id: UUID,
        items: list[LayoutEvidenceItem],
    ) -> SlideEvidenceEditResult:
        slide = self._require_slide(slide_id)
        if len(items) > 6:
            raise WorkflowError("每页最多 6 条语义证据")
        normalized = [self._normalize_item(item) for item in items]
        self._history.record_snapshot(slide, RevisionSource.MANUAL_EDIT)
        slide.evidence_items = normalized
        slide.key_points = [item.claim for item in normalized[:5]]
        self._sync_visual_requirements(slide, normalized)
        saved = self._presentations.save_slide(slide)
        scene_patched = self._patch_scene_for_items(saved, normalized)
        return SlideEvidenceEditResult(slide=saved, scene_patched=scene_patched)

    def sync_asset_from_photo_element(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        asset_id: UUID,
    ) -> SlideSpec | None:
        """After Studio ReplaceAsset on ``photo_N``, mirror asset into evidence item N."""
        index = _photo_element_index(element_id)
        if index is None:
            return None
        slide = self._require_slide(slide_id)
        if index >= len(slide.evidence_items):
            return None
        item = slide.evidence_items[index]
        if item.asset == str(asset_id):
            return slide
        self._history.record_snapshot(slide, RevisionSource.MANUAL_EDIT)
        updated_items = list(slide.evidence_items)
        updated_items[index] = item.model_copy(update={"asset": str(asset_id)})
        slide.evidence_items = updated_items
        self._sync_visual_requirements(slide, updated_items)
        return self._presentations.save_slide(slide)

    def _require_slide(self, slide_id: UUID) -> SlideSpec:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError(f"页面不存在：{slide_id}")
        return slide

    def _normalize_item(self, item: LayoutEvidenceItem) -> LayoutEvidenceItem:
        return LayoutEvidenceItem(
            claim=item.claim.strip(),
            role=item.role,
            asset=item.asset.strip() if item.asset else None,
            focus=item.focus.strip() if item.focus else None,
            source=item.source.strip() if item.source else None,
        )

    def _sync_visual_requirements(
        self,
        slide: SlideSpec,
        items: list[LayoutEvidenceItem],
    ) -> None:
        photo_requirements = [
            requirement
            for requirement in slide.visual_requirements
            if requirement.type in self._PHOTO_TYPES
        ]
        for index, item in enumerate(items):
            if not item.asset:
                continue
            try:
                asset_id = UUID(item.asset)
            except ValueError:
                continue
            if index < len(photo_requirements):
                photo_requirements[index].preferred_asset_ids = [asset_id]
                if item.claim.strip():
                    photo_requirements[index].description = item.claim.strip()
            else:
                slide.visual_requirements.append(
                    VisualRequirement(
                        type=VisualType.SITE_PHOTO,
                        description=item.claim.strip() or f"证据照片 {index + 1}",
                        preferred_asset_ids=[asset_id],
                    )
                )

    def _patch_scene_for_items(
        self,
        slide: SlideSpec,
        items: list[LayoutEvidenceItem],
    ) -> bool:
        from archium.application.visual.studio_scene_edit_service import StudioSceneEditService

        editor = StudioSceneEditService(self._session, settings=self._settings)
        patched = False
        for index, item in enumerate(items):
            annotation_id = f"annotation_{index}"
            photo_id = f"photo_{index}"
            caption = f"{index + 1}. {item.claim}"
            try:
                editor.rewrite_layout_element_text(
                    slide.id,
                    element_id=annotation_id,
                    new_text=caption,
                )
                patched = True
            except WorkflowError:
                pass
            if item.asset:
                try:
                    asset_id = UUID(item.asset)
                except ValueError:
                    continue
                try:
                    editor.replace_layout_element_asset(
                        slide.id,
                        element_id=photo_id,
                        asset_id=asset_id,
                    )
                    patched = True
                except WorkflowError:
                    pass
        return patched


def _photo_element_index(element_id: str) -> int | None:
    if not element_id.startswith("photo_"):
        return None
    suffix = element_id.removeprefix("photo_")
    if not suffix.isdigit():
        return None
    return int(suffix)

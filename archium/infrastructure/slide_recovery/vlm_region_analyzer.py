"""VLM-based non-text region analysis for slide recovery."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from archium.config.settings import Settings, get_settings
from archium.domain.slide_recovery import (
    NormalizedBox,
    RecoveredPageRegion,
    SlideRecoveryPageKind,
)
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.factory import create_llm_provider
from archium.infrastructure.llm.slide_recovery_schemas import (
    SlideRecoveryPageAnalysisDraft,
    SlideRecoveryRegionDraft,
)
from archium.infrastructure.vision.analyzer import analyze_image
from archium.prompts.slide_recovery import (
    SLIDE_RECOVERY_VLM_SYSTEM_PROMPT,
    SLIDE_RECOVERY_VLM_USER_PROMPT,
)

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_DRAWING_TYPES = frozenset(
    {"site_plan", "floor_plan", "section", "elevation", "diagram"}
)
_VISUAL_REGION_TYPES = frozenset(
    {"image", "drawing", "table", "chart", "line", "shape", "background"}
)


@dataclass(frozen=True)
class VlmAnalysisResult:
    page_kind: SlideRecoveryPageKind | None
    regions: list[RecoveredPageRegion]
    source: str


class VlmRegionAnalyzer:
    """Detect non-text page regions via vision LLM with heuristic fallback."""

    def __init__(
        self,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
        model: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._llm = llm
        self._model = model
        if enabled is None:
            enabled = self._settings.slide_recovery_vlm_enabled
        self._enabled = enabled
        if self._llm is None and self._enabled and self._settings.llm_configured:
            self._llm = create_llm_provider(self._settings)

    def analyze(
        self,
        image_path: Path | str,
        *,
        page_width: float,
        page_height: float,
        storage_uri: str | None = None,
    ) -> VlmAnalysisResult:
        path = Path(image_path)
        if not path.is_file():
            return VlmAnalysisResult(page_kind=None, regions=[], source="missing_image")

        if self._vision_llm_available():
            try:
                return self._llm_analyze(path, storage_uri=storage_uri)
            except Exception as exc:
                logger.warning("Slide recovery VLM failed, using heuristic fallback: %s", exc)

        return self._heuristic_analyze(path, storage_uri=storage_uri)

    def _vision_llm_available(self) -> bool:
        return bool(self._enabled and self._llm is not None and self._settings.llm_configured)

    def _llm_analyze(
        self,
        image_path: Path,
        *,
        storage_uri: str | None,
    ) -> VlmAnalysisResult:
        assert self._llm is not None
        model = self._model or self._settings.slide_recovery_vlm_model or self._settings.llm_model
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=SLIDE_RECOVERY_VLM_SYSTEM_PROMPT,
                user_prompt=SLIDE_RECOVERY_VLM_USER_PROMPT,
                model=model,
                temperature=0.1,
                json_mode=True,
                image_paths=(str(image_path),),
            ),
            SlideRecoveryPageAnalysisDraft,
        )
        page_kind = _parse_page_kind(draft.page_kind)
        regions = [
            _region_from_draft(item, storage_uri=storage_uri)
            for item in draft.regions
            if item.region_type in _VISUAL_REGION_TYPES
        ]
        return VlmAnalysisResult(page_kind=page_kind, regions=regions, source="llm_vision")

    def _heuristic_analyze(
        self,
        image_path: Path,
        *,
        storage_uri: str | None,
    ) -> VlmAnalysisResult:
        if Image is None:
            return VlmAnalysisResult(page_kind=None, regions=[], source="heuristic")

        with Image.open(image_path) as image:
            report = analyze_image(UUID(int=0), str(image_path), image.convert("RGB"))
        drawing_type = report.drawing_type or "unknown"
        uri = storage_uri or f"file://{image_path.resolve().as_posix()}"

        if drawing_type in _DRAWING_TYPES:
            region_type = "drawing"
            page_kind = SlideRecoveryPageKind.DRAWING_DOMINANT
            keep_whole = True
            bitmap_fallback = False
            semantic_role = drawing_type
        elif drawing_type == "photo":
            region_type = "image"
            page_kind = SlideRecoveryPageKind.PHOTO
            keep_whole = False
            bitmap_fallback = False
            semantic_role = "photo"
        else:
            region_type = "background"
            page_kind = SlideRecoveryPageKind.IMAGE_TEXT
            keep_whole = False
            bitmap_fallback = True
            semantic_role = "page_background"

        regions = [
            RecoveredPageRegion(
                id=uuid4(),
                bbox=NormalizedBox(x=0.0, y=0.0, width=1.0, height=1.0),
                region_type=region_type,  # type: ignore[arg-type]
                semantic_role=semantic_role,
                confidence=report.drawing_type_confidence or 0.0,
                source_asset_uri=uri,
                keep_whole_drawing=keep_whole,
                bitmap_fallback=bitmap_fallback,
            )
        ]
        return VlmAnalysisResult(page_kind=page_kind, regions=regions, source="heuristic")


def _parse_page_kind(value: str) -> SlideRecoveryPageKind | None:
    normalized = value.strip().lower()
    for kind in SlideRecoveryPageKind:
        if kind.value == normalized:
            return kind
    return None


def _region_from_draft(
    draft: SlideRecoveryRegionDraft,
    *,
    storage_uri: str | None,
) -> RecoveredPageRegion:
    bbox = NormalizedBox(
        x=draft.bbox_x,
        y=draft.bbox_y,
        width=min(draft.bbox_width, 1.0 - draft.bbox_x),
        height=min(draft.bbox_height, 1.0 - draft.bbox_y),
    )
    return RecoveredPageRegion(
        id=uuid4(),
        bbox=bbox,
        region_type=draft.region_type,  # type: ignore[arg-type]
        semantic_role=draft.semantic_role or None,
        confidence=draft.confidence,
        recovered_text=draft.recovered_text or None,
        source_asset_uri=storage_uri,
        keep_whole_drawing=draft.keep_whole_drawing,
        bitmap_fallback=draft.bitmap_fallback,
    )

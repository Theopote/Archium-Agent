"""JSON export for presentation pipeline artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from archium.config.settings import Settings, get_settings
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.slide import SlideSpec


class JsonPresentationRenderer:
    """Export brief, storyline, and slides as a versioned JSON package."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def render(
        self,
        *,
        presentation_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        slides: list[SlideSpec],
        version: int = 1,
    ) -> Path:
        output_dir = self._settings.output_path / "presentations" / str(presentation_id) / f"v{version}"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "presentation.json"

        payload = {
            "presentation_id": str(presentation_id),
            "version": version,
            "generated_at": datetime.now(UTC).isoformat(),
            "brief": brief.model_dump(mode="json"),
            "storyline": storyline.model_dump(mode="json"),
            "slides": [slide.model_dump(mode="json") for slide in slides],
        }
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path

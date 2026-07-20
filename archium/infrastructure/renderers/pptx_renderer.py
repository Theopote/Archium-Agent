"""PPTX renderer driven by RenderScene."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from archium.config.settings import Settings, get_settings
from archium.domain.visual.render_scene import RenderScene
from archium.infrastructure.renderers.pptxgen_cli import PptxGenCliRunner
from archium.infrastructure.renderers.scene_pptx_adapter import RenderScenePptxAdapter


class PptxRenderer:
    """Export RenderScene to editable PPTX via PptxGenJS render-plan.mjs."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._cli = PptxGenCliRunner(self._settings)
        self._adapter = RenderScenePptxAdapter()

    def build_instruction_deck(
        self,
        *,
        title: str,
        scenes: list[tuple[RenderScene, str | None]],
    ) -> dict[str, Any]:
        return self._adapter.render_deck(title=title, scenes=scenes)

    def export_pptx(
        self,
        scene: RenderScene,
        output_path: Path,
        *,
        title: str | None = None,
        speaker_notes: str | None = None,
    ) -> Path:
        deck = self._adapter.render_deck(
            title=title or "Archium Slide",
            scenes=[(scene, speaker_notes)],
        )
        return self.export_deck(deck, output_path)

    def export_deck(self, deck: dict[str, Any], output_path: Path) -> Path:
        """Write a pre-built instruction deck to PPTX."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            deck_path = Path(tmp) / "render_scene.deck.json"
            deck_path.write_text(
                json.dumps(deck, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return self._cli.render_layout_instructions(deck_path, output_path)

    def export_presentation(
        self,
        *,
        title: str,
        scenes: list[tuple[RenderScene, str | None]],
        output_path: Path,
    ) -> Path:
        deck = self.build_instruction_deck(title=title, scenes=scenes)
        return self.export_deck(deck, output_path)

    def font_fallbacks(self, scene: RenderScene) -> list[str]:
        return self._adapter.font_fallbacks(scene)


def maybe_export_scene_pptx(
    scene: RenderScene,
    output_path: Path,
    *,
    title: str,
    speaker_notes: str | None = None,
    settings: Settings | None = None,
) -> Path | None:
    """Export PPTX from RenderScene when Node/PptxGenJS is available."""
    if shutil.which("node") is None:
        return None
    renderer = PptxRenderer(settings)
    if not renderer._cli.is_available() or not renderer._cli.layout_plan_script_path.exists():
        return None
    return renderer.export_pptx(
        scene,
        output_path,
        title=title,
        speaker_notes=speaker_notes,
    )

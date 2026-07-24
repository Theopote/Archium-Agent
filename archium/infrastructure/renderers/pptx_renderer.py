"""PPTX renderer driven by RenderScene."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from archium.config.settings import Settings, get_settings
from archium.domain.export_fidelity import ChartExportMode
from archium.domain.visual.pptx_structure import (
    PptxStructureMode,
    PresentationStructureSpec,
)
from archium.domain.visual.render_scene import RenderScene
from archium.infrastructure.renderers.pptx_master_expander import expand_masters_from_structure
from archium.infrastructure.renderers.pptx_ooxml_structure import require_structured_ooxml
from archium.infrastructure.renderers.pptxgen_cli import PptxGenCliRunner
from archium.infrastructure.renderers.scene_pptx_adapter import RenderScenePptxAdapter

logger = logging.getLogger(__name__)


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
        structure_mode: PptxStructureMode | None = None,
        structure: PresentationStructureSpec | None = None,
        chart_export_mode: ChartExportMode | None = None,
        project_id: UUID | None = None,
    ) -> dict[str, Any]:
        mode = structure_mode or self._default_structure_mode()
        chart_mode = chart_export_mode or self._default_chart_export_mode()
        resolved_scenes = [
            (self._resolve_for_export(scene, project_id=project_id), notes)
            for scene, notes in scenes
        ]
        return self._adapter.render_deck(
            title=title,
            scenes=resolved_scenes,
            structure_mode=mode,
            structure=structure,
            chart_export_mode=chart_mode,
        )

    def export_pptx(
        self,
        scene: RenderScene,
        output_path: Path,
        *,
        title: str | None = None,
        speaker_notes: str | None = None,
        structure_mode: PptxStructureMode | None = None,
        structure: PresentationStructureSpec | None = None,
        chart_export_mode: ChartExportMode | None = None,
        validate_ooxml: bool | None = None,
        project_id: UUID | None = None,
    ) -> Path:
        deck = self.build_instruction_deck(
            title=title or "Archium Slide",
            scenes=[(scene, speaker_notes)],
            structure_mode=structure_mode,
            structure=structure,
            chart_export_mode=chart_export_mode,
            project_id=project_id,
        )
        return self.export_deck(deck, output_path, validate_ooxml=validate_ooxml)

    def export_deck(
        self,
        deck: dict[str, Any],
        output_path: Path,
        *,
        validate_ooxml: bool | None = None,
    ) -> Path:
        """Write a pre-built instruction deck to PPTX."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            deck_path = Path(tmp) / "render_scene.deck.json"
            deck_path.write_text(
                json.dumps(deck, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            rendered = self._cli.render_layout_instructions(deck_path, output_path)

        structure = self._structure_from_deck(deck)
        if structure is not None and structure.mode == PptxStructureMode.STRUCTURED:
            expand_masters_from_structure(rendered, structure, output_path=rendered)

        if self._should_validate_ooxml(deck, validate_ooxml):
            require_structured_ooxml(rendered)
        return rendered

    def export_presentation(
        self,
        *,
        title: str,
        scenes: list[tuple[RenderScene, str | None]],
        output_path: Path,
        structure_mode: PptxStructureMode | None = None,
        structure: PresentationStructureSpec | None = None,
        chart_export_mode: ChartExportMode | None = None,
        validate_ooxml: bool | None = None,
        enforce_capability_contract: bool = True,
        project_id: UUID | None = None,
    ) -> Path:
        resolved_pairs = [
            (self._resolve_for_export(scene, project_id=project_id), notes)
            for scene, notes in scenes
        ]
        if enforce_capability_contract:
            from archium.domain.powerpoint_contract import PowerPointContractService

            contracts = PowerPointContractService()
            chart_mode = (
                chart_export_mode or self._default_chart_export_mode()
            ).value
            for scene, _notes in resolved_pairs:
                contracts.require_capability_export_gate(
                    scene, chart_export_mode=chart_mode
                )
                emissions = contracts.plan_emissions(
                    scene, chart_export_mode=chart_mode
                )
                contracts.require_scene_closure(
                    scene, emissions, chart_export_mode=chart_mode
                )
                contracts.require_emission_object_types(
                    scene, emissions, chart_export_mode=chart_mode
                )

        mode = structure_mode or self._default_structure_mode()
        chart_mode = chart_export_mode or self._default_chart_export_mode()
        deck = self._adapter.render_deck(
            title=title,
            scenes=resolved_pairs,
            structure_mode=mode,
            structure=structure,
            chart_export_mode=chart_mode,
        )
        return self.export_deck(deck, output_path, validate_ooxml=validate_ooxml)

    def font_fallbacks(self, scene: RenderScene) -> list[str]:
        return self._adapter.font_fallbacks(scene)

    def _resolve_for_export(
        self,
        scene: RenderScene,
        *,
        project_id: UUID | None,
    ) -> RenderScene:
        from archium.infrastructure.storage.asset_path_resolver import (
            AssetPathResolveContext,
            AssetPathResolver,
        )

        resolved_project = project_id
        if resolved_project is None and scene.presentation_id is not None:
            # Best-effort: presentation_id alone cannot resolve project storage,
            # but project_id from callers is preferred.
            pass
        return AssetPathResolver().resolve_scene(
            scene,
            AssetPathResolveContext(
                project_id=resolved_project,
                project_storage_root=self._settings.project_storage_path,
            ),
        )

    def _default_structure_mode(self) -> PptxStructureMode:
        raw = getattr(self._settings, "pptx_structure_mode", "flat")
        try:
            return PptxStructureMode(str(raw).strip().lower())
        except ValueError:
            return PptxStructureMode.FLAT

    def _default_chart_export_mode(self) -> ChartExportMode:
        raw = getattr(self._settings, "pptx_chart_export_mode", "cross_app_stable")
        try:
            return ChartExportMode(str(raw).strip().lower())
        except ValueError:
            return ChartExportMode.CROSS_APP_STABLE

    def _structure_from_deck(self, deck: dict[str, Any]) -> PresentationStructureSpec | None:
        raw = deck.get("structure")
        if not isinstance(raw, dict):
            return None
        try:
            return PresentationStructureSpec.model_validate(raw)
        except Exception:
            return None

    def _should_validate_ooxml(
        self,
        deck: dict[str, Any],
        validate_ooxml: bool | None,
    ) -> bool:
        if validate_ooxml is not None:
            return validate_ooxml
        mode = str(deck.get("structure_mode") or "").lower()
        structure = deck.get("structure")
        if isinstance(structure, dict) and str(structure.get("mode", "")).lower() == "structured":
            return True
        return mode == PptxStructureMode.STRUCTURED.value


def scene_pptx_unavailable_reason(settings: Settings | None = None) -> str | None:
    """Return why Scene→PPTX cannot run, or None when the toolchain is ready."""
    if shutil.which("node") is None:
        return "node executable not found on PATH"
    renderer = PptxRenderer(settings)
    if not renderer._cli.is_available():
        return "PptxGenJS CLI / npm dependencies unavailable"
    if not renderer._cli.layout_plan_script_path.exists():
        return f"missing render-plan script: {renderer._cli.layout_plan_script_path}"
    return None


def maybe_export_scene_pptx(
    scene: RenderScene,
    output_path: Path,
    *,
    title: str,
    speaker_notes: str | None = None,
    settings: Settings | None = None,
    structure_mode: PptxStructureMode | None = None,
    structure: PresentationStructureSpec | None = None,
    chart_export_mode: ChartExportMode | None = None,
    project_id: UUID | None = None,
) -> Path | None:
    """Export PPTX from RenderScene when Node/PptxGenJS is available."""
    reason = scene_pptx_unavailable_reason(settings)
    if reason is not None:
        logger.warning("Scene PPTX export skipped: %s", reason)
        return None
    renderer = PptxRenderer(settings)
    return renderer.export_pptx(
        scene,
        output_path,
        title=title,
        speaker_notes=speaker_notes,
        structure_mode=structure_mode,
        structure=structure,
        chart_export_mode=chart_export_mode,
        project_id=project_id,
    )

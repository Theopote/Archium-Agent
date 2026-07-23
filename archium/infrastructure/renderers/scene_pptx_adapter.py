"""Adapt RenderScene into PptxGenJS layout instruction payloads."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from archium.application.visual.scene_fonts import (
    DEFAULT_CJK_FONT,
    detect_font_fallbacks,
    text_has_cjk,
)
from archium.domain.export_fidelity import ChartExportMode
from archium.domain.visual.pptx_structure import (
    PptxStructureMode,
    PresentationStructureSpec,
)
from archium.infrastructure.renderers.pptx_structure_catalog import (
    default_archium_structure_spec,
    structure_spec_to_pptxgen_payload,
)
from archium.domain.visual.render_scene import (
    ChartNode,
    DrawingNode,
    ImageNode,
    RenderScene,
    ShapeNode,
    TableNode,
    TextNode,
)
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import RenderedSlideInstruction


class RenderScenePptxAdapter:
    """Translate RenderScene into executable PptxGen render-plan instructions."""

    def render_slide(
        self,
        scene: RenderScene,
        *,
        design_system_id: UUID | None = None,
        speaker_notes: str | None = None,
    ) -> RenderedSlideInstruction:
        # Hidden nodes remain part of authored revision state, but are not
        # visible delivery objects under the RenderScene closure contract.
        elements = [
            self._node_instruction(node, scene)
            for node in scene.sorted_nodes()
            if node.visible
        ]
        theme_tokens: dict[str, Any] = {
            "colors": dict(scene.theme_tokens.colors),
            "typography": dict(scene.theme_tokens.typography),
            "spacing": dict(scene.theme_tokens.spacing),
            "page": {
                "width": scene.page_width,
                "height": scene.page_height,
                "unit": "in",
            },
        }
        if scene.background.color:
            theme_tokens["colors"]["background"] = scene.background.color
        return RenderedSlideInstruction(
            layout_plan_id=scene.layout_plan_id,
            design_system_id=design_system_id or scene.layout_plan_id,
            layout_family=scene.source_layout_family,
            layout_variant=scene.source_layout_variant,
            page_width=scene.page_width,
            page_height=scene.page_height,
            theme_tokens=theme_tokens,
            elements=elements,
            speaker_notes=speaker_notes,
        )

    def render_deck(
        self,
        *,
        title: str,
        scenes: list[tuple[RenderScene, str | None]],
        design_system_id: UUID | None = None,
        structure_mode: PptxStructureMode = PptxStructureMode.FLAT,
        structure: PresentationStructureSpec | None = None,
        chart_export_mode: ChartExportMode = ChartExportMode.CROSS_APP_STABLE,
    ) -> dict[str, Any]:
        instructions: list[dict[str, Any]] = []
        for scene, notes in scenes:
            instruction = self.render_slide(
                scene,
                design_system_id=design_system_id,
                speaker_notes=notes,
            )
            instructions.append(instruction.to_dict())
        deck: dict[str, Any] = {
            "title": title,
            "schema": "archium.render_scene.v1",
            "slides": instructions,
            "structure_mode": structure_mode.value,
            "chart_export_mode": chart_export_mode.value,
        }
        resolved = self._resolve_structure(
            structure_mode=structure_mode,
            structure=structure,
            scenes=[scene for scene, _ in scenes],
        )
        if resolved is not None:
            deck["structure"] = structure_spec_to_pptxgen_payload(resolved)
        return deck

    def _resolve_structure(
        self,
        *,
        structure_mode: PptxStructureMode,
        structure: PresentationStructureSpec | None,
        scenes: list[RenderScene],
    ) -> PresentationStructureSpec | None:
        if structure_mode == PptxStructureMode.FLAT and structure is None:
            return None
        if structure is not None:
            if structure.mode == PptxStructureMode.FLAT and structure_mode == PptxStructureMode.STRUCTURED:
                return structure.model_copy(update={"mode": PptxStructureMode.STRUCTURED})
            return structure
        if structure_mode != PptxStructureMode.STRUCTURED:
            return None
        page_width = scenes[0].page_width if scenes else 10.0
        page_height = scenes[0].page_height if scenes else 5.625
        background = "FFFFFF"
        if scenes and scenes[0].background.color:
            background = scenes[0].background.color
        elif scenes:
            background = scenes[0].theme_tokens.colors.get("background", "FFFFFF")
        return default_archium_structure_spec(
            page_width=page_width,
            page_height=page_height,
            background_color=str(background),
        )

    def font_fallbacks(self, scene: RenderScene) -> list[str]:
        """Return recorded font substitutions (CJK-on-Latin, missing files)."""
        return detect_font_fallbacks(scene)

    def _node_instruction(self, node: object, scene: RenderScene) -> dict[str, Any]:
        if isinstance(node, TextNode):
            return self._text_instruction(node, scene)
        if isinstance(node, ImageNode):
            return self._image_instruction(node)
        if isinstance(node, DrawingNode):
            return self._drawing_instruction(node)
        if isinstance(node, ShapeNode):
            return self._shape_instruction(node)
        if isinstance(node, ChartNode):
            return self._chart_instruction(node)
        if isinstance(node, TableNode):
            return self._table_instruction(node)
        raise TypeError(f"unsupported render node: {type(node)!r}")

    def _chart_instruction(self, node: ChartNode) -> dict[str, Any]:
        instruction: dict[str, Any] = {
            "id": node.id,
            "role": node.semantic_role or "chart",
            "content_type": "chart",
            "x": node.x,
            "y": node.y,
            "w": node.width,
            "h": node.height,
            "z_index": node.z_index,
            "chart_type": node.chart_type,
            "show_legend": node.show_legend,
            "show_value": node.show_value,
            "series": [
                {
                    "name": series.name,
                    "labels": list(series.labels),
                    "values": list(series.values),
                }
                for series in node.series
            ],
        }
        if node.title:
            instruction["title"] = node.title
        path = _filesystem_export_path(node.preview_resolved_path, node.preview_storage_uri)
        if path:
            instruction["path"] = path
        return instruction

    def _table_instruction(self, node: TableNode) -> dict[str, Any]:
        return {
            "id": node.id,
            "role": node.semantic_role or "table",
            "content_type": "table",
            "x": node.x,
            "y": node.y,
            "w": node.width,
            "h": node.height,
            "z_index": node.z_index,
            "headers": list(node.headers),
            "rows": [list(row) for row in node.rows],
        }

    def _text_instruction(self, node: TextNode, scene: RenderScene) -> dict[str, Any]:
        content_type = "metric" if node.semantic_role == "metric" else "text"
        cjk = node.font_family_cjk or self._cjk_font(node, scene)
        latin = node.font_family_latin or node.font_family
        # Prefer resolved CJK primary for CJK text so PPTX matches PNG/HTML.
        primary = node.font_family
        if text_has_cjk(node.text):
            primary = cjk
        return {
            "id": node.id,
            "role": node.semantic_role or "body_text",
            "content_type": content_type,
            "x": node.x,
            "y": node.y,
            "w": node.width,
            "h": node.height,
            "z_index": node.z_index,
            "alignment": node.alignment,
            "text": node.text,
            "font_family": latin if not text_has_cjk(node.text) else primary,
            "font_family_cjk": cjk or DEFAULT_CJK_FONT,
            "font_size": node.font_size,
            "font_weight": node.font_weight,
            "color": node.color.lstrip("#"),
        }

    def _image_instruction(self, node: ImageNode) -> dict[str, Any]:
        instruction: dict[str, Any] = {
            "id": node.id,
            "role": node.semantic_role or "supporting_visual",
            "content_type": "image",
            "x": node.x,
            "y": node.y,
            "w": node.width,
            "h": node.height,
            "z_index": node.z_index,
            "fit_mode": node.fit_mode,
        }
        path = _filesystem_export_path(node.resolved_path, node.asset_path)
        if path and not node.asset_unresolved:
            instruction["path"] = path
        else:
            instruction["asset_unresolved"] = True
            instruction["asset_error"] = "LAYOUT.UNRESOLVED_ASSET_PATH"
        return instruction

    def _drawing_instruction(self, node: DrawingNode) -> dict[str, Any]:
        instruction: dict[str, Any] = {
            "id": node.id,
            "role": node.semantic_role or "hero_visual",
            "content_type": "drawing",
            "x": node.x,
            "y": node.y,
            "w": node.width,
            "h": node.height,
            "z_index": node.z_index,
            "fit_mode": "contain",
            "drawing_type": node.drawing_type,
        }
        path = _filesystem_export_path(node.resolved_path, node.asset_path)
        if path and not node.asset_unresolved:
            instruction["path"] = path
        else:
            instruction["asset_unresolved"] = True
            instruction["asset_error"] = "LAYOUT.TECHNICAL_DRAWING_MISSING"
        return instruction

    def _shape_instruction(self, node: ShapeNode) -> dict[str, Any]:
        instruction: dict[str, Any] = {
            "id": node.id,
            "role": node.semantic_role or "decoration",
            "content_type": "shape",
            "x": node.x,
            "y": node.y,
            "w": node.width,
            "h": node.height,
            "z_index": node.z_index,
        }
        if node.fill_color:
            instruction["fill_color"] = node.fill_color
        if node.stroke_color:
            instruction["stroke_color"] = node.stroke_color
        if node.stroke_width:
            instruction["stroke_width"] = node.stroke_width
        if node.corner_radius:
            instruction["corner_radius"] = node.corner_radius
        return instruction

    @staticmethod
    def _cjk_font(node: TextNode, scene: RenderScene) -> str:
        if node.font_family_cjk:
            return node.font_family_cjk
        role = node.semantic_role or "body"
        token_name = {
            "title": "title",
            "subtitle": "subtitle",
            "caption": "caption",
            "source": "source",
            "citation": "source",
            "metric": "metric",
            "body_text": "body",
            "lead_statement": "body",
            "page_number": "footnote",
            "heading": "heading",
        }.get(role, "body")
        token = scene.theme_tokens.typography.get(token_name, {})
        if isinstance(token, dict):
            family = token.get("font_family")
            if isinstance(family, str) and family:
                return family
        return DEFAULT_CJK_FONT


_PORTABLE_URI_PREFIXES = ("storage://", "project://", "benchmark://")


def _filesystem_export_path(*candidates: str | None) -> str | None:
    """Pick the first host filesystem path; never pass portable URIs to Node."""
    for raw in candidates:
        text = (raw or "").strip()
        if not text or text.startswith(_PORTABLE_URI_PREFIXES):
            continue
        return text
    return None

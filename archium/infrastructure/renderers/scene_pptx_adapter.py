"""Adapt RenderScene into PptxGenJS layout instruction payloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from archium.domain.export_fidelity import ChartExportMode
from archium.domain.visual.font_names import (
    DEFAULT_CJK_FONT,
)
from archium.domain.visual.pptx_structure import (
    PptxStructureMode,
    PresentationStructureSpec,
)
from archium.domain.visual.render_scene import (
    ChartNode,
    ConnectorNode,
    DrawingNode,
    FreeformNode,
    GroupNode,
    ImageNode,
    RenderScene,
    ShapeNode,
    TableNode,
    TextNode,
    connector_path_points,
)
from archium.domain.visual.scene_fonts import (
    text_has_cjk,
)
from archium.infrastructure.layout.scene_fonts import detect_font_fallbacks
from archium.infrastructure.renderers.pptx_structure_catalog import (
    default_archium_structure_spec,
    structure_spec_to_pptxgen_payload,
)
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import RenderedSlideInstruction
from archium.infrastructure.renderers.svg_icon_recolor import materialize_recolored_icon


class RenderScenePptxAdapter:
    """Translate RenderScene into executable PptxGen render-plan instructions."""

    def render_slide(
        self,
        scene: RenderScene,
        *,
        design_system_id: UUID | None = None,
        speaker_notes: str | None = None,
        citations: list[str] | None = None,
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
            layout_family=(
                scene.source_layout_family.value if scene.source_layout_family else ""
            ),
            layout_variant=scene.source_layout_variant,
            page_width=scene.page_width,
            page_height=scene.page_height,
            theme_tokens=theme_tokens,
            elements=elements,
            speaker_notes=speaker_notes,
            citations=list(citations or []),
        )

    def render_deck(
        self,
        *,
        title: str,
        scenes: list[tuple[RenderScene, str | None]]
        | list[tuple[RenderScene, str | None, list[str] | None]],
        design_system_id: UUID | None = None,
        structure_mode: PptxStructureMode = PptxStructureMode.FLAT,
        structure: PresentationStructureSpec | None = None,
        chart_export_mode: ChartExportMode = ChartExportMode.CROSS_APP_STABLE,
    ) -> dict[str, Any]:
        instructions: list[dict[str, Any]] = []
        for entry in scenes:
            if len(entry) == 3:
                scene, notes, cites = entry
            else:
                scene, notes = entry
                cites = None
            instruction = self.render_slide(
                scene,
                design_system_id=design_system_id,
                speaker_notes=notes,
                citations=list(cites or []) if cites else None,
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
            scenes=[entry[0] for entry in scenes],
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
            instruction = self._text_instruction(node, scene)
        elif isinstance(node, ImageNode):
            instruction = self._image_instruction(node)
        elif isinstance(node, DrawingNode):
            instruction = self._drawing_instruction(node)
        elif isinstance(node, ShapeNode):
            instruction = self._shape_instruction(node)
        elif isinstance(node, ConnectorNode):
            instruction = self._connector_instruction(node, scene)
        elif isinstance(node, FreeformNode):
            instruction = self._freeform_instruction(node)
        elif isinstance(node, GroupNode):
            instruction = self._group_instruction(node)
        elif isinstance(node, ChartNode):
            instruction = self._chart_instruction(node)
        elif isinstance(node, TableNode):
            instruction = self._table_instruction(node)
        else:
            raise TypeError(f"unsupported render node: {type(node)!r}")
        group_id = getattr(node, "group_id", None)
        if group_id:
            instruction["group_id"] = group_id
        return instruction

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
        from archium.domain.visual.render_scene import effective_run_style

        content_type = "metric" if node.semantic_role == "metric" else "text"
        cjk = node.font_family_cjk or self._cjk_font(node, scene)
        latin = node.font_family_latin or node.font_family
        # Prefer resolved CJK primary for CJK text so PPTX matches PNG/HTML.
        primary = node.font_family
        if text_has_cjk(node.text):
            primary = cjk
        instruction: dict[str, Any] = {
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
        if abs(node.letter_spacing) > 1e-6:
            instruction["letter_spacing"] = node.letter_spacing
        if node.opacity < 0.999:
            instruction["opacity"] = node.opacity
        if abs(node.rotation) > 1e-6:
            instruction["rotation"] = node.rotation
        if node.runs:
            runs_payload: list[dict[str, Any]] = []
            for index, run in enumerate(node.runs):
                style = effective_run_style(node, run)
                run_cjk = str(style["font_family_cjk"] or cjk or DEFAULT_CJK_FONT)
                run_latin = str(style["font_family_latin"] or latin)
                run_text = run.text
                run_primary = (
                    run_cjk if text_has_cjk(run_text) else (run_latin or str(style["font_family"]))
                )
                weight = int(style["font_weight"] or node.font_weight)
                run_payload: dict[str, Any] = {
                    "text": run_text,
                    "font_family": run_primary,
                    "font_family_cjk": run_cjk,
                    "font_size": float(style["font_size"] or node.font_size),
                    "font_weight": weight,
                    "font_style": str(style["font_style"] or "normal"),
                    "color": str(style["color"] or node.color).lstrip("#"),
                    "break_line": run_text.endswith("\n")
                    or (index < len(node.runs) - 1 and "\n" in run_text),
                }
                letter = float(style["letter_spacing"] or 0.0)
                if abs(letter) > 1e-6:
                    run_payload["letter_spacing"] = letter
                opacity = float(style["opacity"] if style["opacity"] is not None else 1.0)
                if opacity < 0.999:
                    run_payload["opacity"] = opacity
                if style["outline"]:
                    run_payload["outline"] = True
                    run_payload["outline_width_pt"] = float(style["outline_width_pt"] or 1.0)
                    run_payload["outline_color"] = str(style["outline_color"] or "").lstrip("#")
                    run_payload["fill_enabled"] = bool(style["fill_enabled"])
                runs_payload.append(run_payload)
            instruction["runs"] = runs_payload
        return instruction

    def _image_instruction(self, node: ImageNode) -> dict[str, Any]:
        from archium.domain.visual.render_scene import (
            bottom_fade_gradient,
            gradient_fill_to_payload,
        )

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
        if node.image_mask:
            instruction["image_mask"] = node.image_mask
        fill = node.fill
        if fill is None and (node.image_mask or "") == "gradient_fade":
            fill = bottom_fade_gradient()
        if fill is not None:
            instruction["fill"] = gradient_fill_to_payload(fill)
        path = _filesystem_export_path(
            node.resolved_path, node.asset_path, node.storage_uri
        )
        if path and not node.asset_unresolved:
            export_path = path
            if node.icon_stroke_color and Path(path).suffix.lower() == ".svg":
                export_path = str(
                    materialize_recolored_icon(Path(path), node.icon_stroke_color),
                )
                instruction["icon_stroke_color"] = node.icon_stroke_color.lstrip("#")
            instruction["path"] = export_path
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
        path = _filesystem_export_path(
            node.resolved_path, node.asset_path, node.storage_uri
        )
        if path and not node.asset_unresolved:
            instruction["path"] = path
        else:
            instruction["asset_unresolved"] = True
            instruction["asset_error"] = "LAYOUT.TECHNICAL_DRAWING_MISSING"
        return instruction

    def _shape_instruction(self, node: ShapeNode) -> dict[str, Any]:
        from archium.domain.visual.render_scene import gradient_fill_to_payload

        instruction: dict[str, Any] = {
            "id": node.id,
            "role": node.semantic_role or "decoration",
            "content_type": "shape",
            "x": node.x,
            "y": node.y,
            "w": node.width,
            "h": node.height,
            "z_index": node.z_index,
            "shape_kind": node.shape_kind,
        }
        if node.fill_color:
            instruction["fill_color"] = node.fill_color
        if node.fill is not None:
            instruction["fill"] = gradient_fill_to_payload(node.fill)
        if node.stroke_color:
            instruction["stroke_color"] = node.stroke_color
        if node.stroke_width:
            instruction["stroke_width"] = node.stroke_width
        if node.corner_radius:
            instruction["corner_radius"] = node.corner_radius
        if node.opacity < 0.999:
            instruction["opacity"] = node.opacity
        return instruction

    def _connector_instruction(self, node: ConnectorNode, scene: RenderScene) -> dict[str, Any]:
        points = connector_path_points(scene, node)
        if len(points) < 2:
            points = [
                (node.x, node.y),
                (node.x + node.width, node.y + node.height),
            ]
        instruction: dict[str, Any] = {
            "id": node.id,
            "role": node.semantic_role or "connector",
            "content_type": "connector",
            "x": node.x,
            "y": node.y,
            "w": node.width,
            "h": node.height,
            "z_index": node.z_index,
            "routing": node.routing,
            "stroke_color": node.stroke_color.lstrip("#"),
            "stroke_width": node.stroke_width,
            "arrow_start": node.arrow_start,
            "arrow_end": node.arrow_end,
            "label": node.label,
            "start_node_id": node.start.node_id,
            "end_node_id": node.end.node_id,
            "points": [{"x": x, "y": y} for x, y in points],
        }
        if node.opacity < 0.999:
            instruction["opacity"] = node.opacity
        return instruction

    def _freeform_instruction(self, node: FreeformNode) -> dict[str, Any]:
        instruction: dict[str, Any] = {
            "id": node.id,
            "role": node.semantic_role or "annotation",
            "content_type": "freeform",
            "x": node.x,
            "y": node.y,
            "w": node.width,
            "h": node.height,
            "z_index": node.z_index,
            "closed": node.closed,
            "points": [{"x": point.x, "y": point.y} for point in node.points],
            "stroke_width": node.stroke_width,
        }
        if node.fill_color:
            instruction["fill_color"] = node.fill_color.lstrip("#")
        if node.stroke_color:
            instruction["stroke_color"] = node.stroke_color.lstrip("#")
        if node.opacity < 0.999:
            instruction["opacity"] = node.opacity
        return instruction

    def _group_instruction(self, node: GroupNode) -> dict[str, Any]:
        return {
            "id": node.id,
            "role": node.semantic_role or "group",
            "content_type": "group",
            "x": node.x,
            "y": node.y,
            "w": node.width,
            "h": node.height,
            "z_index": node.z_index,
            "children": list(node.children),
            "clip_children": node.clip_children,
        }

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

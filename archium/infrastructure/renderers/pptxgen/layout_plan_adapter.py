"""PptxGenJS adapter — execute LayoutPlan without re-deciding layout."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from archium.application.visual.icon_stroke_resolve import resolve_icon_stroke_color
from archium.application.visual.svg_icon_recolor import (
    is_architectural_icon_ref,
    materialize_recolored_icon,
)
from archium.domain.export_fidelity import ChartExportMode
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.application.visual.text_style_resolve import resolve_text_style
from archium.domain.visual.pptx_structure import (
    PptxStructureMode,
    PresentationStructureSpec,
)
from archium.infrastructure.renderers.pptx_structure_catalog import (
    default_archium_structure_spec,
    structure_spec_to_pptxgen_payload,
)


@dataclass
class SlideContentBundle:
    """Resolved binary/text content keyed by LayoutElement.content_ref / role."""

    asset_paths: dict[str, str] = field(default_factory=dict)
    asset_origins: dict[str, str] = field(default_factory=dict)
    page_number: int | None = None
    speaker_notes: str | None = None


@dataclass
class RenderedSlideInstruction:
    """Executable instruction payload consumed by pptxgen `render-plan.mjs`."""

    layout_plan_id: UUID
    design_system_id: UUID
    layout_family: str
    layout_variant: str
    page_width: float
    page_height: float
    theme_tokens: dict[str, Any]
    elements: list[dict[str, Any]]
    speaker_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "layout_plan_id": str(self.layout_plan_id),
            "design_system_id": str(self.design_system_id),
            "layout_family": self.layout_family,
            "layout_variant": self.layout_variant,
            "page_width": self.page_width,
            "page_height": self.page_height,
            "theme_tokens": self.theme_tokens,
            "elements": self.elements,
        }
        if self.speaker_notes:
            payload["speaker_notes"] = self.speaker_notes
        return payload


class PptxLayoutPlanAdapter:
    """Translate LayoutPlan + DesignSystem into executable render instructions.

    The adapter must not choose a new layout family or reposition elements.
    """

    def render_slide(
        self,
        layout_plan: LayoutPlan,
        design_system: DesignSystem,
        content_bundle: SlideContentBundle | None = None,
    ) -> RenderedSlideInstruction:
        bundle = content_bundle or SlideContentBundle()
        theme_tokens = {
            "colors": design_system.colors.model_dump(),
            "typography": {
                name: getattr(design_system.typography, name).model_dump()
                for name in (
                    "display",
                    "title",
                    "subtitle",
                    "heading",
                    "body",
                    "caption",
                    "metric",
                    "footnote",
                    "source",
                )
            },
            "spacing": design_system.spacing.model_dump(),
            "page": design_system.page.model_dump(),
            "image_style": design_system.image_style.model_dump(),
            "footer_style": design_system.footer_style.model_dump(),
        }
        elements = [
            self._element_instruction(element, design_system, bundle)
            for element in sorted(layout_plan.elements, key=lambda el: el.z_index)
        ]
        return RenderedSlideInstruction(
            layout_plan_id=layout_plan.id,
            design_system_id=design_system.id,
            layout_family=layout_plan.layout_family.value,
            layout_variant=layout_plan.layout_variant,
            page_width=layout_plan.page_width,
            page_height=layout_plan.page_height,
            theme_tokens=theme_tokens,
            elements=elements,
        )

    def _element_instruction(
        self,
        element: LayoutElement,
        design_system: DesignSystem,
        bundle: SlideContentBundle,
    ) -> dict[str, Any]:
        style_token = element.style_token or "body"
        typography = resolve_text_style(element, design_system.typography)
        color = design_system.colors.resolve(typography.color_token)
        instruction: dict[str, Any] = {
            "id": element.id,
            "role": element.role.value,
            "content_type": element.content_type.value,
            "x": element.x,
            "y": element.y,
            "w": element.width,
            "h": element.height,
            "z_index": element.z_index,
            "alignment": element.alignment,
            "style_token": style_token,
            "font_family": typography.font_family_latin or typography.font_family,
            "font_family_cjk": typography.font_family,
            "font_size": typography.font_size,
            "font_weight": typography.font_weight,
            "color": color.lstrip("#"),
        }
        if element.font_size_override is not None:
            instruction["font_size_override"] = element.font_size_override
        if element.text_content is not None:
            instruction["text"] = element.text_content
        if element.content_ref:
            instruction["content_ref"] = element.content_ref
            path = bundle.asset_paths.get(element.content_ref)
            if path:
                export_path = path
                if is_architectural_icon_ref(element.content_ref) and Path(path).suffix.lower() == ".svg":
                    stroke = resolve_icon_stroke_color(design_system)
                    instruction["icon_stroke_color"] = stroke.lstrip("#")
                    export_path = str(
                        materialize_recolored_icon(Path(path), stroke),
                    )
                instruction["path"] = export_path
                if not _is_supported_layout_image_path(export_path):
                    instruction["asset_unresolved"] = True
                    instruction["asset_error"] = "LAYOUT.UNSUPPORTED_IMAGE_FORMAT"
            elif element.content_type in {
                LayoutContentType.IMAGE,
                LayoutContentType.DRAWING,
                LayoutContentType.CHART,
            }:
                # Explicit failure marker — renderer must not silently omit the box.
                instruction["asset_unresolved"] = True
                if element.content_type == LayoutContentType.DRAWING:
                    instruction["asset_error"] = "LAYOUT.TECHNICAL_DRAWING_MISSING"
                else:
                    instruction["asset_error"] = "LAYOUT.UNRESOLVED_ASSET_PATH"
        elif element.content_type in {
            LayoutContentType.IMAGE,
            LayoutContentType.DRAWING,
            LayoutContentType.CHART,
        }:
            instruction["asset_unresolved"] = True
            if element.content_type == LayoutContentType.DRAWING:
                instruction["asset_error"] = "LAYOUT.TECHNICAL_DRAWING_MISSING"
            elif element.role == LayoutElementRole.HERO_VISUAL:
                instruction["asset_error"] = "LAYOUT.HERO_ASSET_MISSING"
            else:
                instruction["asset_error"] = "LAYOUT.MISSING_ASSET_REFERENCE"
        if element.fit_mode is not None:
            instruction["fit_mode"] = element.fit_mode.value
        if element.crop_policy is not None:
            instruction["crop_policy"] = element.crop_policy.value
        if element.content_type in {LayoutContentType.IMAGE, LayoutContentType.DRAWING}:
            instruction["preserve_aspect_ratio"] = (
                design_system.image_style.drawing_preserve_aspect_ratio
                if element.content_type == LayoutContentType.DRAWING
                else True
            )
        if element.role == LayoutElementRole.PAGE_NUMBER and bundle.page_number is not None:
            instruction["text"] = str(bundle.page_number)
        if element.chart_data is not None:
            instruction["chart_type"] = element.chart_data.chart_type
            instruction["show_legend"] = element.chart_data.show_legend
            instruction["show_value"] = element.chart_data.show_value
            if element.chart_data.title:
                instruction["title"] = element.chart_data.title
            instruction["series"] = [
                {
                    "name": series.name,
                    "labels": list(series.labels),
                    "values": list(series.values),
                }
                for series in element.chart_data.series
            ]
            # Structured chart data clears unresolved-asset placeholder noise.
            if instruction.get("series"):
                instruction.pop("asset_unresolved", None)
                instruction.pop("asset_error", None)
        if element.table_data is not None:
            instruction["headers"] = list(element.table_data.headers)
            instruction["rows"] = [list(row) for row in element.table_data.rows]
        return instruction

    def render_deck(
        self,
        *,
        title: str,
        slides: list[tuple[LayoutPlan, DesignSystem, SlideContentBundle | None]],
        structure_mode: PptxStructureMode = PptxStructureMode.FLAT,
        structure: PresentationStructureSpec | None = None,
        chart_export_mode: ChartExportMode = ChartExportMode.CROSS_APP_STABLE,
    ) -> dict[str, Any]:
        """Build a deck JSON payload for `render-plan.mjs`."""
        instructions: list[dict[str, Any]] = []
        for plan, design_system, bundle in slides:
            instruction = self.render_slide(plan, design_system, bundle)
            if bundle is not None and bundle.speaker_notes:
                instruction.speaker_notes = bundle.speaker_notes
            instructions.append(instruction.to_dict())
        deck: dict[str, Any] = {
            "title": title,
            "schema": "archium.layout_instructions.v1",
            "slides": instructions,
            "structure_mode": structure_mode.value,
            "chart_export_mode": chart_export_mode.value,
        }
        resolved = self._resolve_structure(
            structure_mode=structure_mode,
            structure=structure,
            slides=slides,
        )
        if resolved is not None:
            deck["structure"] = structure_spec_to_pptxgen_payload(resolved)
        return deck

    def _resolve_structure(
        self,
        *,
        structure_mode: PptxStructureMode,
        structure: PresentationStructureSpec | None,
        slides: list[tuple[LayoutPlan, DesignSystem, SlideContentBundle | None]],
    ) -> PresentationStructureSpec | None:
        if structure_mode == PptxStructureMode.FLAT and structure is None:
            return None
        if structure is not None:
            if (
                structure.mode == PptxStructureMode.FLAT
                and structure_mode == PptxStructureMode.STRUCTURED
            ):
                return structure.model_copy(update={"mode": PptxStructureMode.STRUCTURED})
            return structure
        if structure_mode != PptxStructureMode.STRUCTURED:
            return None
        first_plan = slides[0][0] if slides else None
        first_ds = slides[0][1] if slides else None
        page_width = first_plan.page_width if first_plan else 10.0
        page_height = first_plan.page_height if first_plan else 5.625
        background = "FFFFFF"
        if first_ds is not None:
            background = first_ds.colors.background or "FFFFFF"
        return default_archium_structure_spec(
            page_width=page_width,
            page_height=page_height,
            background_color=str(background),
        )


def _is_supported_layout_image_path(path: str) -> bool:
    """Keep adapter import-light to avoid infra<->application cycles."""
    from pathlib import Path

    supported = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
    return Path(path).suffix.lower() in supported

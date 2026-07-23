"""Compile LayoutPlan + content into a renderer-neutral RenderScene.

Chart / table handling:

- When ``LayoutElement.chart_data`` / ``table_data`` is present, emit
  ``ChartNode`` / ``TableNode`` (dual export via ``ChartExportMode``).
- Otherwise ``CHART`` without data still binds as ``ImageNode`` (raster preview);
  ``TABLE`` without grid data still binds as ``TextNode``.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from archium.application.visual.asset_reference import is_supported_layout_image_path
from archium.application.visual.scene_fonts import (
    collect_font_assets,
    resolve_text_fonts,
)
from archium.application.visual.style_overlay import apply_style_overlays
from archium.domain.reference_style import ReferenceStyleProfile
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, OverflowPolicy
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    BoxSpacing,
    ChartNode,
    ChartSeriesData,
    DrawingFitMode,
    DrawingNode,
    DrawingType,
    ImageNode,
    RenderScene,
    SceneAssetReference,
    ShapeNode,
    TableNode,
    TextNode,
    TextParagraph,
    ThemeTokens,
)
from archium.domain.visual.text_style import resolve_text_style
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle

_VISUAL_REQ_TO_DRAWING_TYPE: dict[str, DrawingType] = {
    "site_plan": "site_plan",
    "floor_plan": "floor_plan",
    "elevation": "elevation",
    "section": "section",
    "detail": "detail",
    "diagram": "diagram",
    "heritage_map": "heritage_map",
    "circulation_plan": "circulation_plan",
}

_VALID_ORIGINS = frozenset(
    {
        "project_upload",
        "public_research",
        "reference_case",
        "ai_generated",
        "stock_image",
    }
)


class RenderSceneCompiler:
    """Translate planning artifacts into a unified RenderScene (V1 minimal nodes).

    Applies ``DesignSystem`` plus optional ArtDirection / ReferenceStyle overlays.
    """

    def compile(
        self,
        *,
        slide: SlideSpec,
        layout_plan: LayoutPlan,
        design_system: DesignSystem,
        content_bundle: SlideContentBundle | None = None,
        visual_intent: VisualIntent | None = None,
        art_direction: ArtDirection | None = None,
        reference_style: ReferenceStyleProfile | None = None,
        presentation_id: UUID | None = None,
    ) -> RenderScene:
        overlay = apply_style_overlays(
            design_system,
            art_direction=art_direction,
            reference_style=reference_style,
        )
        effective = overlay.design_system
        bundle = content_bundle or SlideContentBundle()
        warnings: list[str] = list(overlay.warnings)
        asset_manifest: list[SceneAssetReference] = []
        nodes: list[TextNode | ImageNode | DrawingNode | ShapeNode | ChartNode | TableNode] = []
        drawing_type = self._infer_drawing_type(slide, visual_intent)

        bg_color = effective.colors.resolve("background")
        for element in sorted(layout_plan.elements, key=lambda el: el.z_index):
            compiled = self._compile_element(
                element,
                design_system=effective,
                bundle=bundle,
                drawing_type=drawing_type,
                asset_manifest=asset_manifest,
                warnings=warnings,
                overflow_policy=layout_plan.overflow_policy,
            )
            nodes.extend(compiled)

        theme = ThemeTokens(
            colors={
                name: effective.colors.resolve(name)
                for name in (
                    "background",
                    "surface",
                    "primary_text",
                    "secondary_text",
                    "muted_text",
                    "primary",
                    "secondary",
                    "accent",
                    "border",
                )
            },
            typography={
                name: getattr(effective.typography, name).model_dump()
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
            spacing=effective.spacing.model_dump(),
        )
        font_assets = collect_font_assets(
            effective,
            [n for n in nodes if isinstance(n, TextNode)],
        )

        return RenderScene(
            slide_id=layout_plan.slide_id,
            presentation_id=presentation_id or slide.presentation_id,
            layout_plan_id=layout_plan.id,
            design_system_id=effective.id,
            page_width=layout_plan.page_width,
            page_height=layout_plan.page_height,
            background=BackgroundStyle(color=bg_color),
            nodes=nodes,
            theme_tokens=theme,
            font_assets=font_assets,
            asset_manifest=asset_manifest,
            source_layout_family=layout_plan.layout_family.value,
            source_layout_variant=layout_plan.layout_variant,
            warnings=warnings,
        )

    def _infer_drawing_type(
        self,
        slide: SlideSpec,
        visual_intent: VisualIntent | None,
    ) -> DrawingType:
        for req in slide.visual_requirements:
            mapped = _VISUAL_REQ_TO_DRAWING_TYPE.get(req.type.value)
            if mapped:
                return mapped
        if visual_intent is not None:
            dominant = visual_intent.dominant_content_type.value
            mapped = _VISUAL_REQ_TO_DRAWING_TYPE.get(dominant)
            if mapped:
                return mapped
        return "site_plan"

    def _resolve_asset_origin(self, element: LayoutElement, bundle: SlideContentBundle) -> str:
        if not element.content_ref:
            return "project_upload"
        origin = bundle.asset_origins.get(element.content_ref, "project_upload")
        if origin in _VALID_ORIGINS:
            return origin
        return "project_upload"

    def _image_semantic_role(self, element: LayoutElement, origin: str) -> str:
        if origin in {"reference_case", "public_research"}:
            return "reference_case_photo"
        if element.role == LayoutElementRole.HERO_VISUAL:
            return "project_photo"
        if element.role == LayoutElementRole.CAPTION:
            return "caption"
        if element.role == LayoutElementRole.METRIC:
            return "metric"
        return element.role.value

    def _drawing_semantic_role(
        self,
        drawing_type: DrawingType,
    ) -> str:
        return drawing_type

    def _compile_element(
        self,
        element: LayoutElement,
        *,
        design_system: DesignSystem,
        bundle: SlideContentBundle,
        drawing_type: DrawingType,
        asset_manifest: list[SceneAssetReference],
        warnings: list[str],
        overflow_policy: OverflowPolicy = OverflowPolicy.WARN,
    ) -> list[TextNode | ImageNode | DrawingNode | ShapeNode | ChartNode | TableNode]:
        nodes: list[TextNode | ImageNode | DrawingNode | ShapeNode | ChartNode | TableNode] = []
        if element.content_type == LayoutContentType.DRAWING:
            nodes = list(self._compile_drawing(element, bundle, drawing_type, asset_manifest, warnings))
        elif element.content_type == LayoutContentType.CHART:
            chart_nodes = self._compile_chart(element, bundle, asset_manifest, warnings)
            if chart_nodes:
                nodes = list(chart_nodes)
            else:
                nodes = list(self._compile_image(element, bundle, asset_manifest, warnings))
        elif element.content_type == LayoutContentType.IMAGE:
            nodes = list(self._compile_image(element, bundle, asset_manifest, warnings))
        elif element.content_type == LayoutContentType.TABLE:
            table_nodes = self._compile_table(element)
            if table_nodes:
                nodes = list(table_nodes)
            else:
                nodes = list(
                    self._compile_text(
                        element,
                        design_system,
                        bundle,
                        warnings,
                        overflow_policy=overflow_policy,
                    )
                )
        elif element.content_type in {
            LayoutContentType.TEXT,
            LayoutContentType.METRIC,
        }:
            nodes = list(
                self._compile_text(
                    element,
                    design_system,
                    bundle,
                    warnings,
                    overflow_policy=overflow_policy,
                )
            )
        elif element.content_type == LayoutContentType.SHAPE:
            nodes = list(self._compile_shape(element, design_system))
        return nodes

    def _compile_chart(
        self,
        element: LayoutElement,
        bundle: SlideContentBundle,
        asset_manifest: list[SceneAssetReference],
        warnings: list[str],
    ) -> list[ChartNode]:
        data = element.chart_data
        if data is None or not data.series:
            return []
        preview_uri = ""
        preview_path: str | None = None
        if element.content_ref:
            path = bundle.asset_paths.get(element.content_ref)
            if path:
                preview_path = path
                preview_uri = path
        return [
            ChartNode(
                id=element.id,
                semantic_role=element.role.value,
                source_layout_element_id=element.id,
                x=element.x,
                y=element.y,
                width=element.width,
                height=element.height,
                z_index=element.z_index,
                chart_type=data.chart_type,
                title=data.title,
                series=[
                    ChartSeriesData(
                        name=series.name,
                        labels=list(series.labels),
                        values=list(series.values),
                    )
                    for series in data.series
                ],
                show_legend=data.show_legend,
                show_value=data.show_value,
                preview_storage_uri=preview_uri,
                preview_resolved_path=preview_path,
            )
        ]

    def _compile_table(self, element: LayoutElement) -> list[TableNode]:
        data = element.table_data
        if data is None:
            parsed = _parse_table_from_text(element.text_content)
            if parsed is None:
                return []
            headers, rows = parsed
        else:
            headers = list(data.headers)
            rows = [list(row) for row in data.rows]
        if not headers or not rows:
            return []
        return [
            TableNode(
                id=element.id,
                semantic_role=element.role.value,
                source_layout_element_id=element.id,
                x=element.x,
                y=element.y,
                width=element.width,
                height=element.height,
                z_index=element.z_index,
                headers=headers,
                rows=rows,
            )
        ]

    def _compile_text(
        self,
        element: LayoutElement,
        design_system: DesignSystem,
        bundle: SlideContentBundle,
        warnings: list[str],
        *,
        overflow_policy: OverflowPolicy = OverflowPolicy.WARN,
    ) -> list[TextNode | ShapeNode]:
        typography = resolve_text_style(element, design_system.typography)
        color = design_system.colors.resolve(typography.color_token)
        text = (element.text_content or "").strip()
        if not text and element.role == LayoutElementRole.PAGE_NUMBER and bundle.page_number:
            text = str(bundle.page_number)
        if not text:
            warnings.append(f"EMPTY_TEXT_DROPPED:{element.id}")
            return []

        nodes: list[TextNode | ShapeNode] = []
        if element.role == LayoutElementRole.METRIC:
            surface = design_system.colors.resolve("surface")
            border = design_system.colors.resolve("border")
            nodes.append(
                ShapeNode(
                    id=f"{element.id}__card",
                    semantic_role="metric_card",
                    source_layout_element_id=element.id,
                    x=element.x,
                    y=element.y,
                    width=element.width,
                    height=element.height,
                    z_index=max(0, element.z_index - 1),
                    shape_kind="card",
                    fill_color=surface,
                    stroke_color=border,
                    stroke_width=1,
                    corner_radius=4 / 96,
                )
            )

        semantic = "metric" if element.role == LayoutElementRole.METRIC else element.role.value
        if element.role == LayoutElementRole.SOURCE:
            semantic = "citation"
        # Map role → typography token name for theme re-resolution.
        typography_token = _typography_token_for_role(element.role)
        cjk_family = typography.font_family
        latin_family = typography.font_family_latin or typography.font_family
        resolved = resolve_text_fonts(
            text,
            cjk_family=cjk_family,
            latin_family=latin_family,
            bold=typography.font_weight >= 600,
        )
        nodes.append(
            TextNode(
                id=element.id,
                semantic_role=semantic,
                source_layout_element_id=element.id,
                x=element.x,
                y=element.y,
                width=element.width,
                height=element.height,
                z_index=element.z_index,
                locked=element.locked,
                lock_scopes=[scope.value for scope in element.lock_scopes],
                text=text,
                paragraphs=[TextParagraph(text=text, alignment=element.alignment)],
                font_family=resolved.primary,
                font_family_cjk=resolved.cjk,
                font_family_latin=resolved.latin,
                font_size=typography.font_size,
                font_weight=typography.font_weight,
                color=color,
                color_token=typography.color_token,
                typography_token=typography_token,
                alignment=element.alignment or typography.alignment,
                line_height=typography.line_height,
                letter_spacing=typography.letter_spacing,
                padding=BoxSpacing(left=4 / 96, right=4 / 96, top=2 / 96, bottom=2 / 96),
                overflow_policy=_scene_overflow_policy(overflow_policy),
            )
        )
        return nodes

    def _compile_image(
        self,
        element: LayoutElement,
        bundle: SlideContentBundle,
        asset_manifest: list[SceneAssetReference],
        warnings: list[str],
    ) -> list[ImageNode]:
        path, unresolved = self._resolve_asset_path(element, bundle, warnings)
        origin = self._resolve_asset_origin(element, bundle)
        fit = "cover"
        if element.fit_mode is not None:
            fit = "contain" if element.fit_mode.value == "contain" else "cover"
        if path and not unresolved:
            asset_manifest.append(
                SceneAssetReference(
                    storage_uri=path,
                    asset_path=path,
                    content_ref=element.content_ref,
                    origin=origin,
                )
            )
        return [
            ImageNode(
                id=element.id,
                semantic_role=self._image_semantic_role(element, origin),
                source_layout_element_id=element.id,
                x=element.x,
                y=element.y,
                width=element.width,
                height=element.height,
                z_index=element.z_index,
                locked=element.locked,
                storage_uri=path or "",
                asset_path=path or "",
                asset_origin=origin,  # type: ignore[arg-type]
                fit_mode=fit,  # type: ignore[arg-type]
                asset_unresolved=unresolved,
            )
        ]

    def _compile_drawing(
        self,
        element: LayoutElement,
        bundle: SlideContentBundle,
        drawing_type: DrawingType,
        asset_manifest: list[SceneAssetReference],
        warnings: list[str],
    ) -> list[DrawingNode]:
        path, unresolved = self._resolve_asset_path(element, bundle, warnings)
        origin = self._resolve_asset_origin(element, bundle)
        fit_mode: DrawingFitMode = "contain"
        if element.fit_mode is not None and element.fit_mode.value == "cover":
            warnings.append(f"DRAWING_COVER_MODE_FORBIDDEN:{element.id}")
            fit_mode = "contain"
        if path and not unresolved:
            asset_manifest.append(
                SceneAssetReference(
                    storage_uri=path,
                    asset_path=path,
                    content_ref=element.content_ref,
                    origin=origin,
                )
            )
        return [
            DrawingNode(
                id=element.id,
                semantic_role=self._drawing_semantic_role(drawing_type),
                source_layout_element_id=element.id,
                x=element.x,
                y=element.y,
                width=element.width,
                height=element.height,
                z_index=element.z_index,
                locked=element.locked,
                lock_scopes=[scope.value for scope in element.lock_scopes],
                storage_uri=path or "",
                asset_path=path or "",
                drawing_type=drawing_type,
                fit_mode=fit_mode,
                crop_allowed=False,
                asset_unresolved=unresolved,
            )
        ]

    def _compile_shape(
        self,
        element: LayoutElement,
        design_system: DesignSystem,
    ) -> list[ShapeNode]:
        return [
            ShapeNode(
                id=element.id,
                semantic_role=element.role.value,
                source_layout_element_id=element.id,
                x=element.x,
                y=element.y,
                width=element.width,
                height=element.height,
                z_index=element.z_index,
                shape_kind="rectangle",
                fill_color=design_system.colors.resolve("surface"),
                stroke_color=design_system.colors.resolve("border"),
                stroke_width=1,
            )
        ]

    def _resolve_asset_path(
        self,
        element: LayoutElement,
        bundle: SlideContentBundle,
        warnings: list[str],
    ) -> tuple[str | None, bool]:
        if not element.content_ref:
            warnings.append(f"MISSING_ASSET_REFERENCE:{element.id}")
            return None, True
        path = bundle.asset_paths.get(element.content_ref)
        if not path:
            warnings.append(f"UNRESOLVED_ASSET:{element.content_ref}")
            return None, True
        if not is_supported_layout_image_path(path):
            warnings.append(f"UNSUPPORTED_FORMAT:{element.content_ref}")
            return path, True
        return path, False


def _scene_overflow_policy(
    policy: OverflowPolicy,
) -> Literal["error", "shrink", "clip", "continue"]:
    """Map LayoutPlan OverflowPolicy onto TextNode.overflow_policy.

    WARN/SPLIT → error so scene semantic QA can detect overflow and repair can act.
    """
    if policy == OverflowPolicy.SHRINK:
        return "shrink"
    if policy == OverflowPolicy.CLIP:
        return "clip"
    return "error"


def _typography_token_for_role(role: LayoutElementRole) -> str:
    mapping = {
        LayoutElementRole.TITLE: "title",
        LayoutElementRole.SUBTITLE: "subtitle",
        LayoutElementRole.LEAD_STATEMENT: "heading",
        LayoutElementRole.BODY_TEXT: "body",
        LayoutElementRole.CAPTION: "caption",
        LayoutElementRole.METRIC: "metric",
        LayoutElementRole.SOURCE: "source",
        LayoutElementRole.FOOTER: "footnote",
        LayoutElementRole.PAGE_NUMBER: "footnote",
        LayoutElementRole.ANNOTATION: "caption",
    }
    return mapping.get(role, "body")


def _parse_table_from_text(text: str | None) -> tuple[list[str], list[list[str]]] | None:
    """Parse a simple pipe/tab/CSV-ish text grid into headers + rows."""
    if not text or not str(text).strip():
        return None
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    def _split(line: str) -> list[str]:
        if "|" in line:
            return [cell.strip() for cell in line.split("|") if cell.strip() != ""]
        if "\t" in line:
            return [cell.strip() for cell in line.split("\t")]
        if "," in line:
            return [cell.strip() for cell in line.split(",")]
        return [line]

    rows = [_split(line) for line in lines]
    width = max(len(row) for row in rows)
    if width < 2:
        return None
    normalized = [row + [""] * (width - len(row)) for row in rows]
    return normalized[0], normalized[1:]


def new_render_scene_id() -> UUID:
    return uuid4()

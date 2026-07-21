"""Reference slide edit-based scene generation (Phase 6 skeleton).

Copies induced reference slide structure into a ``RenderScene``, strips
reference-template text/assets, and binds project ``SlideSpec`` content only.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from archium.application.visual.scene_fonts import (
    collect_font_assets,
    resolve_text_fonts,
    typography_role_for_semantic,
)
from archium.application.visual.semantic_content_plan import (
    SemanticContentPlan,
    SemanticFillState,
    build_semantic_content_plan,
    normalize_text_role_for_schema,
    replacement_text_for_role,
)
from archium.application.visual.placeholder_binding_matcher import effective_semantic_role
from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.slide import SlideSpec
from archium.domain.slide_generation_context import SlideGenerationContext
from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    ContentRole,
)
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
)
from archium.domain.visual.design_system import DesignSystem, TextStyleToken
from archium.domain.visual.reference_slide import (
    REFERENCE_TEMPLATE_ASSET_ORIGIN,
    ReferenceElement,
    ReferenceElementType,
    ReferenceSlideSnapshot,
)
from archium.domain.visual.reference_slide_editing import (
    PreserveDecorationAction,
    ReferenceSlideEditResult,
    RemoveReferenceAssetAction,
    ReplaceAssetAction,
    ReplaceTextAction,
    SkipUnsupportedAction,
)
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    BoxSpacing,
    DrawingNode,
    ImageNode,
    RenderScene,
    SceneAssetReference,
    ShapeNode,
    TextNode,
    TextParagraph,
    ThemeTokens,
)

_DRAWING_ASSET_TYPES = frozenset(
    {AssetType.DRAWING, AssetType.DIAGRAM, AssetType.CHART}
)
_PHOTO_ASSET_TYPES = frozenset(
    {AssetType.PHOTO, AssetType.IMAGE, AssetType.OTHER}
)

_ROLE_TO_TYPOGRAPHY: dict[str, str] = {
    "title": "title",
    "subtitle": "subtitle",
    "central_claim": "heading",
    "lead_statement": "body",
    "body": "body",
    "evidence": "body",
    "interpretation": "body",
    "metric": "metric",
    "caption": "caption",
    "source": "source",
    "decision_request": "heading",
    "page_number": "footnote",
}


class ReferenceSlideEditingService:
    """V1 skeleton: structure copy + reference strip + project content fill."""

    def generate_scene(
        self,
        *,
        reference_slide: ReferenceSlideSnapshot,
        content_schema: ArchitecturalContentSchema,
        slide_spec: SlideSpec,
        assets: list[Asset],
        design_system: DesignSystem,
        template: ArchitecturalTemplate,
        layout_id: str | None = None,
        presentation_id: UUID | None = None,
        generation_context: SlideGenerationContext | None = None,
    ) -> ReferenceSlideEditResult:
        actions: list[
            ReplaceTextAction
            | ReplaceAssetAction
            | RemoveReferenceAssetAction
            | PreserveDecorationAction
            | SkipUnsupportedAction
        ] = []
        warnings: list[str] = []
        nodes: list[TextNode | ImageNode | DrawingNode | ShapeNode] = []
        asset_manifest: list[SceneAssetReference] = []
        stripped_text = 0
        stripped_asset = 0

        layout = self._resolve_layout(template, layout_id, content_schema)
        merged_assets = self._merge_context_assets(assets, generation_context)
        asset_pool = self._project_asset_pool(merged_assets, content_schema)
        content_plan = build_semantic_content_plan(
            content_schema,
            slide_spec,
            generation_context=generation_context,
        )
        fill_state = SemanticFillState()
        photo_idx = 0
        drawing_idx = 0

        if generation_context is not None:
            warnings.append("slide_generation_context active")

        ref_assets_by_id = {asset.id: asset for asset in reference_slide.image_assets}
        image_slot_count = sum(
            1
            for el in reference_slide.iter_elements()
            if el.element_type == ReferenceElementType.IMAGE
        )
        if content_plan.uses_semantic_contract:
            warnings.append("semantic_content_contract active")
            expected_images = content_plan.expected_image_slot_count()
            if expected_images and image_slot_count != expected_images:
                warnings.append(
                    "image slot count "
                    f"({image_slot_count}) vs semantic contract ({expected_images})"
                )

        for element in sorted(reference_slide.iter_elements(), key=lambda el: el.z_index):
            if element.element_type == ReferenceElementType.GROUP:
                continue

            if self._is_decoration(element):
                nodes.append(self._decoration_node(element, design_system))
                actions.append(
                    PreserveDecorationAction(
                        element_id=element.id,
                        reason="preserve reference decoration geometry",
                        shape_kind="rectangle",
                        locked=True,
                    )
                )
                continue

            if element.element_type == ReferenceElementType.TEXT or (
                element.element_type == ReferenceElementType.PLACEHOLDER
                and element.text
                and not self._placeholder_hosts_picture(element)
            ):
                role = self._resolve_text_role(element)
                role = normalize_text_role_for_schema(
                    role,
                    schema=content_schema,
                    plan=content_plan,
                    state=fill_state,
                )
                replacement = replacement_text_for_role(
                    role,
                    plan=content_plan,
                    slide_spec=slide_spec,
                    state=fill_state,
                )
                if element.text.strip() and element.text.strip() != replacement.strip():
                    stripped_text += 1
                text_nodes = self._text_nodes(
                    element=element,
                    role=role,
                    text=replacement,
                    design_system=design_system,
                )
                nodes.extend(text_nodes)
                actions.append(
                    ReplaceTextAction(
                        element_id=element.id,
                        semantic_role=role,
                        reference_text=element.text,
                        replacement_text=replacement,
                        reason=(
                            "semantic contract fill"
                            if content_plan.uses_semantic_contract
                            else "strip reference text and bind SlideSpec content"
                        ),
                    )
                )
                continue

            if element.element_type in {
                ReferenceElementType.IMAGE,
                ReferenceElementType.DRAWING,
            } or self._placeholder_hosts_picture(element):
                ref_asset = ref_assets_by_id.get(element.asset_id or "")
                if ref_asset and ref_asset.asset_origin == REFERENCE_TEMPLATE_ASSET_ORIGIN:
                    stripped_asset += 1
                    actions.append(
                        RemoveReferenceAssetAction(
                            element_id=element.id,
                            reference_asset_id=ref_asset.id,
                            reference_relative_path=ref_asset.relative_path,
                            reason="reference_template asset must not appear in output scene",
                        )
                    )

                project_asset, visual_role, pool_idx = self._next_project_asset(
                    element=element,
                    pool=asset_pool,
                    photo_idx=photo_idx,
                    drawing_idx=drawing_idx,
                    plan=content_plan,
                )
                if (
                    element.element_type == ReferenceElementType.IMAGE
                    or self._placeholder_hosts_picture(element)
                ):
                    photo_idx = pool_idx
                else:
                    drawing_idx = pool_idx

                if project_asset is not None:
                    uri = project_asset.path.strip()
                    asset_manifest.append(
                        SceneAssetReference(
                            asset_id=project_asset.id,
                            storage_uri=uri,
                            asset_path=uri,
                            origin="project_upload",
                        )
                    )
                    if element.element_type == ReferenceElementType.DRAWING:
                        nodes.append(
                            DrawingNode(
                                id=element.id,
                                semantic_role=visual_role,
                                source_layout_element_id=element.id,
                                x=element.x,
                                y=element.y,
                                width=element.width,
                                height=element.height,
                                z_index=element.z_index,
                                asset_id=project_asset.id,
                                storage_uri=uri,
                                asset_path=uri,
                                drawing_type="site_plan",
                                asset_unresolved=False,
                            )
                        )
                    else:
                        nodes.append(
                            ImageNode(
                                id=element.id,
                                semantic_role=visual_role,
                                source_layout_element_id=element.id,
                                x=element.x,
                                y=element.y,
                                width=element.width,
                                height=element.height,
                                z_index=element.z_index,
                                asset_id=project_asset.id,
                                storage_uri=uri,
                                asset_path=uri,
                                asset_origin="project_upload",
                                fit_mode="cover",
                                asset_unresolved=False,
                            )
                        )
                    actions.append(
                        ReplaceAssetAction(
                            element_id=element.id,
                            visual_role=visual_role,
                            asset_id=project_asset.id,
                            storage_uri=uri,
                            reason=(
                                "semantic visual_evidence bind"
                                if content_plan.uses_semantic_contract
                                else "bind project asset to reference image slot"
                            ),
                        )
                    )
                else:
                    warning = (
                        f"no project asset for {element.element_type.value} slot {element.id}"
                    )
                    warnings.append(warning)
                    if element.element_type == ReferenceElementType.DRAWING:
                        nodes.append(
                            DrawingNode(
                                id=element.id,
                                semantic_role="drawing",
                                source_layout_element_id=element.id,
                                x=element.x,
                                y=element.y,
                                width=element.width,
                                height=element.height,
                                z_index=element.z_index,
                                asset_unresolved=True,
                            )
                        )
                    else:
                        nodes.append(
                            ImageNode(
                                id=element.id,
                                semantic_role="project_photo",
                                source_layout_element_id=element.id,
                                x=element.x,
                                y=element.y,
                                width=element.width,
                                height=element.height,
                                z_index=element.z_index,
                                asset_unresolved=True,
                            )
                        )
                continue

            if element.element_type in {
                ReferenceElementType.CHART,
                ReferenceElementType.TABLE,
            }:
                actions.append(
                    SkipUnsupportedAction(
                        element_id=element.id,
                        element_type=element.element_type.value,
                        warning="RenderScene V1 has no chart/table nodes",
                        reason="degrade unsupported reference element",
                    )
                )
                warnings.append(
                    f"skipped unsupported {element.element_type.value} element {element.id}"
                )
                continue

            if element.element_type == ReferenceElementType.SHAPE:
                nodes.append(self._decoration_node(element, design_system, locked=False))
                continue

        theme = ThemeTokens(
            colors={
                name: design_system.colors.resolve(name)
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
            spacing=design_system.spacing.model_dump(),
        )
        text_nodes = [node for node in nodes if isinstance(node, TextNode)]
        font_assets = collect_font_assets(design_system, text_nodes)

        scene = RenderScene(
            slide_id=slide_spec.id,
            presentation_id=presentation_id or slide_spec.presentation_id,
            layout_plan_id=uuid4(),
            page_width=reference_slide.width,
            page_height=reference_slide.height,
            background=BackgroundStyle(color=design_system.colors.resolve("background")),
            nodes=nodes,
            theme_tokens=theme,
            font_assets=font_assets,
            asset_manifest=asset_manifest,
            source_layout_family=layout.name if layout else content_schema.name,
            source_layout_variant=layout.page_type.value if layout else content_schema.content_type.value,
            warnings=warnings,
        )

        return ReferenceSlideEditResult(
            scene=scene,
            actions=actions,
            warnings=warnings,
            reference_content_stripped=True,
            stripped_text_count=stripped_text,
            stripped_asset_count=stripped_asset,
        )

    def _resolve_layout(
        self,
        template: ArchitecturalTemplate,
        layout_id: str | None,
        schema: ArchitecturalContentSchema,
    ) -> ArchitecturalTemplateLayout | None:
        if layout_id:
            for layout in template.layouts:
                if layout.id == layout_id:
                    return layout
        for layout in template.layouts:
            if layout.content_schema_id == schema.id:
                return layout
        for layout in template.layouts:
            if layout.representative_slide_id == schema.representative_slide_id:
                return layout
        return template.layouts[0] if template.layouts else None

    @staticmethod
    def _merge_context_assets(
        assets: list[Asset],
        generation_context: SlideGenerationContext | None,
    ) -> list[Asset]:
        if generation_context is None:
            return list(assets)
        merged = list(assets)
        seen = {asset.id for asset in merged}
        for asset in generation_context.relevant_assets:
            if asset.id in seen:
                continue
            seen.add(asset.id)
            merged.append(asset)
        return merged

    def _project_asset_pool(
        self,
        assets: list[Asset],
        schema: ArchitecturalContentSchema,
    ) -> dict[str, list[Asset]]:
        _ = schema  # schema constraints inform future origin filtering
        return {
            "photo": [a for a in assets if a.asset_type in _PHOTO_ASSET_TYPES],
            "drawing": [a for a in assets if a.asset_type in _DRAWING_ASSET_TYPES],
        }

    def _is_decoration(self, element: ReferenceElement) -> bool:
        if element.element_type == ReferenceElementType.DECORATION:
            return True
        if element.likely_background_or_decoration:
            return True
        return bool(element.repeats_across_pages)

    def _placeholder_hosts_picture(self, element: ReferenceElement) -> bool:
        if element.element_type != ReferenceElementType.PLACEHOLDER:
            return False
        if "placeholder_hosts_picture" in element.style_notes:
            return True
        binding = element.placeholder_binding
        if binding is None:
            return False
        return binding.placeholder_type in {
            "PICTURE",
            "BITMAP",
            "CLIP_ART",
            "MEDIA_CLIP",
        } or binding.semantic_role in {
            "hero_image",
            "supporting_image",
            "drawing",
        }

    def _resolve_text_role(self, element: ReferenceElement) -> str:
        role = effective_semantic_role(element)
        if role and role != "placeholder":
            return role
        if element.font_size_pt and element.font_size_pt >= 28:
            return ContentRole.TITLE.value
        if element.font_size_pt and element.font_size_pt <= 10:
            return ContentRole.CAPTION.value
        return ContentRole.BODY.value

    def _typography_for_role(
        self,
        role: str,
        design_system: DesignSystem,
    ) -> TextStyleToken:
        token_name = _ROLE_TO_TYPOGRAPHY.get(role, "body")
        return getattr(design_system.typography, token_name, design_system.typography.body)

    def _text_nodes(
        self,
        *,
        element: ReferenceElement,
        role: str,
        text: str,
        design_system: DesignSystem,
    ) -> list[TextNode]:
        if not text.strip():
            return []
        typography = self._typography_for_role(role, design_system)
        color_token = typography.color_token or "primary_text"
        color = design_system.colors.resolve(color_token)
        cjk_family = element.font_name or typography.font_family
        latin_family = typography.font_family_latin or typography.font_family
        resolved = resolve_text_fonts(
            text,
            cjk_family=cjk_family,
            latin_family=latin_family,
            bold=typography.font_weight >= 600,
        )
        return [
            TextNode(
                id=element.id,
                semantic_role=typography_role_for_semantic(role),
                source_layout_element_id=element.id,
                x=element.x,
                y=element.y,
                width=element.width,
                height=element.height,
                z_index=element.z_index,
                text=text,
                paragraphs=[TextParagraph(text=text, alignment=typography.alignment)],
                font_family=resolved.primary,
                font_family_cjk=resolved.cjk,
                font_family_latin=resolved.latin,
                font_size=element.font_size_pt or typography.font_size,
                font_weight=typography.font_weight,
                color=color,
                alignment=typography.alignment,
                line_height=typography.line_height,
                padding=BoxSpacing(left=4 / 96, right=4 / 96, top=2 / 96, bottom=2 / 96),
            )
        ]

    def _decoration_node(
        self,
        element: ReferenceElement,
        design_system: DesignSystem,
        *,
        locked: bool = True,
    ) -> ShapeNode:
        fill = element.fill_color or design_system.colors.resolve("surface")
        return ShapeNode(
            id=element.id,
            semantic_role="decoration",
            source_layout_element_id=element.id,
            x=element.x,
            y=element.y,
            width=element.width,
            height=element.height,
            z_index=element.z_index,
            locked=locked,
            lock_scopes=["geometry", "style"] if locked else [],
            shape_kind="rectangle",
            fill_color=fill,
            stroke_color=design_system.colors.resolve("border"),
            stroke_width=0,
        )

    def _next_project_asset(
        self,
        *,
        element: ReferenceElement,
        pool: dict[str, list[Asset]],
        photo_idx: int,
        drawing_idx: int,
        plan: SemanticContentPlan | None = None,
    ) -> tuple[Asset | None, str, int]:
        plan = plan or SemanticContentPlan()
        if element.element_type == ReferenceElementType.DRAWING:
            assets = pool["drawing"]
            idx = drawing_idx
            visual_role = "drawing"
        else:
            assets = pool["photo"]
            idx = photo_idx
            if plan.visual_evidence_roles and idx < len(plan.visual_evidence_roles):
                visual_role = plan.visual_evidence_roles[idx]
            else:
                visual_role = "hero_image" if idx == 0 else "supporting_image"
        if not assets:
            return None, visual_role, idx
        chosen = assets[idx % len(assets)]
        return chosen, visual_role, idx + 1

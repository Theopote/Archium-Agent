"""Apply explicit SlideAssetBinding overrides onto SlideSpec visual requirements."""

from __future__ import annotations

from uuid import UUID

from archium.domain.asset import Asset
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.slide_asset_binding import SlideAssetBinding, index_page_asset_bindings


def apply_slide_asset_bindings(
    slides: list[SlideSpec],
    bindings: list[SlideAssetBinding],
    *,
    assets_by_id: dict[UUID, Asset] | None = None,
) -> tuple[list[SlideSpec], list[SlideAssetBinding], int]:
    """Force user page→asset bindings onto slides matched by ``page_order`` / ``order``.

    Returns (slides, bindings_with_slide_id, applied_count).
    Explicit bindings are marked ``confirmed=True`` so auto-match will not overwrite them.
    """
    if not bindings:
        return slides, [], 0

    by_order = index_page_asset_bindings(bindings)
    known_assets = assets_by_id or {}
    applied = 0
    resolved: list[SlideAssetBinding] = []

    for slide in slides:
        page_bindings = by_order.get(slide.order, [])
        for binding in page_bindings:
            if known_assets and binding.asset_id not in known_assets:
                # Keep unresolved binding on outline; skip applying missing assets.
                resolved.append(binding.model_copy(update={"slide_id": slide.id}))
                continue
            if _apply_one_binding(slide, binding, asset=known_assets.get(binding.asset_id)):
                applied += 1
            resolved.append(binding.model_copy(update={"slide_id": slide.id}))

    # Preserve bindings for pages that have no matching slide yet.
    bound_orders = {slide.order for slide in slides}
    for binding in bindings:
        if binding.page_order not in bound_orders:
            resolved.append(binding)

    return slides, resolved, applied


def _apply_one_binding(
    slide: SlideSpec,
    binding: SlideAssetBinding,
    *,
    asset: Asset | None,
) -> bool:
    description = binding.user_description.strip()
    if not description and asset is not None:
        description = asset.description or asset.filename
    if not description:
        description = f"{binding.role_label()}（用户指定）"

    instruction = f"user_binding:{binding.binding_role.value}:{binding.asset_id}"
    requirement = _find_compatible_requirement(slide, binding)
    if requirement is None:
        requirement = VisualRequirement(
            type=binding.visual_type,
            description=description,
            preferred_asset_ids=[binding.asset_id],
            candidate_asset_ids=[binding.asset_id],
            match_score=1.0,
            confirmed=True,
            required=binding.required,
            processing_instructions=[instruction],
        )
        slide.visual_requirements.append(requirement)
        return True

    changed = False
    if requirement.preferred_asset_ids != [binding.asset_id]:
        requirement.preferred_asset_ids = [binding.asset_id]
        changed = True
    if binding.asset_id not in requirement.candidate_asset_ids:
        requirement.candidate_asset_ids = [
            binding.asset_id,
            *[aid for aid in requirement.candidate_asset_ids if aid != binding.asset_id],
        ][:5]
        changed = True
    if not requirement.confirmed:
        requirement.confirmed = True
        changed = True
    if requirement.required != binding.required:
        requirement.required = binding.required
        changed = True
    if requirement.match_score != 1.0:
        requirement.match_score = 1.0
        changed = True
    if description and requirement.description != description:
        # Prefer user description when provided; otherwise keep planner text.
        if binding.user_description.strip():
            requirement.description = description
            changed = True
    if instruction not in requirement.processing_instructions:
        requirement.processing_instructions.append(instruction)
        changed = True
    return changed


def _find_compatible_requirement(
    slide: SlideSpec,
    binding: SlideAssetBinding,
) -> VisualRequirement | None:
    """Prefer an existing unconfirmed requirement of the same visual type."""
    same_type = [
        req
        for req in slide.visual_requirements
        if req.type == binding.visual_type
    ]
    for req in same_type:
        if binding.asset_id in req.preferred_asset_ids or binding.asset_id in req.candidate_asset_ids:
            return req
    for req in same_type:
        if not req.confirmed:
            return req
    for req in same_type:
        if not req.preferred_asset_ids:
            return req
    return None

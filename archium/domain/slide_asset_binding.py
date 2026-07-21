"""Explicit per-page asset bindings — user overrides for material placement.

Users drag/assign project assets onto a planned page (by order) so generation and
asset matching respect ``page_materials``-style intent instead of guessing.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.enums import SlideAssetBindingRole, VisualType

# Role → VisualRequirement.type when materializing bindings onto SlideSpec.
BINDING_ROLE_TO_VISUAL_TYPE: dict[SlideAssetBindingRole, VisualType] = {
    SlideAssetBindingRole.PRIMARY_DRAWING: VisualType.SITE_PLAN,
    SlideAssetBindingRole.PROJECT_PHOTO: VisualType.SITE_PHOTO,
    SlideAssetBindingRole.SUPPORTING_PHOTO: VisualType.SITE_PHOTO,
    SlideAssetBindingRole.REFERENCE_CASE: VisualType.REFERENCE_CASE,
    SlideAssetBindingRole.METRIC_SOURCE: VisualType.CHART,
    SlideAssetBindingRole.BACKGROUND: VisualType.RENDERING,
    SlideAssetBindingRole.LOGO: VisualType.RENDERING,
}

_BINDING_ROLE_LABELS: dict[SlideAssetBindingRole, str] = {
    SlideAssetBindingRole.PRIMARY_DRAWING: "主图纸",
    SlideAssetBindingRole.PROJECT_PHOTO: "项目照片",
    SlideAssetBindingRole.SUPPORTING_PHOTO: "辅助照片",
    SlideAssetBindingRole.REFERENCE_CASE: "参考案例",
    SlideAssetBindingRole.METRIC_SOURCE: "指标数据源",
    SlideAssetBindingRole.BACKGROUND: "背景",
    SlideAssetBindingRole.LOGO: "Logo",
}


class SlideAssetBinding(DomainModel):
    """Bind one project asset to a planned page (Slide Intent Companion).

    ``page_order`` is the durable key before SlideSpec exists. ``slide_id`` is
    filled when the binding is applied after generation.
    """

    page_order: int = Field(ge=0)
    asset_id: UUID
    binding_role: SlideAssetBindingRole = SlideAssetBindingRole.PROJECT_PHOTO
    user_description: str = Field(default="", max_length=2000)
    required: bool = True
    slide_id: UUID | None = None

    @property
    def visual_type(self) -> VisualType:
        return BINDING_ROLE_TO_VISUAL_TYPE[self.binding_role]

    def role_label(self) -> str:
        return _BINDING_ROLE_LABELS.get(self.binding_role, self.binding_role.value)


def index_page_asset_bindings(
    bindings: list[SlideAssetBinding],
) -> dict[int, list[SlideAssetBinding]]:
    indexed: dict[int, list[SlideAssetBinding]] = {}
    for binding in bindings:
        indexed.setdefault(binding.page_order, []).append(binding)
    return indexed


def format_page_asset_bindings_block(
    bindings: list[SlideAssetBinding],
    *,
    asset_labels: dict[UUID, str] | None = None,
) -> str:
    """Human/LLM-readable block for generation prompts."""
    if not bindings:
        return ""
    labels = asset_labels or {}
    lines = ["【页面素材绑定 — 必须优先使用】"]
    for binding in sorted(bindings, key=lambda item: (item.page_order, item.binding_role.value)):
        name = labels.get(binding.asset_id, str(binding.asset_id))
        req = "必用" if binding.required else "建议"
        lines.append(
            f"- [{req}] {binding.role_label()} → {name}"
            f"（asset_id={binding.asset_id}）"
        )
        if binding.user_description.strip():
            lines.append(f"  说明：{binding.user_description.strip()}")
    return "\n".join(lines)


def slide_asset_bindings_from_page_materials(
    page_materials: dict[int, list[dict[str, object]]] | list[dict[str, object]],
) -> list[SlideAssetBinding]:
    """Parse PresentationRequest-style page_materials into bindings.

    Accepts either ``{page_index: [{asset_id, ...}, ...]}`` or a flat list of
    dicts containing ``page_index`` / ``page_order`` plus ``asset_id``.
    Entries without a resolvable ``asset_id`` are skipped (upload-only stubs).
    """
    rows: list[tuple[int, dict[str, object]]] = []
    if isinstance(page_materials, dict):
        for page_index, items in page_materials.items():
            for item in items or []:
                if isinstance(item, dict):
                    rows.append((int(page_index), item))
    else:
        for item in page_materials:
            if not isinstance(item, dict):
                continue
            raw_order = item.get("page_order", item.get("page_index", 0))
            rows.append((int(raw_order), item))

    bindings: list[SlideAssetBinding] = []
    for page_order, item in rows:
        asset_raw = item.get("asset_id")
        if asset_raw is None or str(asset_raw).strip() == "":
            continue
        try:
            asset_id = UUID(str(asset_raw))
        except ValueError:
            continue
        role_raw = str(item.get("binding_role") or item.get("type") or "project_photo")
        try:
            role = SlideAssetBindingRole(role_raw.strip().casefold())
        except ValueError:
            role = _infer_role_from_material_type(role_raw)
        description = str(
            item.get("user_description")
            or item.get("description")
            or item.get("filename")
            or ""
        ).strip()
        required = bool(item.get("required", True))
        bindings.append(
            SlideAssetBinding(
                page_order=page_order,
                asset_id=asset_id,
                binding_role=role,
                user_description=description[:2000],
                required=required,
            )
        )
    return bindings


def _infer_role_from_material_type(raw: str) -> SlideAssetBindingRole:
    token = raw.strip().casefold()
    if any(key in token for key in ("drawing", "图纸", "plan", "平面")):
        return SlideAssetBindingRole.PRIMARY_DRAWING
    if any(key in token for key in ("reference", "案例", "case")):
        return SlideAssetBindingRole.REFERENCE_CASE
    if any(key in token for key in ("excel", "chart", "metric", "指标", "table", "表格")):
        return SlideAssetBindingRole.METRIC_SOURCE
    if any(key in token for key in ("logo",)):
        return SlideAssetBindingRole.LOGO
    if any(key in token for key in ("background", "背景")):
        return SlideAssetBindingRole.BACKGROUND
    if any(key in token for key in ("support", "辅助")):
        return SlideAssetBindingRole.SUPPORTING_PHOTO
    return SlideAssetBindingRole.PROJECT_PHOTO

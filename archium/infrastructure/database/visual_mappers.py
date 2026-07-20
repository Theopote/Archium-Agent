"""ORM <-> domain mappers for visual composition entities."""

from __future__ import annotations

from archium.domain._base import model_to_dict
from archium.domain.visual.architectural_template import ArchitecturalTemplate
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.database.models import (
    ArchitecturalTemplateORM,
    ArtDirectionORM,
    DesignSystemORM,
    LayoutPlanORM,
    RenderSceneORM,
    VisualIntentORM,
)


def design_system_to_orm(
    domain: DesignSystem, target: DesignSystemORM | None = None
) -> DesignSystemORM:
    orm = target or DesignSystemORM(id=domain.id)
    orm.id = domain.id
    orm.name = domain.name
    orm.schema_version = domain.schema_version
    orm.version = domain.version
    orm.approval_status = domain.approval_status.value
    orm.source_type = domain.source_type.value
    orm.payload_json = model_to_dict(domain)
    orm.created_at = domain.created_at
    orm.updated_at = domain.updated_at
    return orm


def design_system_to_domain(orm: DesignSystemORM) -> DesignSystem:
    return DesignSystem.model_validate(orm.payload_json)


def art_direction_to_orm(
    domain: ArtDirection, target: ArtDirectionORM | None = None
) -> ArtDirectionORM:
    orm = target or ArtDirectionORM(id=domain.id)
    orm.id = domain.id
    orm.project_id = domain.project_id
    orm.presentation_id = domain.presentation_id
    orm.deliverable_id = domain.deliverable_id
    orm.design_system_id = domain.design_system_id
    orm.version = domain.version
    orm.approval_status = domain.approval_status.value
    orm.payload_json = model_to_dict(domain)
    orm.created_at = domain.created_at
    orm.updated_at = domain.updated_at
    return orm


def art_direction_to_domain(orm: ArtDirectionORM) -> ArtDirection:
    return ArtDirection.model_validate(orm.payload_json)


def visual_intent_to_orm(
    domain: VisualIntent, target: VisualIntentORM | None = None
) -> VisualIntentORM:
    orm = target or VisualIntentORM(id=domain.id)
    orm.id = domain.id
    orm.slide_id = domain.slide_id
    orm.presentation_id = domain.presentation_id
    orm.art_direction_id = domain.art_direction_id
    orm.version = domain.version
    orm.approval_status = domain.approval_status.value
    orm.payload_json = model_to_dict(domain)
    orm.created_at = domain.created_at
    orm.updated_at = domain.updated_at
    return orm


def visual_intent_to_domain(orm: VisualIntentORM) -> VisualIntent:
    return VisualIntent.model_validate(orm.payload_json)


def layout_plan_to_orm(
    domain: LayoutPlan, target: LayoutPlanORM | None = None
) -> LayoutPlanORM:
    orm = target or LayoutPlanORM(id=domain.id)
    orm.id = domain.id
    orm.slide_id = domain.slide_id
    orm.design_system_id = domain.design_system_id
    orm.visual_intent_id = domain.visual_intent_id
    orm.layout_family = domain.layout_family.value
    orm.layout_variant = domain.layout_variant
    orm.schema_version = domain.schema_version
    orm.version = domain.version
    orm.validation_status = domain.validation_status.value
    orm.payload_json = model_to_dict(domain)
    orm.created_at = domain.created_at
    orm.updated_at = domain.updated_at
    return orm


def layout_plan_to_domain(orm: LayoutPlanORM) -> LayoutPlan:
    return LayoutPlan.model_validate(orm.payload_json)


def render_scene_to_orm(
    domain: RenderScene, target: RenderSceneORM | None = None
) -> RenderSceneORM:
    orm = target or RenderSceneORM(id=domain.id)
    orm.id = domain.id
    orm.slide_id = domain.slide_id
    orm.layout_plan_id = domain.layout_plan_id
    orm.schema_version = domain.schema_version
    orm.version = domain.version
    orm.scene_hash = compute_scene_hash(domain)
    orm.payload_json = model_to_dict(domain)
    orm.created_at = domain.created_at
    orm.updated_at = domain.updated_at
    return orm


def render_scene_to_domain(orm: RenderSceneORM) -> RenderScene:
    return RenderScene.model_validate(orm.payload_json)


def architectural_template_to_orm(
    domain: ArchitecturalTemplate,
    target: ArchitecturalTemplateORM | None = None,
) -> ArchitecturalTemplateORM:
    orm = target or ArchitecturalTemplateORM(id=domain.id)
    orm.id = domain.id
    orm.name = domain.name
    orm.project_id = domain.project_id
    orm.design_system_id = domain.design_system_id
    orm.status = domain.status.value
    orm.version = domain.version
    orm.source_pptx_path = domain.source_pptx_path
    orm.payload_json = model_to_dict(domain)
    orm.created_at = domain.created_at
    orm.updated_at = domain.updated_at
    return orm


def architectural_template_to_domain(orm: ArchitecturalTemplateORM) -> ArchitecturalTemplate:
    return ArchitecturalTemplate.model_validate(orm.payload_json)

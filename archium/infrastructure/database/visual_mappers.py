"""ORM <-> domain mappers for visual composition entities."""

from __future__ import annotations

from uuid import UUID

from archium.domain._base import model_to_dict, utc_now
from archium.domain.visual.architectural_template import ArchitecturalTemplate
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.deck_theme_tokens import DeckThemeTokens
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.element_comment import ElementComment, ElementCommentStatus
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.page_quality import QualityIssue
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash
from archium.domain.visual.scene_change_proposal import (
    ProposalDecision,
    ProposalStatus,
    SceneChangeProposal,
)
from archium.domain.visual.theme_change_proposal import (
    ThemeChangeProposal,
    ThemeProposalDecision,
    ThemeProposalStatus,
)
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.database.models import (
    ArchitecturalTemplateORM,
    ArtDirectionORM,
    DesignSystemORM,
    ElementCommentORM,
    LayoutPlanORM,
    RenderSceneORM,
    SceneChangeProposalORM,
    ThemeChangeProposalORM,
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


def _models_to_json(items: list[object]) -> list[dict[str, object]]:
    return [
        model_to_dict(item)  # type: ignore[arg-type]
        for item in items
        if hasattr(item, "model_dump")
    ]


def _scene_change_proposal_payload(proposal: SceneChangeProposal) -> dict[str, object]:
    return {
        "commands": _models_to_json(proposal.commands),
        "requested_commands": _models_to_json(proposal.requested_commands),
        "successful_commands": _models_to_json(proposal.successful_commands),
        "failed_commands": _models_to_json(proposal.failed_commands),
        "command_results": _models_to_json(proposal.command_results),
        "patch_actions": _models_to_json(proposal.patch_actions),
        "reasons": proposal.reasons,
        "qa_before": _models_to_json(proposal.qa_before),
        "qa_after": _models_to_json(proposal.qa_after),
        "qa_before_by_layer": {
            layer: _models_to_json(items)
            for layer, items in proposal.qa_before_by_layer.items()
        },
        "qa_after_by_layer": {
            layer: _models_to_json(items)
            for layer, items in proposal.qa_after_by_layer.items()
        },
        "decision": model_to_dict(proposal.decision) if proposal.decision is not None else None,
        "preservation": (
            model_to_dict(proposal.preservation) if proposal.preservation is not None else None
        ),
    }


def scene_change_proposal_to_orm(
    proposal: SceneChangeProposal,
    *,
    base_scene_id: UUID,
    proposed_scene_id: UUID,
    target: SceneChangeProposalORM | None = None,
) -> SceneChangeProposalORM:
    orm = target or SceneChangeProposalORM(id=proposal.proposal_id)
    orm.id = proposal.proposal_id
    orm.presentation_id = proposal.presentation_id
    orm.slide_id = proposal.slide_id
    orm.base_revision_id = proposal.base_revision_id
    orm.base_scene_id = base_scene_id
    orm.proposed_scene_id = proposed_scene_id
    orm.base_scene_hash = proposal.base_scene_hash
    orm.status = proposal.status.value
    orm.decided_at = proposal.decided_at
    orm.payload_json = _scene_change_proposal_payload(proposal)
    orm.created_at = proposal.created_at
    orm.updated_at = utc_now()
    return orm


def scene_change_proposal_to_domain(
    orm: SceneChangeProposalORM,
    *,
    base_scene: RenderScene,
    proposed_scene: RenderScene,
) -> SceneChangeProposal:
    payload = orm.payload_json
    decision_payload = payload.get("decision")
    decision = (
        ProposalDecision.model_validate(decision_payload)
        if isinstance(decision_payload, dict)
        else None
    )
    preservation_payload = payload.get("preservation")
    preservation = None
    if isinstance(preservation_payload, dict):
        from archium.domain.visual.partial_edit_preservation import (
            PartialEditPreservationReport,
        )

        preservation = PartialEditPreservationReport.model_validate(preservation_payload)
    return SceneChangeProposal(
        proposal_id=orm.id,
        presentation_id=orm.presentation_id,
        slide_id=orm.slide_id,
        base_revision_id=orm.base_revision_id,
        base_scene_id=orm.base_scene_id,
        proposed_scene_id=orm.proposed_scene_id,
        base_scene_hash=orm.base_scene_hash,
        base_scene=base_scene,
        proposed_scene=proposed_scene,
        commands=payload.get("commands") or payload.get("successful_commands") or [],
        requested_commands=payload.get("requested_commands") or [],
        successful_commands=payload.get("successful_commands") or payload.get("commands") or [],
        failed_commands=payload.get("failed_commands") or [],
        command_results=payload.get("command_results") or [],
        patch_actions=payload.get("patch_actions") or [],
        reasons=list(payload.get("reasons") or []),
        qa_before=payload.get("qa_before") or [],
        qa_after=payload.get("qa_after") or [],
        qa_before_by_layer=payload.get("qa_before_by_layer") or {},
        qa_after_by_layer=payload.get("qa_after_by_layer") or {},
        preservation=preservation,
        status=ProposalStatus(orm.status),
        decision=decision,
        decided_at=orm.decided_at,
        created_at=orm.created_at,
    )


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


def element_comment_to_orm(
    domain: ElementComment,
    target: ElementCommentORM | None = None,
) -> ElementCommentORM:
    orm = target or ElementCommentORM(id=domain.id)
    orm.id = domain.id
    orm.presentation_id = domain.presentation_id
    orm.slide_id = domain.slide_id
    orm.node_id = domain.node_id
    orm.layout_element_id = domain.layout_element_id
    orm.note = domain.note
    orm.status = domain.status.value
    orm.scene_revision_id = domain.scene_revision_id
    orm.scene_hash = domain.scene_hash or ""
    orm.node_snapshot_json = dict(domain.node_snapshot_json or {})
    orm.proposal_id = domain.proposal_id
    orm.created_by = domain.created_by
    orm.created_at = domain.created_at
    orm.updated_at = domain.updated_at
    return orm


def element_comment_to_domain(orm: ElementCommentORM) -> ElementComment:
    snapshot = orm.node_snapshot_json if isinstance(orm.node_snapshot_json, dict) else {}
    return ElementComment(
        id=orm.id,
        presentation_id=orm.presentation_id,
        slide_id=orm.slide_id,
        node_id=orm.node_id,
        layout_element_id=orm.layout_element_id,
        note=orm.note,
        status=ElementCommentStatus(orm.status),
        scene_revision_id=orm.scene_revision_id,
        scene_hash=orm.scene_hash or "",
        node_snapshot_json=dict(snapshot),
        proposal_id=orm.proposal_id,
        created_by=orm.created_by,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _theme_change_proposal_payload(proposal: ThemeChangeProposal) -> dict[str, object]:
    qa_by_slide: dict[str, list[dict[str, object]]] = {}
    for slide_id, issues in proposal.qa_by_slide.items():
        qa_by_slide[slide_id] = _models_to_json(issues)  # type: ignore[arg-type]
    return {
        "token_patch": model_to_dict(proposal.token_patch),
        "sample_slide_ids": [str(item) for item in proposal.sample_slide_ids],
        "preview_scene_hashes": proposal.preview_scene_hashes,
        "qa_by_slide": qa_by_slide,
        "qa_summary": _models_to_json(proposal.qa_summary),
        "decision": (
            model_to_dict(proposal.decision) if proposal.decision is not None else None
        ),
    }


def theme_change_proposal_to_orm(
    proposal: ThemeChangeProposal,
    *,
    base_design_system_id: UUID,
    proposed_design_system_id: UUID,
    target: ThemeChangeProposalORM | None = None,
) -> ThemeChangeProposalORM:
    orm = target or ThemeChangeProposalORM(id=proposal.proposal_id)
    orm.id = proposal.proposal_id
    orm.presentation_id = proposal.presentation_id
    orm.art_direction_id = proposal.art_direction_id
    orm.base_design_system_id = base_design_system_id
    orm.proposed_design_system_id = proposed_design_system_id
    orm.status = proposal.status.value
    orm.decided_at = proposal.decided_at
    orm.payload_json = _theme_change_proposal_payload(proposal)
    orm.created_at = proposal.created_at
    orm.updated_at = utc_now()
    return orm


def theme_change_proposal_to_domain(
    orm: ThemeChangeProposalORM,
    *,
    base_design_system: DesignSystem,
    proposed_design_system: DesignSystem,
) -> ThemeChangeProposal:
    payload = orm.payload_json or {}
    decision_payload = payload.get("decision")
    decision = (
        ThemeProposalDecision.model_validate(decision_payload)
        if isinstance(decision_payload, dict)
        else None
    )
    token_payload = payload.get("token_patch") or {}
    token_patch = DeckThemeTokens.model_validate(
        token_payload if isinstance(token_payload, dict) else {}
    )
    qa_summary_raw = payload.get("qa_summary") or []
    qa_summary = [
        QualityIssue.model_validate(item)
        for item in qa_summary_raw
        if isinstance(item, dict)
    ]
    qa_by_slide_raw = payload.get("qa_by_slide") or {}
    qa_by_slide: dict[str, list[QualityIssue]] = {}
    if isinstance(qa_by_slide_raw, dict):
        for slide_key, issues in qa_by_slide_raw.items():
            if not isinstance(issues, list):
                continue
            qa_by_slide[str(slide_key)] = [
                QualityIssue.model_validate(item)
                for item in issues
                if isinstance(item, dict)
            ]
    sample_raw = payload.get("sample_slide_ids") or []
    sample_slide_ids: list[UUID] = []
    if isinstance(sample_raw, list):
        for item in sample_raw:
            try:
                sample_slide_ids.append(UUID(str(item)))
            except (TypeError, ValueError):
                continue
    hashes = payload.get("preview_scene_hashes") or {}
    return ThemeChangeProposal(
        proposal_id=orm.id,
        presentation_id=orm.presentation_id,
        art_direction_id=orm.art_direction_id,
        base_design_system_id=orm.base_design_system_id,
        proposed_design_system_id=orm.proposed_design_system_id,
        base_design_system=base_design_system,
        proposed_design_system=proposed_design_system,
        token_patch=token_patch,
        sample_slide_ids=sample_slide_ids,
        preview_scene_hashes=hashes if isinstance(hashes, dict) else {},
        qa_by_slide=qa_by_slide,
        qa_summary=qa_summary,
        status=ThemeProposalStatus(orm.status),
        decision=decision,
        decided_at=orm.decided_at,
        created_at=orm.created_at,
    )


def architectural_template_to_domain(orm: ArchitecturalTemplateORM) -> ArchitecturalTemplate:
    return ArchitecturalTemplate.model_validate(orm.payload_json)

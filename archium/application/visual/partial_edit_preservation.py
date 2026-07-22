"""Enforce partial-edit preservation rules on Before/After scene pairs."""

from __future__ import annotations

from uuid import UUID

from archium.domain.slide import SlideSpec
from archium.domain.visual.partial_edit_preservation import (
    PARTIAL_EDIT_INTERACTION_RULE,
    PartialEditPreservationReport,
    PartialEditPreservationRule,
    PreservationViolation,
)
from archium.domain.visual.render_scene import (
    BaseRenderNode,
    DrawingNode,
    ImageNode,
    RenderScene,
    TextNode,
)
from archium.domain.visual.studio_command import (
    AlignNodesCommand,
    DeleteNodeCommand,
    FixOverflowCommand,
    IncreaseDrawingReadabilityCommand,
    MoveNodeCommand,
    ReorderNodeCommand,
    ReplaceAssetCommand,
    ReplaceDrawingCommand,
    ResizeNodeCommand,
    RewriteTextCommand,
    ScenePatchAction,
    SetNodeLockCommand,
    SetNodeVisibilityCommand,
    StudioCommand,
    UpdateNodeStyleCommand,
)
from archium.exceptions import WorkflowError

_SOURCE_ROLES = frozenset({"source", "citation", "footnote", "来源", "引用"})
_ASSET_REPLACE_TYPES = frozenset({"replace_asset", "replace_drawing"})


def command_target_node_ids(command: StudioCommand) -> set[str]:
    """Nodes explicitly mentioned by a StudioCommand."""
    targets: set[str] = set(command.target_node_ids)
    if isinstance(command, RewriteTextCommand):
        targets.add(command.node_id)
    elif isinstance(command, FixOverflowCommand):
        if command.node_ids:
            targets.update(command.node_ids)
    elif isinstance(
        command,
        (
            ReplaceAssetCommand,
            ReplaceDrawingCommand,
            IncreaseDrawingReadabilityCommand,
            MoveNodeCommand,
            ResizeNodeCommand,
            DeleteNodeCommand,
            ReorderNodeCommand,
            SetNodeLockCommand,
            SetNodeVisibilityCommand,
            UpdateNodeStyleCommand,
        ),
    ):
        targets.add(command.node_id)
    elif isinstance(command, AlignNodesCommand):
        targets.update(command.node_ids)
    return {node_id for node_id in targets if node_id.strip()}


def collect_allowed_node_ids(
    commands: list[StudioCommand],
    *,
    patch_actions: list[ScenePatchAction] | None = None,
) -> set[str]:
    """Union of command targets and nodes actually patched by those commands."""
    allowed: set[str] = set()
    for command in commands:
        allowed |= command_target_node_ids(command)
    if patch_actions:
        command_ids = {command.command_id for command in commands}
        for action in patch_actions:
            if (
                (action.command_id is None or action.command_id in command_ids)
                and action.node_id.strip()
            ):
                allowed.add(action.node_id)
    return allowed


def asset_replace_node_ids(commands: list[StudioCommand]) -> set[str]:
    return {
        node_id
        for command in commands
        if command.command_type in _ASSET_REPLACE_TYPES
        for node_id in command_target_node_ids(command)
    }


def changed_node_ids(base: RenderScene, proposed: RenderScene) -> set[str]:
    base_by_id = {node.id: node for node in base.nodes}
    proposed_by_id = {node.id: node for node in proposed.nodes}
    changed: set[str] = set()
    for node_id in set(base_by_id) | set(proposed_by_id):
        before = base_by_id.get(node_id)
        after = proposed_by_id.get(node_id)
        if before is None or after is None:
            changed.add(node_id)
            continue
        if _node_fingerprint(before) != _node_fingerprint(after):
            changed.add(node_id)
    return changed


def evaluate_partial_edit_preservation(
    base: RenderScene,
    proposed: RenderScene,
    *,
    commands: list[StudioCommand],
    patch_actions: list[ScenePatchAction] | None = None,
    slide_before: SlideSpec | None = None,
    slide_after: SlideSpec | None = None,
) -> PartialEditPreservationReport:
    """Compare before/after scenes against the partial-edit contract."""
    allowed = collect_allowed_node_ids(commands, patch_actions=patch_actions)
    changed = changed_node_ids(base, proposed)
    replace_targets = asset_replace_node_ids(commands)
    violations: list[PreservationViolation] = []

    # 1) Unspecified nodes must not change.
    for node_id in sorted(changed - allowed):
        violations.append(
            PreservationViolation(
                rule=PartialEditPreservationRule.UNSPECIFIED_NODES_UNCHANGED,
                message=f"未指定节点 `{node_id}` 发生了变更。",
                node_id=node_id,
                detail=PARTIAL_EDIT_INTERACTION_RULE,
            )
        )

    # 2) Locked nodes must not change.
    base_by_id = {node.id: node for node in base.nodes}
    for node_id in sorted(changed):
        before = base_by_id.get(node_id)
        if before is None:
            continue
        if before.locked or "all" in before.lock_scopes:
            violations.append(
                PreservationViolation(
                    rule=PartialEditPreservationRule.LOCKED_NODES_UNCHANGED,
                    message=f"锁定节点 `{node_id}` 发生了变更。",
                    node_id=node_id,
                )
            )

    # 3) Asset identity preserved unless explicit replace.
    for node_id, before, after in _iter_paired_nodes(base, proposed):
        if not isinstance(before, (ImageNode, DrawingNode)):
            continue
        if not isinstance(after, (ImageNode, DrawingNode)):
            continue
        if node_id in replace_targets:
            continue
        if _asset_identity(before) != _asset_identity(after):
            violations.append(
                PreservationViolation(
                    rule=PartialEditPreservationRule.ASSET_IDENTITY_UNCHANGED,
                    message=f"节点 `{node_id}` 的素材身份被悄然替换。",
                    node_id=node_id,
                    detail=(
                        f"before={_asset_identity(before)} after={_asset_identity(after)}"
                    ),
                )
            )

    # 4) Page facts stay unchanged (SlideSpec message / key_points).
    if slide_before is not None and slide_after is not None:
        if slide_before.message.strip() != slide_after.message.strip():
            violations.append(
                PreservationViolation(
                    rule=PartialEditPreservationRule.PAGE_FACTS_UNCHANGED,
                    message="页面中心结论（SlideSpec.message）在单页微调中被修改。",
                )
            )
        if list(slide_before.key_points) != list(slide_after.key_points):
            violations.append(
                PreservationViolation(
                    rule=PartialEditPreservationRule.PAGE_FACTS_UNCHANGED,
                    message="页面要点（SlideSpec.key_points）在单页微调中被修改。",
                )
            )

    # 5) Citations stay unchanged.
    if slide_before is not None and slide_after is not None:
        before_cites = [cite.model_dump(mode="json") for cite in slide_before.source_citations]
        after_cites = [cite.model_dump(mode="json") for cite in slide_after.source_citations]
        if before_cites != after_cites:
            violations.append(
                PreservationViolation(
                    rule=PartialEditPreservationRule.CITATIONS_UNCHANGED,
                    message="页面引用（SlideSpec.source_citations）在单页微调中被修改。",
                )
            )

    for node_id, before, after in _iter_paired_nodes(base, proposed):
        if not isinstance(before, TextNode) or not isinstance(after, TextNode):
            continue
        role = (before.semantic_role or "").strip().casefold()
        if role not in _SOURCE_ROLES and "source" not in role and "citation" not in role:
            continue
        if node_id in allowed:
            # Explicitly targeted source node may be rewritten only if user asked.
            continue
        if before.text != after.text or list(before.paragraphs) != list(after.paragraphs):
            violations.append(
                PreservationViolation(
                    rule=PartialEditPreservationRule.CITATIONS_UNCHANGED,
                    message=f"来源/引用节点 `{node_id}` 在未指定时被修改。",
                    node_id=node_id,
                )
            )

    return PartialEditPreservationReport(
        allowed_node_ids=sorted(allowed),
        changed_node_ids=sorted(changed),
        violations=violations,
    )


def assert_partial_edit_preservation(
    base: RenderScene,
    proposed: RenderScene,
    *,
    commands: list[StudioCommand],
    patch_actions: list[ScenePatchAction] | None = None,
    slide_before: SlideSpec | None = None,
    slide_after: SlideSpec | None = None,
) -> PartialEditPreservationReport:
    """Evaluate and raise if the partial-edit contract is broken."""
    report = evaluate_partial_edit_preservation(
        base,
        proposed,
        commands=commands,
        patch_actions=patch_actions,
        slide_before=slide_before,
        slide_after=slide_after,
    )
    if report.ok:
        return report
    messages = [violation.message for violation in report.violations]
    raise WorkflowError(
        "单页微调违反保护规则（只修改我提到的部分）：" + "；".join(messages)
    )


def _iter_paired_nodes(
    base: RenderScene,
    proposed: RenderScene,
) -> list[tuple[str, BaseRenderNode, BaseRenderNode]]:
    base_by_id = {node.id: node for node in base.nodes}
    proposed_by_id = {node.id: node for node in proposed.nodes}
    paired: list[tuple[str, BaseRenderNode, BaseRenderNode]] = []
    for node_id in sorted(set(base_by_id) & set(proposed_by_id)):
        paired.append((node_id, base_by_id[node_id], proposed_by_id[node_id]))
    return paired


def _asset_identity(node: ImageNode | DrawingNode) -> tuple[UUID | None, str]:
    return (node.asset_id, (node.storage_uri or node.asset_path or "").strip())


def _node_fingerprint(node: BaseRenderNode) -> str:
    """Stable content fingerprint for change detection (excludes volatile ids)."""
    payload = node.model_dump(mode="json")
    return repr(sorted(payload.items()))

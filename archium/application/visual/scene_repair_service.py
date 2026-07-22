"""Deterministic RenderScene repair from semantic QA findings (Scene Repair Loop).

Two apply modes (see ``SceneRepairApplyMode``):

- **SAFE_AUTO_ONLY** — Studio compile/reuse and workflow persistence. Only
  lossless fixes that do not change content semantics (e.g. drawing cover→contain).
- **ALL_REPAIRABLE** — Proposal path (``FixOverflowCommand``) where the user
  reviews before/after. Includes text shorten, font bump, overflow shrink.
"""

from __future__ import annotations

from uuid import UUID

from archium.application.slide_repair_policy import smart_shorten_text
from archium.application.visual.scene_semantic_qa_service import run_scene_semantic_qa
from archium.domain.slide_semantic_qa import SlideSemanticFinding
from archium.domain.visual.render_scene import (
    DrawingNode,
    ImageNode,
    RenderScene,
    TextNode,
    replace_text_node_content,
)
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.domain.visual.scene_repair import (
    PROPOSAL_REQUIRED_REPAIR_CODES,
    SceneRepairAction,
    SceneRepairApplyMode,
    SceneRepairBatchResult,
    SceneRepairResult,
)

_CHARS_PER_INCH_AT_12PT = 12.0
_MIN_READABLE_FONT_PT = 10.0
_REPAIRABLE_CODES = frozenset(
    {
        SceneSemanticCheckCode.TEXT_OVERFLOW,
        SceneSemanticCheckCode.FONT_TOO_SMALL,
        SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN,
    }
)


def proposal_required_findings(
    findings: list[SlideSemanticFinding],
) -> list[SlideSemanticFinding]:
    """Findings that must be resolved via Studio Proposal, not auto-repair."""
    return [
        finding
        for finding in findings
        if finding.check_code in PROPOSAL_REQUIRED_REPAIR_CODES
    ]


def summarize_deferred_repair(finding: SlideSemanticFinding) -> str:
    if finding.check_code == SceneSemanticCheckCode.TEXT_OVERFLOW:
        nodes = ", ".join(finding.evidence_refs or []) or "文本节点"
        return f"文本溢出（{nodes}）"
    if finding.check_code == SceneSemanticCheckCode.FONT_TOO_SMALL:
        nodes = ", ".join(finding.evidence_refs or []) or "文本节点"
        return f"字体过小（{nodes}）"
    return finding.title or finding.check_code


class SceneRepairService:
    """Apply bounded, deterministic patches to RenderScene after semantic QA."""

    def repair_scene(
        self,
        scene: RenderScene,
        findings: list[SlideSemanticFinding],
        *,
        apply_mode: SceneRepairApplyMode = SceneRepairApplyMode.SAFE_AUTO_ONLY,
    ) -> SceneRepairResult:
        actions: list[SceneRepairAction] = []
        patched = scene.model_copy(deep=True)
        by_node: dict[str, list[SlideSemanticFinding]] = {}
        for finding in findings:
            if finding.check_code not in _REPAIRABLE_CODES:
                continue
            for node_id in finding.evidence_refs or []:
                by_node.setdefault(node_id, []).append(finding)

        for node_id, node_findings in by_node.items():
            node = patched.node_by_id(node_id)
            if node is None:
                continue
            for finding in node_findings:
                action = self._repair_node(patched, node_id, finding, apply_mode=apply_mode)
                if action is not None:
                    actions.append(action)

        return SceneRepairResult(scene=patched, actions=actions, applied_count=len(actions))

    def repair_deck(
        self,
        presentation_id: UUID,
        scenes: list[RenderScene],
        *,
        max_rounds: int = 2,
        slide_orders: dict[UUID, int] | None = None,
        apply_mode: SceneRepairApplyMode = SceneRepairApplyMode.SAFE_AUTO_ONLY,
    ) -> SceneRepairBatchResult:
        """QA → repair loop, up to ``max_rounds`` (default 2)."""
        current = [scene.model_copy(deep=True) for scene in scenes]
        all_actions: list[SceneRepairAction] = []
        rounds = 0
        orders = slide_orders or {}

        for _ in range(max(0, max_rounds)):
            report = run_scene_semantic_qa(
                presentation_id,
                current,
                slide_orders=orders,
            )
            repairable = [
                finding
                for finding in report.findings
                if finding.check_code in _REPAIRABLE_CODES
            ]
            if not repairable:
                break

            rounds += 1
            by_scene: dict[UUID, list[SlideSemanticFinding]] = {}
            for finding in repairable:
                if finding.slide_id is None:
                    continue
                by_scene.setdefault(finding.slide_id, []).append(finding)

            updated: list[RenderScene] = []
            for scene in current:
                scene_findings = by_scene.get(scene.slide_id, [])
                if not scene_findings:
                    updated.append(scene)
                    continue
                result = self.repair_scene(scene, scene_findings, apply_mode=apply_mode)
                all_actions.extend(result.actions)
                updated.append(result.scene)
            current = updated

        final_report = run_scene_semantic_qa(
            presentation_id,
            current,
            slide_orders=orders,
        )
        remaining = sum(
            1
            for finding in final_report.findings
            if finding.check_code in _REPAIRABLE_CODES
        )
        deferred = proposal_required_findings(final_report.findings)
        return SceneRepairBatchResult(
            scenes=current,
            actions=all_actions,
            rounds=rounds,
            remaining_issue_count=remaining,
            deferred_findings=deferred,
        )

    def _repair_node(
        self,
        scene: RenderScene,
        node_id: str,
        finding: SlideSemanticFinding,
        *,
        apply_mode: SceneRepairApplyMode,
    ) -> SceneRepairAction | None:
        node = scene.node_by_id(node_id)
        if node is None:
            return None

        if finding.check_code == SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN:
            if isinstance(node, (DrawingNode, ImageNode)) and node.fit_mode == "cover":
                node.fit_mode = "contain"
                return SceneRepairAction(
                    scene_id=scene.slide_id,
                    node_id=node_id,
                    check_code=finding.check_code,
                    action_type="set_fit_mode_contain",
                    reason="drawing must not use cover",
                )
            return None

        if apply_mode == SceneRepairApplyMode.SAFE_AUTO_ONLY:
            return None

        if finding.check_code == SceneSemanticCheckCode.FONT_TOO_SMALL and isinstance(node, TextNode):
            bumped = max(node.font_size, _MIN_READABLE_FONT_PT)
            if bumped <= node.font_size:
                return None
            node.font_size = bumped
            return SceneRepairAction(
                scene_id=scene.slide_id,
                node_id=node_id,
                check_code=finding.check_code,
                action_type="bump_font_size",
                reason=f"raised font to {bumped}pt",
            )

        if finding.check_code == SceneSemanticCheckCode.TEXT_OVERFLOW and isinstance(node, TextNode):
            scale = max(node.font_size, 1.0) / 12.0
            capacity = int(
                max(1.0, node.width * _CHARS_PER_INCH_AT_12PT / scale)
                * max(1.0, node.height / (node.line_height * node.font_size / 72.0))
            )
            limit = max(8, capacity)
            shortened, applied, reason = smart_shorten_text(node.text or "", limit)
            if applied and shortened != node.text:
                replace_text_node_content(node, shortened)
                return SceneRepairAction(
                    scene_id=scene.slide_id,
                    node_id=node_id,
                    check_code=finding.check_code,
                    action_type="shorten_text",
                    reason=reason,
                )
            if node.overflow_policy == "error":
                node.overflow_policy = "shrink"
                return SceneRepairAction(
                    scene_id=scene.slide_id,
                    node_id=node_id,
                    check_code=finding.check_code,
                    action_type="set_overflow_shrink",
                    reason="text could not be shortened safely",
                )
        return None

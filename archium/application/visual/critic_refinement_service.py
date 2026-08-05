"""VQ-007: Screenshot / structure Critic → bounded allowlisted scene refinements.

Loop contract:
  evaluate (VisualCriticService) → propose (closed map) → apply (≤N actions)
  → optional re-evaluate → stop (max rounds).

Never calls LayoutRepairService. Never free-rewrites copy via LLM.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from archium.application.visual.visual_critic_service import VisualCriticService
from archium.domain.visual.critic import VisualCriticReport
from archium.domain.visual.critic_refinement import (
    CRITIC_CODE_TO_ACTIONS,
    DEFAULT_REFINEMENT_ROUNDS,
    MAX_ACTIONS_PER_DECK,
    MAX_ACTIONS_PER_PAGE,
    MAX_REFINEMENT_ROUNDS,
    VisualRefinementAction,
    VisualRefinementActionType,
    VisualRefinementDeckResult,
    VisualRefinementLoopResult,
    VisualRefinementProposal,
    VisualRefinementRound,
)
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import (
    ImageNode,
    RenderScene,
    ShapeNode,
    TextNode,
    TextRun,
    set_text_node_runs,
)
from archium.logging import get_logger

logger = get_logger(__name__, operation="critic_refinement")

_TITLE_ROLES = frozenset({"title", "section_title", "cover_title"})
_BODY_ROLES = frozenset({"body", "body_text", "lead", "lead_statement", "caption", "annotation"})
_HERO_ROLES = frozenset({"hero", "hero_visual", "project_photo", "cover_image"})


class CriticRefinementService:
    """Map Visual Critic findings to allowlisted RenderScene patches."""

    def __init__(self, critic: VisualCriticService | None = None) -> None:
        self._critic = critic or VisualCriticService()

    def propose(
        self,
        report: VisualCriticReport,
        scene: RenderScene,
        *,
        max_actions: int = MAX_ACTIONS_PER_PAGE,
    ) -> VisualRefinementProposal:
        """Build a capped proposal from critic findings (no application)."""
        cap = max(0, min(int(max_actions), MAX_ACTIONS_PER_PAGE))
        actions: list[VisualRefinementAction] = []
        deferred: list[str] = []
        seen: set[VisualRefinementActionType] = set()

        for finding in report.findings:
            mapped = CRITIC_CODE_TO_ACTIONS.get(finding.rule_code)
            if not mapped:
                deferred.append(finding.rule_code)
                continue
            for action_type in mapped:
                if action_type in seen:
                    continue
                target = self._resolve_target(scene, action_type)
                if target is None and action_type not in {
                    VisualRefinementActionType.QUIET_MOTIF,
                    VisualRefinementActionType.SOFTEN_ACCENT_SHAPES,
                    VisualRefinementActionType.FIX_TEXT_CONTRAST,
                }:
                    continue
                magnitude = _default_magnitude(action_type)
                actions.append(
                    VisualRefinementAction(
                        action_type=action_type,
                        rule_code=finding.rule_code,
                        target_node_id=target,
                        magnitude=magnitude,
                        reason=finding.suggestion or finding.message,
                    )
                )
                seen.add(action_type)
                if len(actions) >= cap:
                    break
            if len(actions) >= cap:
                break

        return VisualRefinementProposal(
            slide_id=report.slide_id,
            layout_plan_id=report.layout_plan_id,
            source_score=report.total_score,
            actions=actions,
            deferred_codes=sorted(set(deferred)),
        )

    def apply(
        self,
        scene: RenderScene,
        actions: list[VisualRefinementAction],
    ) -> tuple[RenderScene, list[VisualRefinementAction]]:
        """Apply allowlisted actions; unknown types are skipped."""
        patched = scene.model_copy(deep=True)
        applied: list[VisualRefinementAction] = []
        for action in actions:
            if action.action_type not in VisualRefinementActionType:
                continue
            ok = self._apply_one(patched, action)
            if ok:
                applied.append(action.model_copy(update={"applied": True}))
        if applied:
            warnings = list(patched.warnings)
            warnings.append(f"vq7_refinement:applied={len(applied)}")
            for item in applied:
                warnings.append(f"vq7_action:{item.action_type.value}")
            patched = patched.model_copy(update={"warnings": warnings})
        return patched, applied

    def refine_page(
        self,
        scene: RenderScene,
        plan: LayoutPlan,
        *,
        image_path: str | Path | None = None,
        max_rounds: int = DEFAULT_REFINEMENT_ROUNDS,
        max_actions: int = MAX_ACTIONS_PER_PAGE,
    ) -> VisualRefinementLoopResult:
        """Evaluate → propose → apply → re-evaluate, capped rounds."""
        rounds_cap = max(0, min(int(max_rounds), MAX_REFINEMENT_ROUNDS))
        actions_cap = max(0, min(int(max_actions), MAX_ACTIONS_PER_PAGE))
        current = scene.model_copy(deep=True)
        before = self._critic.evaluate_plan(plan, image_path=image_path)
        if rounds_cap == 0 or actions_cap == 0:
            return VisualRefinementLoopResult(
                scene=current,
                before_report=before,
                after_report=before,
                stopped_reason="disabled",
            )

        rounds: list[VisualRefinementRound] = []
        total_applied = 0
        after = before
        proposal: VisualRefinementProposal | None = None
        stopped = "completed"

        for index in range(rounds_cap):
            proposal = self.propose(after, current, max_actions=actions_cap)
            if not proposal.actions:
                stopped = "no_allowlisted_actions"
                rounds.append(
                    VisualRefinementRound(
                        round_index=index,
                        before_score=after.total_score,
                        after_score=after.total_score,
                        proposed=[],
                        applied=[],
                        stopped_reason=stopped,
                    )
                )
                break

            current, applied = self.apply(current, proposal.actions)
            total_applied += len(applied)
            re_eval = self._critic.evaluate_plan(plan, image_path=image_path)
            # Score uses plan geometry; stamp note that scene was patched.
            if applied:
                re_eval = re_eval.model_copy(
                    update={
                        "notes": [
                            *list(re_eval.notes),
                            f"vq7:scene_patched actions={len(applied)} round={index}",
                        ]
                    }
                )
            rounds.append(
                VisualRefinementRound(
                    round_index=index,
                    before_score=after.total_score,
                    after_score=re_eval.total_score,
                    proposed=list(proposal.actions),
                    applied=applied,
                    stopped_reason=None if applied else "apply_noop",
                )
            )
            after = re_eval
            if not applied:
                stopped = "apply_noop"
                break
            # Stop early when score already healthy.
            if after.total_score is not None and after.total_score >= 0.72:
                stopped = "score_threshold"
                break
        else:
            stopped = "max_rounds"

        return VisualRefinementLoopResult(
            scene=current,
            before_report=before,
            after_report=after,
            proposal=proposal,
            rounds=rounds,
            applied_count=total_applied,
            stopped_reason=stopped,
        )

    def refine_deck(
        self,
        *,
        scenes: list[RenderScene],
        plans: list[LayoutPlan],
        image_paths: dict[str, str | Path] | None = None,
        max_rounds: int = DEFAULT_REFINEMENT_ROUNDS,
        max_actions_per_page: int = MAX_ACTIONS_PER_PAGE,
        max_actions_deck: int = MAX_ACTIONS_PER_DECK,
        presentation_id: UUID | None = None,
    ) -> VisualRefinementDeckResult:
        """Run bounded refinement across pages with a deck-wide action budget."""
        by_plan = {str(p.id): p for p in plans}
        by_slide = {str(p.slide_id): p for p in plans}
        images = image_paths or {}
        page_results: list[VisualRefinementLoopResult] = []
        budget = max(0, min(int(max_actions_deck), MAX_ACTIONS_PER_DECK))
        total_applied = 0
        touched = 0
        notes: list[str] = []

        for scene in scenes:
            if budget <= 0:
                notes.append("deck_action_budget_exhausted")
                break
            plan = by_plan.get(str(scene.layout_plan_id)) or by_slide.get(str(scene.slide_id))
            if plan is None:
                notes.append(f"skip_scene_no_plan:{scene.id}")
                continue
            image = images.get(str(plan.id)) or images.get(str(scene.slide_id))
            page_cap = min(max_actions_per_page, budget)
            result = self.refine_page(
                scene,
                plan,
                image_path=image,
                max_rounds=max_rounds,
                max_actions=page_cap,
            )
            page_results.append(result)
            total_applied += result.applied_count
            budget -= result.applied_count
            if result.applied_count:
                touched += 1

        return VisualRefinementDeckResult(
            page_results=page_results,
            total_applied=total_applied,
            pages_touched=touched,
            presentation_id=presentation_id,
            notes=notes,
        )

    def _resolve_target(
        self,
        scene: RenderScene,
        action_type: VisualRefinementActionType,
    ) -> str | None:
        if action_type == VisualRefinementActionType.BOOST_TITLE_SCALE:
            node = next(
                (
                    n
                    for n in scene.nodes
                    if isinstance(n, TextNode) and n.semantic_role in _TITLE_ROLES
                ),
                None,
            )
            return node.id if node else None
        if action_type == VisualRefinementActionType.ENLARGE_HERO:
            node = next(
                (
                    n
                    for n in scene.nodes
                    if isinstance(n, ImageNode)
                    and (
                        n.semantic_role in _HERO_ROLES
                        or "hero" in n.semantic_role
                        or n.id == "hero"
                    )
                ),
                None,
            )
            if node is None:
                node = next((n for n in scene.nodes if isinstance(n, ImageNode)), None)
            return node.id if node else None
        if action_type in {
            VisualRefinementActionType.SOFTEN_SECONDARY_TEXT,
            VisualRefinementActionType.TRIM_BODY_BOX,
        }:
            node = next(
                (
                    n
                    for n in scene.nodes
                    if isinstance(n, TextNode) and n.semantic_role in _BODY_ROLES
                ),
                None,
            )
            return node.id if node else None
        if action_type == VisualRefinementActionType.FIX_TEXT_CONTRAST:
            return None
        return None

    def _apply_one(self, scene: RenderScene, action: VisualRefinementAction) -> bool:
        kind = action.action_type
        if kind == VisualRefinementActionType.BOOST_TITLE_SCALE:
            return self._boost_title(scene, action)
        if kind == VisualRefinementActionType.ENLARGE_HERO:
            return self._enlarge_hero(scene, action)
        if kind == VisualRefinementActionType.SOFTEN_SECONDARY_TEXT:
            return self._soften_secondary_text(scene, action)
        if kind == VisualRefinementActionType.TRIM_BODY_BOX:
            return self._trim_body_box(scene, action)
        if kind == VisualRefinementActionType.QUIET_MOTIF:
            return self._quiet_motif(scene, action)
        if kind == VisualRefinementActionType.SOFTEN_ACCENT_SHAPES:
            return self._soften_accent_shapes(scene, action)
        if kind == VisualRefinementActionType.FIX_TEXT_CONTRAST:
            return self._fix_text_contrast(scene)
        return False

    def _boost_title(self, scene: RenderScene, action: VisualRefinementAction) -> bool:
        node = self._text_node(scene, action.target_node_id, _TITLE_ROLES)
        if node is None:
            return False
        scale = 1.0 + min(0.25, max(0.05, action.magnitude))
        new_size = min(84.0, round(float(node.font_size) * scale, 1))
        updated = node.model_copy(
            update={"font_size": new_size, "font_weight": max(node.font_weight, 700)}
        )
        if node.runs:
            runs = [
                TextRun(
                    text=run.text,
                    font_family=run.font_family,
                    font_family_cjk=run.font_family_cjk,
                    font_family_latin=run.font_family_latin,
                    font_size=(
                        min(96.0, round(float(run.font_size) * scale, 1))
                        if run.font_size is not None
                        else new_size
                    ),
                    font_weight=max(run.font_weight or 400, 700),
                    font_style=run.font_style,
                    color=run.color,
                    color_token=run.color_token,
                )
                for run in node.runs
            ]
            set_text_node_runs(updated, runs)
        self._replace_node(scene, updated)
        return True

    def _enlarge_hero(self, scene: RenderScene, action: VisualRefinementAction) -> bool:
        node = None
        if action.target_node_id:
            candidate = scene.node_by_id(action.target_node_id)
            if isinstance(candidate, ImageNode):
                node = candidate
        if node is None:
            return False
        grow = min(0.2, max(0.05, action.magnitude))
        new_w = min(scene.page_width * 0.92, node.width * (1.0 + grow))
        new_h = min(scene.page_height * 0.82, node.height * (1.0 + grow))
        # Keep top-left anchored; clamp inside page.
        new_x = max(0.15, min(node.x, scene.page_width - new_w - 0.15))
        new_y = max(0.15, min(node.y, scene.page_height - new_h - 0.15))
        updated = node.model_copy(
            update={"width": round(new_w, 3), "height": round(new_h, 3), "x": new_x, "y": new_y}
        )
        self._replace_node(scene, updated)
        return True

    def _soften_secondary_text(
        self, scene: RenderScene, action: VisualRefinementAction
    ) -> bool:
        node = self._text_node(scene, action.target_node_id, _BODY_ROLES)
        if node is None:
            return False
        # Keep opacity high enough that ink stays readable on the page board.
        opacity = max(0.72, float(node.opacity) * (1.0 - min(0.2, action.magnitude)))
        size = max(11.0, round(float(node.font_size) * (1.0 - min(0.12, action.magnitude * 0.5)), 1))
        updated = node.model_copy(update={"opacity": round(opacity, 3), "font_size": size})
        self._replace_node(scene, updated)
        # Re-assert contrast after any fade.
        self._fix_text_contrast(scene)
        return True

    def _fix_text_contrast(self, scene: RenderScene) -> bool:
        from archium.application.visual.text_contrast_guard import (
            apply_text_background_contrast_to_scene,
            scene_text_contrast_failures,
        )

        before = len(scene_text_contrast_failures(scene))
        patched = apply_text_background_contrast_to_scene(scene)
        object.__setattr__(scene, "nodes", list(patched.nodes))
        object.__setattr__(scene, "warnings", list(patched.warnings))
        after = len(scene_text_contrast_failures(scene))
        return before > after or "text_contrast:enforced" in scene.warnings

    def _trim_body_box(self, scene: RenderScene, action: VisualRefinementAction) -> bool:
        node = self._text_node(scene, action.target_node_id, _BODY_ROLES)
        if node is None:
            return False
        shrink = min(0.2, max(0.05, action.magnitude))
        new_h = max(0.4, node.height * (1.0 - shrink))
        updated = node.model_copy(update={"height": round(new_h, 3)})
        self._replace_node(scene, updated)
        return True

    def _quiet_motif(self, scene: RenderScene, action: VisualRefinementAction) -> bool:
        scale = max(0.25, 1.0 - min(0.55, action.magnitude + 0.25))
        changed = False
        nodes: list[object] = []
        for node in scene.nodes:
            node_id = str(getattr(node, "id", ""))
            if not node_id.startswith("vl_motif_"):
                nodes.append(node)
                continue
            # Drop connector / index noise first; keep at most a quiet rule.
            if any(token in node_id for token in ("connector", "index_", "path_poly", "contour")):
                changed = True
                continue
            opacity = round(float(getattr(node, "opacity", 1.0)) * scale, 3)
            nodes.append(node.model_copy(update={"opacity": opacity}))
            changed = True
        if changed:
            object.__setattr__(scene, "nodes", nodes)
        return changed

    def _soften_accent_shapes(
        self, scene: RenderScene, action: VisualRefinementAction
    ) -> bool:
        scale = max(0.3, 1.0 - min(0.5, action.magnitude + 0.15))
        changed = False
        nodes: list[object] = []
        for node in scene.nodes:
            if isinstance(node, ShapeNode) and (
                str(getattr(node, "id", "")).startswith("vl_")
                or "accent" in str(getattr(node, "semantic_role", ""))
                or "motif" in str(getattr(node, "semantic_role", ""))
            ):
                opacity = round(float(node.opacity) * scale, 3)
                nodes.append(node.model_copy(update={"opacity": opacity}))
                changed = True
            else:
                nodes.append(node)
        if changed:
            object.__setattr__(scene, "nodes", nodes)
        return changed

    @staticmethod
    def _text_node(
        scene: RenderScene,
        node_id: str | None,
        roles: frozenset[str],
    ) -> TextNode | None:
        if node_id:
            candidate = scene.node_by_id(node_id)
            if isinstance(candidate, TextNode):
                return candidate
        return next(
            (n for n in scene.nodes if isinstance(n, TextNode) and n.semantic_role in roles),
            None,
        )

    @staticmethod
    def _replace_node(scene: RenderScene, updated: object) -> None:
        node_id = getattr(updated, "id", None)
        nodes = list(scene.nodes)
        for index, node in enumerate(nodes):
            if getattr(node, "id", None) == node_id:
                nodes[index] = updated  # type: ignore[assignment]
                break
        object.__setattr__(scene, "nodes", nodes)


def _default_magnitude(action_type: VisualRefinementActionType) -> float:
    return {
        VisualRefinementActionType.BOOST_TITLE_SCALE: 0.15,
        VisualRefinementActionType.ENLARGE_HERO: 0.12,
        VisualRefinementActionType.SOFTEN_SECONDARY_TEXT: 0.2,
        VisualRefinementActionType.TRIM_BODY_BOX: 0.12,
        VisualRefinementActionType.QUIET_MOTIF: 0.3,
        VisualRefinementActionType.SOFTEN_ACCENT_SHAPES: 0.25,
        VisualRefinementActionType.FIX_TEXT_CONTRAST: 0.0,
    }.get(action_type, 0.12)


__all__ = ["CriticRefinementService"]

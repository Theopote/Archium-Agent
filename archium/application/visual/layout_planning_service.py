"""Layout planning — rule + optional LLM decision, deterministic geometry."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.asset_reference import (
    build_asset_reference_context,
    content_refs_from_plan,
)
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.config.settings import Settings, get_settings
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import LayoutFamily, LayoutValidationStatus, VisualContentType
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.validation import LayoutValidationReport
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)
from archium.infrastructure.layout.generators.base import (
    LayoutGeneratorContext,
    content_from_slide,
)
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.layout.layout_solver import LayoutSolver
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.visual_schemas import LayoutDecisionDraft
from archium.logging import get_logger
from archium.prompts.layout_plan import (
    LAYOUT_PLAN_SYSTEM_PROMPT,
    build_layout_plan_user_prompt,
)

logger = get_logger(__name__, operation="layout_planning")

LAYOUT_DECISION_LLM_FALLBACK = "VISUAL.LAYOUT_DECISION_LLM_FALLBACK"


class LayoutPlanningService:
    """Plan LayoutPlan candidates and select the best scored valid plan."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
        validator: LayoutValidationService | None = None,
        solver: LayoutSolver | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._validator = validator or LayoutValidationService()
        self._solver = solver or LayoutSolver()
        self._registry = get_layout_family_registry()
        self._plans = LayoutPlanRepository(session)
        self._intents = VisualIntentRepository(session)
        self._art = ArtDirectionRepository(session)
        self._design = DesignSystemRepository(session)
        self._settings = settings or get_settings()
        self._warnings: list[dict[str, Any]] = []

    def drain_warnings(self) -> list[dict[str, Any]]:
        """Return and clear structured warnings collected during the last plan call."""
        warnings = list(self._warnings)
        self._warnings.clear()
        return warnings

    def plan_slide(
        self,
        *,
        slide: SlideSpec,
        visual_intent_id: UUID,
        art_direction_id: UUID | None,
        design_system_id: UUID,
        candidate_count: int = 3,
    ) -> LayoutPlan:
        candidates = self.generate_candidates(
            slide=slide,
            visual_intent_id=visual_intent_id,
            art_direction_id=art_direction_id,
            design_system_id=design_system_id,
            candidate_count=candidate_count,
        )
        best = self.select_best(candidates)
        saved = self._plans.save(best)
        return saved

    def generate_candidates(
        self,
        *,
        slide: SlideSpec,
        visual_intent_id: UUID,
        art_direction_id: UUID | None,
        design_system_id: UUID,
        candidate_count: int = 3,
        project_id: UUID | None = None,
    ) -> list[tuple[LayoutPlan, LayoutValidationReport]]:
        self._warnings.clear()
        intent = self._intents.get(visual_intent_id)
        if intent is None:
            raise ValueError(f"VisualIntent {visual_intent_id} not found")
        design = self._design.get(design_system_id)
        if design is None:
            raise ValueError(f"DesignSystem {design_system_id} not found")
        art = self._art.get(art_direction_id) if art_direction_id else None

        decisions = self._decide_candidates(slide, intent, art, design, candidate_count)
        content = content_from_slide(slide, intent)
        drawing = intent.dominant_content_type in {
            VisualContentType.SITE_PLAN,
            VisualContentType.FLOOR_PLAN,
            VisualContentType.SECTION,
            VisualContentType.ELEVATION,
        }

        results: list[tuple[LayoutPlan, LayoutValidationReport]] = []
        for decision in decisions:
            family = LayoutFamily(decision.layout_family)
            variant = self._registry.resolve_variant(family, decision.layout_variant)
            context = LayoutGeneratorContext(
                slide=slide,
                visual_intent=intent,
                art_direction=art,
                design_system=design,
                content=content,
                variant=variant,
            )
            plan = self._solver.generate(family, context)
            asset_context = None
            if project_id is not None:
                asset_context = build_asset_reference_context(
                    self._session,
                    project_id=project_id,
                    content_refs=content_refs_from_plan(plan),
                    settings=self._settings,
                )
            report = self._validator.validate(
                plan,
                design,
                require_source=bool(content.source_text)
                or family == LayoutFamily.DRAWING_FOCUS,
                drawing_hero=drawing,
                asset_context=asset_context,
            )
            plan.validation_status = (
                LayoutValidationStatus.VALID
                if report.valid
                else LayoutValidationStatus.INVALID
            )
            results.append((plan, report))
        return results

    def select_best(
        self, candidates: list[tuple[LayoutPlan, LayoutValidationReport]]
    ) -> LayoutPlan:
        if not candidates:
            raise ValueError("no layout candidates to select")
        non_critical = [
            (plan, report)
            for plan, report in candidates
            if not report.has_critical()
        ]
        pool = non_critical or candidates
        pool_sorted = sorted(
            pool,
            key=lambda item: (
                0 if item[1].valid else 1,
                -(item[1].score),
            ),
        )
        return pool_sorted[0][0]

    def _decide_candidates(
        self,
        slide: SlideSpec,
        intent: VisualIntent,
        art: ArtDirection | None,
        design: DesignSystem,
        candidate_count: int,
    ) -> list[LayoutDecisionDraft]:
        asset_count = (
            (1 if intent.hero_asset_id else 0) + len(intent.supporting_asset_ids)
        ) or len(slide.visual_requirements)

        if self._llm is not None:
            allowed = [
                item.family.value
                for item in self._registry.candidates_for(
                    intent.dominant_content_type,
                    asset_count=max(asset_count, 0),
                    preferred=list(intent.preferred_layout_families),
                )
            ]
            try:
                draft = self._llm.generate_structured(
                    LLMRequest(
                        system_prompt=LAYOUT_PLAN_SYSTEM_PROMPT,
                        user_prompt=build_layout_plan_user_prompt(
                            slide=slide,
                            intent=intent,
                            art_direction=art,
                            allowed_families=allowed,
                        ),
                        temperature=0.2,
                    ),
                    LayoutDecisionDraft,
                )
                if draft.layout_family in allowed:
                    primary = draft
                    extras = self._rule_decisions(intent, asset_count, candidate_count)
                    merged = [primary]
                    for extra in extras:
                        if extra.layout_family == primary.layout_family and (
                            extra.layout_variant == primary.layout_variant
                        ):
                            continue
                        merged.append(extra)
                        if len(merged) >= candidate_count:
                            break
                    return merged[:candidate_count]
                fallback = self._rule_decisions(intent, asset_count, candidate_count)
                self._record_llm_fallback(
                    error_type="DisallowedLayoutFamily",
                    fallback_family=fallback[0].layout_family,
                    detail=f"llm_family={draft.layout_family}",
                )
                return fallback
            except Exception as exc:
                fallback = self._rule_decisions(intent, asset_count, candidate_count)
                self._record_llm_fallback(
                    error_type=type(exc).__name__,
                    fallback_family=fallback[0].layout_family,
                )
                return fallback

        return self._rule_decisions(intent, asset_count, candidate_count)

    def _record_llm_fallback(
        self,
        *,
        error_type: str,
        fallback_family: str,
        detail: str | None = None,
    ) -> None:
        provider, model = self._llm_identity()
        payload: dict[str, Any] = {
            "code": LAYOUT_DECISION_LLM_FALLBACK,
            "provider": provider,
            "model": model,
            "error_type": error_type,
            "fallback_family": fallback_family,
        }
        if detail:
            payload["detail"] = detail
        self._warnings.append(payload)
        # Structured log — never include prompts or secrets.
        logger.warning(
            "%s provider=%s model=%s error_type=%s fallback_family=%s%s",
            LAYOUT_DECISION_LLM_FALLBACK,
            provider,
            model,
            error_type,
            fallback_family,
            f" detail={detail}" if detail else "",
            extra={
                "rule_code": LAYOUT_DECISION_LLM_FALLBACK,
                "llm_provider": provider,
                "llm_model": model,
                "error_type": error_type,
                "fallback_family": fallback_family,
            },
        )

    def _llm_identity(self) -> tuple[str, str]:
        llm = self._llm
        if llm is None:
            return "none", "none"
        provider = getattr(llm, "provider_name", None) or type(llm).__name__
        model = getattr(llm, "model", None)
        settings = getattr(llm, "_settings", None)
        if settings is not None:
            provider = getattr(settings, "llm_provider", None) or provider
            model = model or getattr(settings, "llm_model", None)
        return str(provider), str(model or "unknown")

    def _rule_decisions(
        self,
        intent: VisualIntent,
        asset_count: int,
        candidate_count: int,
    ) -> list[LayoutDecisionDraft]:
        definitions = self._registry.candidates_for(
            intent.dominant_content_type,
            asset_count=max(asset_count, 0),
            preferred=list(intent.preferred_layout_families),
        )
        decisions: list[LayoutDecisionDraft] = []
        for definition in definitions:
            for variant in definition.supported_variants:
                decisions.append(
                    LayoutDecisionDraft(
                        layout_family=definition.family.value,
                        layout_variant=variant,
                        hero_content_ref=(
                            str(intent.hero_asset_id) if intent.hero_asset_id else None
                        ),
                        supporting_content_refs=[
                            str(asset_id) for asset_id in intent.supporting_asset_ids
                        ],
                        reading_order=list(intent.reading_order),
                        density_adjustment=intent.density_level.value,
                        split_recommended=False,
                        split_reason=None,
                    )
                )
                if len(decisions) >= candidate_count:
                    return decisions
        if not decisions:
            decisions.append(
                LayoutDecisionDraft(
                    layout_family=LayoutFamily.TEXTUAL_ARGUMENT.value,
                    layout_variant="lead_and_points",
                    reading_order=list(intent.reading_order),
                    density_adjustment=intent.density_level.value,
                )
            )
        return decisions


def format_layout_decision_warnings(warnings: list[dict[str, Any]]) -> list[str]:
    """Human-readable lines for workflow / UI warning lists."""
    lines: list[str] = []
    for item in warnings:
        if item.get("code") != LAYOUT_DECISION_LLM_FALLBACK:
            continue
        lines.append(
            f"{LAYOUT_DECISION_LLM_FALLBACK} "
            f"provider={item.get('provider', '?')} "
            f"model={item.get('model', '?')} "
            f"error_type={item.get('error_type', '?')} "
            f"fallback_family={item.get('fallback_family', '?')}"
            + (f" detail={item['detail']}" if item.get("detail") else "")
        )
    return lines

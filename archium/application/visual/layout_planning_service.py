"""Layout planning — rule + optional LLM decision, deterministic geometry."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.layout_validation_service import LayoutValidationService
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
from archium.prompts.layout_plan import (
    LAYOUT_PLAN_SYSTEM_PROMPT,
    build_layout_plan_user_prompt,
)


class LayoutPlanningService:
    """Plan LayoutPlan candidates and select the best scored valid plan."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
        validator: LayoutValidationService | None = None,
        solver: LayoutSolver | None = None,
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
    ) -> list[tuple[LayoutPlan, LayoutValidationReport]]:
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
            report = self._validator.validate(
                plan,
                design,
                require_source=bool(content.source_text)
                or family == LayoutFamily.DRAWING_FOCUS,
                drawing_hero=drawing,
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
                    # Build variants around the LLM primary choice.
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
            except Exception:
                pass

        return self._rule_decisions(intent, asset_count, candidate_count)

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

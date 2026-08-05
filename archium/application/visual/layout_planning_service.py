"""Layout planning — rule + optional LLM decision, deterministic geometry."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from archium.application.agent_skills import apply_skills_to_request
from archium.application.unit_of_work import SessionLike, session_of
from archium.application.visual.asset_reference import (
    build_asset_reference_context,
    content_refs_from_plan,
)
from archium.application.visual.layout_locked import preserve_locked_elements
from archium.application.visual.layout_style_preference import (
    LayoutStylePreference,
    derive_layout_style_preference,
    merge_preferred_families,
)
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.slide_capacity_service import SlideCapacityService
from archium.application.visual.visual_grammar_intent import (
    derive_grammar_layout_preference,
    forbidden_families_for_intent,
    merge_layout_style_preferences,
    order_variants_for_intent,
)
from archium.config.settings import Settings, get_settings
from archium.domain.enums import SlideType
from archium.domain.reference_style import ReferenceStyleProfile
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.deck_composition import PacingRole, SlideCompositionDirective
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import (
    ContinuityRole,
    DensityLevel,
    LayoutElementRole,
    LayoutFamily,
    LayoutValidationStatus,
    OverflowPolicy,
    VisualContentType,
)
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.slide_capacity_budget import (
    CAPACITY_IMPOSSIBLE_RULE,
    CAPACITY_OVERLOAD_RULE,
    CAPACITY_TIGHT_RULE,
    CapacityStatus,
    SlideCapacityBudget,
)
from archium.domain.visual.validation import LayoutValidationReport
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.database.repositories import ProjectRepository
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
_SEMANTIC_SPECIALIST_FAMILIES = frozenset(
    {
        LayoutFamily.PROCESS_NARRATIVE,
        LayoutFamily.METRIC_DASHBOARD,
        LayoutFamily.COMPARATIVE_MATRIX,
        LayoutFamily.ANALYTICAL_DIAGRAM,
    }
)


class LayoutPlanningService:
    """Plan LayoutPlan candidates and select the best scored valid plan."""

    def __init__(
        self,
        session: SessionLike,
        *,
        llm: LLMProvider | None = None,
        validator: LayoutValidationService | None = None,
        solver: LayoutSolver | None = None,
        settings: Settings | None = None,
    ) -> None:
        session = session_of(session)
        self._session = session
        self._llm = llm
        self._validator = validator or LayoutValidationService()
        self._solver = solver or LayoutSolver()
        self._registry = get_layout_family_registry()
        self._plans = LayoutPlanRepository(session)
        self._intents = VisualIntentRepository(session)
        self._art = ArtDirectionRepository(session)
        self._design = DesignSystemRepository(session)
        self._projects = ProjectRepository(session)
        self._settings = settings or get_settings()
        self._warnings: list[dict[str, Any]] = []
        self._capacity = SlideCapacityService()
        self._last_capacity_budget: SlideCapacityBudget | None = None
        self._last_style_preference: LayoutStylePreference = LayoutStylePreference()

    def drain_warnings(self) -> list[dict[str, Any]]:
        """Return and clear structured warnings collected during the last plan call."""
        warnings = list(self._warnings)
        self._warnings.clear()
        return warnings

    @property
    def last_style_preference(self) -> LayoutStylePreference:
        """Style-driven layout preference from the most recent generate_candidates call."""
        return self._last_style_preference

    def plan_slide(
        self,
        *,
        slide: SlideSpec,
        visual_intent_id: UUID,
        art_direction_id: UUID | None,
        design_system_id: UUID,
        candidate_count: int = 3,
        project_id: UUID | None = None,
        reference_style: ReferenceStyleProfile | None = None,
    ) -> LayoutPlan:
        candidates = self.generate_candidates(
            slide=slide,
            visual_intent_id=visual_intent_id,
            art_direction_id=art_direction_id,
            design_system_id=design_system_id,
            candidate_count=candidate_count,
            project_id=project_id,
            reference_style=reference_style,
        )
        best = self.select_best(
            candidates,
            style_preference=self._last_style_preference,
        )
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
        deck_directive: SlideCompositionDirective | None = None,
        previous_layout_plan: LayoutPlan | None = None,
        reference_style: ReferenceStyleProfile | None = None,
        style_preference: LayoutStylePreference | None = None,
    ) -> list[tuple[LayoutPlan, LayoutValidationReport]]:
        self._warnings.clear()
        intent = self._intents.get(visual_intent_id)
        if intent is None:
            raise ValueError(f"VisualIntent {visual_intent_id} not found")
        design = self._design.get(design_system_id)
        if design is None:
            raise ValueError(f"DesignSystem {design_system_id} not found")
        art = self._art.get(art_direction_id) if art_direction_id else None
        if art is not None and art.style_preset_id:
            from archium.application.visual.style_overlay import apply_style_overlays

            design = apply_style_overlays(
                design,
                art_direction=art,
            ).design_system

        from archium.application.visual.template_usage_brief_context import (
            constraints_from_brief,
            load_brief_for_art_direction,
        )

        usage_brief = load_brief_for_art_direction(self._session, art)
        usage_constraints = constraints_from_brief(usage_brief) if usage_brief is not None else None
        if usage_constraints is not None:
            self._warnings.append(
                {
                    "code": "TEMPLATE_USAGE_BRIEF.BOUND",
                    "detail": (
                        f"consuming TemplateUsageBrief "
                        f"{usage_constraints.brief_id} v{usage_constraints.brief_version}"
                    ),
                    "template_usage_brief_id": str(usage_constraints.brief_id),
                    "template_usage_brief_version": usage_constraints.brief_version,
                }
            )

        capacity = self._capacity.estimate(
            slide,
            design,
            visual_intent=intent,
        )
        self._last_capacity_budget = capacity
        if capacity.status == CapacityStatus.IMPOSSIBLE:
            self._warnings.append(
                {
                    "code": CAPACITY_IMPOSSIBLE_RULE,
                    "severity": "blocker",
                    "detail": (
                        f"capacity_ratio={capacity.capacity_ratio:.2f}; "
                        f"status={capacity.status.value}; "
                        "drawing/min-readable exceeds fixed canvas — BLOCKED"
                    ),
                    "capacity_ratio": capacity.capacity_ratio,
                    "capacity_status": capacity.status.value,
                    "recommended_action": capacity.recommended_action,
                    "overflow_risk": capacity.overflow_risk,
                }
            )
        elif capacity.status == CapacityStatus.OVERLOADED:
            overload_severity = (
                "blocker" if self._settings.visual_capacity_block_overloaded else "major"
            )
            self._warnings.append(
                {
                    "code": CAPACITY_OVERLOAD_RULE,
                    "severity": overload_severity,
                    "detail": (
                        f"capacity_ratio={capacity.capacity_ratio:.2f}; "
                        f"status={capacity.status.value}; "
                        f"action={capacity.recommended_action}; "
                        + (
                            "blocked — adapt content or split before layout"
                            if overload_severity == "blocker"
                            else "forbid further font shrink — adapt or split"
                        )
                    ),
                    "capacity_ratio": capacity.capacity_ratio,
                    "capacity_status": capacity.status.value,
                    "recommended_action": capacity.recommended_action,
                    "overflow_risk": capacity.overflow_risk,
                }
            )
        elif capacity.status == CapacityStatus.TIGHT:
            self._warnings.append(
                {
                    "code": CAPACITY_TIGHT_RULE,
                    "severity": "minor",
                    "detail": (
                        f"capacity_ratio={capacity.capacity_ratio:.2f}; "
                        "candidates allowed but QA is mandatory"
                    ),
                    "capacity_ratio": capacity.capacity_ratio,
                    "capacity_status": capacity.status.value,
                    "recommended_action": capacity.recommended_action,
                    "overflow_risk": capacity.overflow_risk,
                }
            )

        if capacity.blocks_layout_candidates(
            block_overloaded=self._settings.visual_capacity_block_overloaded,
        ):
            return []

        resolved_style = reference_style
        if resolved_style is None and project_id is not None:
            resolved_style = self.resolve_reference_style(project_id)
        intent_pref = LayoutStylePreference(
            preferred_families=tuple(intent.preferred_layout_families),
            notes=(
                ("visual_intent:preferred_layout_families",)
                if intent.preferred_layout_families
                else ()
            ),
        )
        grammar_pref = derive_grammar_layout_preference(intent)
        # Explicit intent preferences (Studio presets / user edits) outrank grammar defaults.
        style_pref = style_preference or merge_layout_style_preferences(
            intent_pref,
            grammar_pref,
            derive_layout_style_preference(
                reference_style=resolved_style,
                art_direction=art,
            ),
        )
        self._last_style_preference = style_pref
        for note in style_pref.notes:
            self._warnings.append({"code": "LAYOUT.STYLE_PREFERENCE", "detail": note})

        decisions = self._decide_candidates(
            slide,
            intent,
            art,
            design,
            candidate_count,
            deck_directive=deck_directive,
            style_preference=style_pref,
        )
        content = content_from_slide(slide, intent)
        drawing = intent.dominant_content_type in {
            VisualContentType.SITE_PLAN,
            VisualContentType.FLOOR_PLAN,
            VisualContentType.SECTION,
            VisualContentType.ELEVATION,
        }
        if (
            usage_constraints is not None
            and usage_constraints.forbid_drawing_cover_crop
            and drawing
        ):
            self._warnings.append(
                {
                    "code": "TEMPLATE_USAGE_BRIEF.DRAWING_CONTAIN",
                    "detail": "brief forbids drawing cover/crop — contain required",
                    "template_usage_brief_id": str(usage_constraints.brief_id),
                    "template_usage_brief_version": usage_constraints.brief_version,
                }
            )

        results: list[tuple[LayoutPlan, LayoutValidationReport]] = []
        for decision in decisions:
            family = LayoutFamily(decision.layout_family)
            # Re-estimate with chosen family for tighter image budget metadata.
            family_budget = self._capacity.estimate(
                slide,
                design,
                visual_intent=intent,
                layout_family=family,
            )
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
            plan = preserve_locked_elements(plan, previous_layout_plan)
            if family_budget.is_overloaded or family_budget.status == CapacityStatus.TIGHT:
                # OVERLOADED forces split; TIGHT keeps current policy but QA is required.
                if family_budget.is_overloaded:
                    plan = plan.model_copy(update={"overflow_policy": OverflowPolicy.SPLIT})
                elif plan.overflow_policy == OverflowPolicy.CLIP:
                    plan = plan.model_copy(update={"overflow_policy": OverflowPolicy.WARN})
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
                require_source=bool(content.source_text) or family == LayoutFamily.DRAWING_FOCUS,
                drawing_hero=drawing,
                asset_context=asset_context,
            )
            plan.validation_status = (
                LayoutValidationStatus.VALID if report.valid else LayoutValidationStatus.INVALID
            )
            results.append((plan, report))
        return results

    @property
    def last_capacity_budget(self) -> SlideCapacityBudget | None:
        return self._last_capacity_budget

    def select_best(
        self,
        candidates: list[tuple[LayoutPlan, LayoutValidationReport]],
        *,
        deck_directive: SlideCompositionDirective | None = None,
        previous_layout_plan: LayoutPlan | None = None,
        style_preference: LayoutStylePreference | None = None,
    ) -> LayoutPlan:
        return self.select_best_for_deck(
            candidates,
            deck_directive=deck_directive,
            previous_layout_plan=previous_layout_plan,
            style_preference=style_preference,
        )

    def select_best_for_deck(
        self,
        candidates: list[tuple[LayoutPlan, LayoutValidationReport]],
        *,
        deck_directive: SlideCompositionDirective | None = None,
        previous_layout_plan: LayoutPlan | None = None,
        recent_layout_plans: Sequence[LayoutPlan] | None = None,
        style_preference: LayoutStylePreference | None = None,
    ) -> LayoutPlan:
        if not candidates:
            raise ValueError("no layout candidates to select")
        non_critical = [(plan, report) for plan, report in candidates if not report.has_critical()]
        pool = non_critical or candidates
        if style_preference is not None:
            resolved_style = style_preference
        else:
            resolved_style = (
                getattr(self, "_last_style_preference", None) or LayoutStylePreference()
            )
        pool_sorted = sorted(
            pool,
            key=lambda item: self._selection_sort_key(
                item,
                deck_directive=deck_directive,
                previous_layout_plan=previous_layout_plan,
                recent_layout_plans=recent_layout_plans,
                style_preference=resolved_style,
            ),
        )
        return pool_sorted[0][0]

    def resolve_reference_style(self, project_id: UUID) -> ReferenceStyleProfile | None:
        profiles = self._projects.list_reference_style_profiles(project_id)
        if not profiles:
            return None
        approved = [profile for profile in profiles if profile.is_approved]
        return (approved or profiles)[0]

    def resolve_style_preference(
        self,
        *,
        project_id: UUID | None = None,
        art_direction: ArtDirection | None = None,
        reference_style: ReferenceStyleProfile | None = None,
    ) -> LayoutStylePreference:
        resolved = reference_style
        if resolved is None and project_id is not None:
            resolved = self.resolve_reference_style(project_id)
        return derive_layout_style_preference(
            reference_style=resolved,
            art_direction=art_direction,
        )

    @staticmethod
    def _selection_sort_key(
        item: tuple[LayoutPlan, LayoutValidationReport],
        *,
        deck_directive: SlideCompositionDirective | None,
        previous_layout_plan: LayoutPlan | None,
        recent_layout_plans: Sequence[LayoutPlan] | None = None,
        style_preference: LayoutStylePreference | None = None,
    ) -> tuple[float, float, float, str]:
        plan, report = item
        validity_rank = 0.0 if report.valid else 1.0
        score_rank = -report.score
        composition_penalty = 0.0
        composition_bonus = 0.0

        if deck_directive is not None:
            monument_hero_fallback = (
                plan.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                and plan.layout_variant == "monument"
                and LayoutFamily.HERO in (deck_directive.preferred_layout_families or [])
            )
            if plan.layout_family in deck_directive.forbidden_layout_families:
                # Hero opening without assets must keep the text monument cover;
                # page_direction often forbids textual_argument for image-led openings.
                if not monument_hero_fallback:
                    composition_penalty += 1.0
                else:
                    composition_bonus += 0.5
            preferred = deck_directive.preferred_layout_families
            if preferred and plan.layout_family == preferred[0]:
                composition_bonus += (
                    0.28 if plan.layout_family in _SEMANTIC_SPECIALIST_FAMILIES else 0.08
                )
            elif preferred and plan.layout_family in preferred[1:]:
                composition_bonus += 0.03
            elif monument_hero_fallback:
                # Treat monument as the realized preferred opener when HERO is unavailable.
                composition_bonus += 0.3
            if (
                deck_directive.pacing_role == PacingRole.CLOSING
                and plan.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                and plan.layout_variant == "quote_argument"
            ):
                composition_bonus += 0.48
            if (
                deck_directive.pacing_role == PacingRole.CLOSING
                and plan.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                and plan.layout_variant == "lead_and_points"
            ):
                composition_penalty += 0.28
            if (
                deck_directive.pacing_role == PacingRole.TRANSITION
                and plan.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                and plan.layout_variant == "section_opener"
            ):
                composition_bonus += 0.5
            if (
                deck_directive.pacing_role == PacingRole.TRANSITION
                and plan.layout_family
                in {
                    LayoutFamily.STRATEGY_CARDS,
                    LayoutFamily.PROCESS_NARRATIVE,
                    LayoutFamily.METRIC_DASHBOARD,
                }
            ):
                composition_penalty += 0.35
            # Quote posters are for closing/summary — don't steal body content pages.
            if (
                plan.layout_variant == "quote_argument"
                and deck_directive.pacing_role != PacingRole.CLOSING
            ):
                composition_penalty += 0.2

            # Priority weights: hero / text / drawing must move candidate scores.
            if plan.layout_family in {
                LayoutFamily.HERO,
                LayoutFamily.EVIDENCE_BOARD,
                LayoutFamily.HYBRID_CANVAS,
            }:
                composition_bonus += 0.12 * deck_directive.hero_priority
            if plan.layout_family in {
                LayoutFamily.TEXTUAL_ARGUMENT,
                LayoutFamily.STRATEGY_CARDS,
            }:
                composition_bonus += 0.12 * deck_directive.text_priority
            if plan.layout_family in {
                LayoutFamily.DRAWING_FOCUS,
                LayoutFamily.ANALYTICAL_DIAGRAM,
            }:
                composition_bonus += 0.12 * deck_directive.drawing_priority

            # Density waveform affinity.
            if (
                deck_directive.target_density == DensityLevel.SPACIOUS
                and plan.layout_family
                in {
                    LayoutFamily.HERO,
                    LayoutFamily.TEXTUAL_ARGUMENT,
                }
                or deck_directive.target_density == DensityLevel.COMPACT
                and plan.layout_family
                in {
                    LayoutFamily.EVIDENCE_BOARD,
                    LayoutFamily.METRIC_DASHBOARD,
                    LayoutFamily.DRAWING_FOCUS,
                }
            ):
                composition_bonus += 0.05
            elif deck_directive.target_density == DensityLevel.BALANCED and plan.layout_family in {
                LayoutFamily.STRATEGY_CARDS,
                LayoutFamily.COMPARATIVE_MATRIX,
                LayoutFamily.PROCESS_NARRATIVE,
                LayoutFamily.ANALYTICAL_DIAGRAM,
            }:
                composition_bonus += 0.03

        if style_preference is not None and not style_preference.is_empty:
            composition_bonus += style_preference.selection_bonus(
                plan.layout_family,
                plan.layout_variant,
            )
            # No-asset hero openings: prefer monument only when HERO is primary intent.
            primary_pref = (
                style_preference.preferred_families[0]
                if style_preference.preferred_families
                else None
            )
            if (
                primary_pref == LayoutFamily.HERO
                and plan.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                and plan.layout_variant == "monument"
            ):
                composition_bonus += 0.45
            if (
                primary_pref == LayoutFamily.HERO
                and plan.layout_family == LayoutFamily.PROCESS_NARRATIVE
            ):
                composition_penalty += 0.25
            # Keep cover vs body text openers distinct.
            if (
                primary_pref == LayoutFamily.HERO
                and plan.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                and plan.layout_variant == "lead_and_points"
            ):
                composition_penalty += 0.25
            if (
                primary_pref != LayoutFamily.HERO
                and plan.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                and plan.layout_variant == "monument"
            ):
                composition_penalty += 0.3
            if (
                plan.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                and plan.layout_variant == "section_opener"
            ):
                composition_bonus += 0.42
            # When the intent wants an asset-led family we don't have assets for,
            # prefer sparse text openers over strategy/process shells that invent cards.
            # Do NOT demote STRATEGY_CARDS when it is the explicit primary preference.
            asset_led = {
                LayoutFamily.HERO,
                LayoutFamily.HYBRID_CANVAS,
                LayoutFamily.DRAWING_FOCUS,
                LayoutFamily.EVIDENCE_BOARD,
                LayoutFamily.ANALYTICAL_DIAGRAM,
            }
            if primary_pref in asset_led:
                if (
                    plan.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                    and plan.layout_variant in {"lead_and_points", "section_opener"}
                ):
                    composition_bonus += 0.2
                if plan.layout_family == LayoutFamily.STRATEGY_CARDS:
                    composition_penalty += 0.15
                if plan.layout_family == LayoutFamily.PROCESS_NARRATIVE:
                    composition_penalty += 0.2
            elif primary_pref == LayoutFamily.STRATEGY_CARDS:
                if plan.layout_family == LayoutFamily.STRATEGY_CARDS:
                    composition_bonus += 0.28
                if plan.layout_variant == "strategy_concept":
                    composition_bonus += 0.12

        if previous_layout_plan is not None:
            preferred_primary = (
                style_preference.preferred_families[0]
                if style_preference is not None and style_preference.preferred_families
                else None
            )
            honor_explicit_preference = (
                preferred_primary is not None and plan.layout_family == preferred_primary
            )
            if plan.layout_family == previous_layout_plan.layout_family:
                if honor_explicit_preference:
                    # Studio/user preferred family outranks anti-repetition.
                    pass
                elif deck_directive is not None and deck_directive.should_contrast_previous:
                    composition_penalty += 0.12
                elif deck_directive is not None and deck_directive.should_match_previous:
                    composition_bonus += 0.05
                else:
                    composition_penalty += 0.04
            if (
                plan.layout_variant == previous_layout_plan.layout_variant
                and not honor_explicit_preference
            ):
                composition_penalty += 0.06
            # Same text shell twice in a row reads as wallpaper — push alternate variants.
            if (
                previous_layout_plan.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                and previous_layout_plan.layout_variant == "lead_and_points"
                and not honor_explicit_preference
            ):
                if (
                    plan.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                    and plan.layout_variant == "lead_and_points"
                ):
                    composition_penalty += 0.22
                elif plan.layout_variant in {"two_column_text", "quote_argument", "monument"}:
                    composition_bonus += 0.18
                elif plan.layout_family == LayoutFamily.STRATEGY_CARDS:
                    composition_bonus += 0.12

        # Prevent an A-B-A wallpaper rhythm. The immediate predecessor already
        # receives the stronger penalty above; the second-most-recent page gets
        # a lighter penalty so a good family can still recur after a real beat.
        history = list(recent_layout_plans or [])
        for distance, recent in enumerate(reversed(history[-3:]), start=1):
            if previous_layout_plan is not None and recent.id == previous_layout_plan.id:
                continue
            if plan.layout_family == recent.layout_family:
                composition_penalty += 0.06 / distance
            if (
                plan.layout_family == recent.layout_family
                and plan.layout_variant == recent.layout_variant
            ):
                composition_penalty += 0.16 / distance
                if plan.layout_variant in {"lead_and_points", "two_column_text"}:
                    composition_penalty += 0.14 / distance
            # Prefer a contrasting text variant when lead_and_points already appeared.
            if (
                recent.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                and recent.layout_variant == "lead_and_points"
                and plan.layout_variant == "two_column_text"
            ):
                composition_bonus += 0.12 / distance
            if (
                recent.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
                and recent.layout_variant == "lead_and_points"
                and plan.layout_variant == "quote_argument"
                and deck_directive is not None
                and deck_directive.pacing_role == PacingRole.CLOSING
            ):
                composition_bonus += 0.1 / distance

        return (
            validity_rank + composition_penalty,
            score_rank - composition_bonus,
            composition_penalty,
            str(plan.id),
        )

    def _decide_candidates(
        self,
        slide: SlideSpec,
        intent: VisualIntent,
        art: ArtDirection | None,
        design: DesignSystem,
        candidate_count: int,
        deck_directive: SlideCompositionDirective | None = None,
        style_preference: LayoutStylePreference | None = None,
    ) -> list[LayoutDecisionDraft]:
        _ = design  # reserved for future design-aware family filters
        # Requirements describe desired media, not media that can actually be
        # placed. Only bound assets may unlock asset-dependent layout families.
        asset_count = (1 if intent.hero_asset_id else 0) + len(intent.supporting_asset_ids)
        style_pref = style_preference or LayoutStylePreference()
        # Rank: deck rhythm → slide intent (user/explicit) → reference style cues.
        preferred_for_registry = merge_preferred_families(
            list(deck_directive.preferred_layout_families) if deck_directive else None,
            list(intent.preferred_layout_families),
            list(style_pref.preferred_families),
        )

        if self._llm is not None:
            allowed = [
                item.family.value
                for item in self._registry.candidates_for(
                    intent.dominant_content_type,
                    asset_count=max(asset_count, 0),
                    preferred=preferred_for_registry,
                )
            ]
            allowed = self._filter_allowed_families(
                allowed,
                deck_directive,
                preferred_order=preferred_for_registry,
            )
            key_point_count = len(slide.key_points)
            is_title_slide = slide.slide_type == SlideType.TITLE
            is_section_opener = (
                slide.slide_type == SlideType.SECTION
                or intent.continuity_role == ContinuityRole.SECTION_OPENING
            )
            try:
                request, skill_audit = apply_skills_to_request(
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
                    task_type="layout_plan",
                    slide_type=str(getattr(slide, "slide_type", "") or ""),
                )
                from archium.application.agent_skills.audit_store import record_skill_audit

                record_skill_audit(
                    skill_audit,
                    presentation_id=slide.presentation_id,
                    slide_id=slide.id,
                    settings=self._settings,
                )
                draft = self._llm.generate_structured(
                    request,
                    LayoutDecisionDraft,
                )
                if draft.layout_family in allowed:
                    primary = draft
                    extras = self._rule_decisions(
                        intent,
                        asset_count,
                        candidate_count,
                        deck_directive=deck_directive,
                        style_preference=style_pref,
                        key_point_count=key_point_count,
                        is_title_slide=is_title_slide,
                        is_section_opener=is_section_opener,
                    )
                    merged = [primary]
                    for extra in extras:
                        if extra.layout_family == primary.layout_family and (
                            extra.layout_variant == primary.layout_variant
                        ):
                            continue
                        merged.append(extra)
                        if len(merged) >= candidate_count:
                            break
                    return self._apply_preference_to_decisions(
                        merged[:candidate_count],
                        deck_directive,
                        style_pref,
                        candidate_count,
                    )
                fallback = self._rule_decisions(
                    intent,
                    asset_count,
                    candidate_count,
                    deck_directive=deck_directive,
                    style_preference=style_pref,
                    key_point_count=key_point_count,
                    is_title_slide=is_title_slide,
                    is_section_opener=is_section_opener,
                )
                self._record_llm_fallback(
                    error_type="DisallowedLayoutFamily",
                    fallback_family=fallback[0].layout_family,
                    detail=f"llm_family={draft.layout_family}",
                )
                return fallback
            except Exception as exc:
                fallback = self._rule_decisions(
                    intent,
                    asset_count,
                    candidate_count,
                    deck_directive=deck_directive,
                    style_preference=style_pref,
                    key_point_count=key_point_count,
                    is_title_slide=is_title_slide,
                    is_section_opener=is_section_opener,
                )
                self._record_llm_fallback(
                    error_type=type(exc).__name__,
                    fallback_family=fallback[0].layout_family,
                )
                return fallback

        return self._rule_decisions(
            intent,
            asset_count,
            candidate_count,
            deck_directive=deck_directive,
            style_preference=style_pref,
            key_point_count=len(slide.key_points),
            is_title_slide=slide.slide_type == SlideType.TITLE,
            is_section_opener=(
                slide.slide_type == SlideType.SECTION
                or intent.continuity_role == ContinuityRole.SECTION_OPENING
            ),
        )

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
        deck_directive: SlideCompositionDirective | None = None,
        style_preference: LayoutStylePreference | None = None,
        *,
        key_point_count: int = 0,
        is_title_slide: bool = False,
        is_section_opener: bool = False,
    ) -> list[LayoutDecisionDraft]:
        style_pref = style_preference or LayoutStylePreference()
        preferred = merge_preferred_families(
            list(deck_directive.preferred_layout_families) if deck_directive else None,
            list(intent.preferred_layout_families),
            list(style_pref.preferred_families),
        )
        definitions = self._registry.candidates_for(
            intent.dominant_content_type,
            asset_count=max(asset_count, 0),
            preferred=preferred,
        )
        # Deck composition sees narrative context (titles, pacing, neighboring
        # slides) that a per-slide intent may miss. When it explicitly selects
        # a semantic specialist, let that family enter the candidate pool even
        # if the earlier intent classifier only emitted generic text_argument.
        if deck_directive and deck_directive.preferred_layout_families:
            primary = deck_directive.preferred_layout_families[0]
            if primary in _SEMANTIC_SPECIALIST_FAMILIES:
                specialist = self._registry.get(primary)
                asset_compatible = specialist.min_assets <= asset_count <= specialist.max_assets
                requires_missing_hero = (
                    asset_count == 0
                    and LayoutElementRole.HERO_VISUAL in specialist.required_roles
                )
                if specialist.implemented and asset_compatible and not requires_missing_hero:
                    definitions = [
                        specialist,
                        *(item for item in definitions if item.family != primary),
                    ]
        grammar_forbidden = forbidden_families_for_intent(intent)
        decisions: list[LayoutDecisionDraft] = []
        # No presentation-ready hero asset → text monument cover, not a tiny image
        # floating in empty whitespace.
        hero_families = {LayoutFamily.HERO, LayoutFamily.DRAWING_FOCUS}
        prefers_hero = bool(
            set(intent.preferred_layout_families) & hero_families
            or intent.dominant_content_type
            in {
                VisualContentType.HERO_IMAGE,
                VisualContentType.SITE_PLAN,
                VisualContentType.FLOOR_PLAN,
                VisualContentType.SECTION,
                VisualContentType.ELEVATION,
            }
        )
        if (
            prefers_hero
            and intent.hero_asset_id is None
            and asset_count == 0
            and (is_title_slide or intent.continuity_role == ContinuityRole.OPENING)
        ):
            decisions.append(
                LayoutDecisionDraft(
                    layout_family=LayoutFamily.TEXTUAL_ARGUMENT.value,
                    layout_variant="monument",
                    reading_order=list(intent.reading_order),
                    density_adjustment=DensityLevel.SPACIOUS.value,
                )
            )
        # Chapter 扉页 without a hero: index + short title, never invent strategy cards.
        if is_section_opener and intent.hero_asset_id is None and asset_count == 0:
            decisions.append(
                LayoutDecisionDraft(
                    layout_family=LayoutFamily.TEXTUAL_ARGUMENT.value,
                    layout_variant="section_opener",
                    reading_order=list(intent.reading_order),
                    density_adjustment=DensityLevel.SPACIOUS.value,
                )
            )
        # Sparse text pages: never prefer strategy/process shells that invent cards.
        sparse_copy = asset_count == 0 and key_point_count < 2
        if (
            sparse_copy
            and not is_section_opener
            and intent.dominant_content_type
            in {
                VisualContentType.TEXT_ARGUMENT,
                VisualContentType.MIXED,
                VisualContentType.PHOTO_EVIDENCE,
                VisualContentType.PROCESS,
            }
        ):
            decisions.append(
                LayoutDecisionDraft(
                    layout_family=LayoutFamily.TEXTUAL_ARGUMENT.value,
                    layout_variant=(
                        "monument" if is_title_slide else "lead_and_points"
                    ),
                    reading_order=list(intent.reading_order),
                    density_adjustment=DensityLevel.SPACIOUS.value,
                )
            )
        if (
            deck_directive is not None
            and deck_directive.transition_mode
            and asset_count > 0
            and LayoutFamily.HERO not in deck_directive.forbidden_layout_families
        ):
            decisions.append(
                LayoutDecisionDraft(
                    layout_family=LayoutFamily.HERO.value,
                    layout_variant="full_bleed",
                    hero_content_ref=(str(intent.hero_asset_id) if intent.hero_asset_id else None),
                    supporting_content_refs=[
                        str(asset_id) for asset_id in intent.supporting_asset_ids
                    ],
                    reading_order=list(intent.reading_order),
                    density_adjustment=DensityLevel.SPACIOUS.value,
                )
            )
        pool_limit = max(candidate_count * 3, candidate_count, 6)
        _SECTION_OPENER_SKIP = frozenset(
            {
                LayoutFamily.STRATEGY_CARDS,
                LayoutFamily.PROCESS_NARRATIVE,
                LayoutFamily.METRIC_DASHBOARD,
            }
        )
        for definition in definitions:
            if (
                is_section_opener
                and asset_count == 0
                and intent.hero_asset_id is None
                and definition.family in _SECTION_OPENER_SKIP
            ):
                continue
            if (
                deck_directive is not None
                and definition.family in deck_directive.forbidden_layout_families
            ):
                continue
            closing_poster_override = (
                deck_directive is not None
                and deck_directive.pacing_role == PacingRole.CLOSING
                and definition.family == LayoutFamily.TEXTUAL_ARGUMENT
            )
            monument_cover_override = (
                prefers_hero
                and intent.hero_asset_id is None
                and asset_count == 0
                and definition.family == LayoutFamily.TEXTUAL_ARGUMENT
            )
            section_opener_override = (
                is_section_opener
                and intent.hero_asset_id is None
                and asset_count == 0
                and definition.family == LayoutFamily.TEXTUAL_ARGUMENT
            )
            if (
                definition.family in grammar_forbidden
                and not closing_poster_override
                and not monument_cover_override
                and not section_opener_override
            ):
                continue
            variants = self._order_variants(
                definition.family,
                order_variants_for_intent(
                    intent,
                    definition.family,
                    definition.supported_variants,
                ),
                style_pref,
            )
            if (
                is_section_opener
                and asset_count == 0
                and intent.hero_asset_id is None
                and definition.family == LayoutFamily.TEXTUAL_ARGUMENT
            ):
                variants = [
                    "section_opener",
                    *[v for v in variants if v != "section_opener"],
                ]
            # strategy_concept needs a real hero image; without assets prefer cards.
            if (
                definition.family == LayoutFamily.STRATEGY_CARDS
                and asset_count == 0
                and intent.hero_asset_id is None
            ):
                variants = [
                    v for v in variants if v != "strategy_concept"
                ] or ["cards_with_lead"]
            # four_cards with fewer than 4 points leaves an empty slot / mechanical grid.
            if (
                definition.family == LayoutFamily.STRATEGY_CARDS
                and key_point_count < 4
            ):
                variants = [v for v in variants if v != "four_cards"] or variants
            for variant in variants:
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
                        density_adjustment=(
                            DensityLevel.SPACIOUS.value
                            if is_section_opener and asset_count == 0
                            else intent.density_level.value
                        ),
                        split_recommended=False,
                        split_reason=None,
                    )
                )
            if len(decisions) >= pool_limit:
                break
        if not decisions:
            decisions.append(
                LayoutDecisionDraft(
                    layout_family=LayoutFamily.TEXTUAL_ARGUMENT.value,
                    layout_variant=(
                        "section_opener"
                        if is_section_opener
                        else "lead_and_points"
                    ),
                    reading_order=list(intent.reading_order),
                    density_adjustment=intent.density_level.value,
                )
            )
        return self._apply_preference_to_decisions(
            decisions,
            deck_directive,
            merge_layout_style_preferences(
                LayoutStylePreference(
                    preferred_families=tuple(intent.preferred_layout_families),
                ),
                style_pref,
            ),
            candidate_count,
        )

    @staticmethod
    def _order_variants(
        family: LayoutFamily,
        variants: Sequence[str],
        style_preference: LayoutStylePreference,
    ) -> list[str]:
        if style_preference.is_empty:
            return list(variants)
        preferred = [
            variant
            for preferred_family, variant in style_preference.preferred_variants
            if preferred_family == family and variant in variants
        ]
        ordered = list(dict.fromkeys([*preferred, *variants]))
        return ordered

    @staticmethod
    def _filter_allowed_families(
        allowed: list[str],
        deck_directive: SlideCompositionDirective | None,
        preferred_order: list[LayoutFamily] | None = None,
        style_preference: LayoutStylePreference | None = None,
    ) -> list[str]:
        filtered = list(allowed)
        if deck_directive is not None:
            forbidden = {family.value for family in deck_directive.forbidden_layout_families}
            filtered = [family for family in filtered if family not in forbidden]
        preferred: list[str] = []
        if preferred_order:
            preferred.extend(family.value for family in preferred_order)
        else:
            if deck_directive is not None and deck_directive.preferred_layout_families:
                preferred.extend(
                    family.value for family in deck_directive.preferred_layout_families
                )
            if style_preference is not None and style_preference.preferred_families:
                preferred.extend(family.value for family in style_preference.preferred_families)
        if preferred:
            ordered = [family for family in preferred if family in filtered]
            ordered.extend(family for family in filtered if family not in ordered)
            return ordered or filtered or allowed
        return filtered or allowed

    @staticmethod
    def _apply_directive_to_decisions(
        decisions: list[LayoutDecisionDraft],
        deck_directive: SlideCompositionDirective | None,
        candidate_count: int,
    ) -> list[LayoutDecisionDraft]:
        """Backward-compatible wrapper used by older tests."""
        return LayoutPlanningService._apply_preference_to_decisions(
            decisions,
            deck_directive,
            LayoutStylePreference(),
            candidate_count,
        )

    @staticmethod
    def _apply_preference_to_decisions(
        decisions: list[LayoutDecisionDraft],
        deck_directive: SlideCompositionDirective | None,
        style_preference: LayoutStylePreference | None,
        candidate_count: int,
    ) -> list[LayoutDecisionDraft]:
        if not decisions:
            return []
        style_pref = style_preference or LayoutStylePreference()
        pool = list(decisions)

        preferred_families = merge_preferred_families(
            list(deck_directive.preferred_layout_families) if deck_directive else None,
            list(style_pref.preferred_families),
        )
        # Style variants refine within families; deck family rank still wins.
        preferred_family_values = [family.value for family in preferred_families]
        preferred_variant_keys = [
            (family.value, variant) for family, variant in style_pref.preferred_variants
        ]
        hero_without_asset_cover = (
            bool(preferred_families) and preferred_families[0] == LayoutFamily.HERO
        )
        section_opener_text = any(
            item.layout_family == LayoutFamily.TEXTUAL_ARGUMENT.value
            and item.layout_variant == "section_opener"
            for item in pool
        )

        if deck_directive is not None:
            forbidden = {family.value for family in deck_directive.forbidden_layout_families}
            filtered = []
            for item in pool:
                if item.layout_family not in forbidden:
                    filtered.append(item)
                    continue
                if (
                    hero_without_asset_cover
                    and item.layout_family == LayoutFamily.TEXTUAL_ARGUMENT.value
                    and item.layout_variant == "monument"
                ):
                    filtered.append(item)
                elif (
                    section_opener_text
                    and item.layout_family == LayoutFamily.TEXTUAL_ARGUMENT.value
                    and item.layout_variant == "section_opener"
                ):
                    filtered.append(item)
            pool = filtered or list(decisions)

        def sort_key(item: LayoutDecisionDraft) -> tuple[int, int, int, int, int, int, str, str]:
            # No-asset hero openings must keep the text monument ahead of process/cards.
            monument_rank = (
                0
                if hero_without_asset_cover
                and item.layout_family == LayoutFamily.TEXTUAL_ARGUMENT.value
                and item.layout_variant == "monument"
                else 1
            )
            section_rank = (
                0
                if item.layout_family == LayoutFamily.TEXTUAL_ARGUMENT.value
                and item.layout_variant == "section_opener"
                and (
                    (
                        deck_directive is not None
                        and deck_directive.pacing_role == PacingRole.TRANSITION
                    )
                    or section_opener_text
                )
                else 1
            )
            # When primary preference needs assets we don't have, prefer sparse text
            # openers over process/strategy shells that invent placeholder cards.
            asset_heavy = {
                LayoutFamily.HERO,
                LayoutFamily.HYBRID_CANVAS,
                LayoutFamily.DRAWING_FOCUS,
                LayoutFamily.EVIDENCE_BOARD,
                LayoutFamily.ANALYTICAL_DIAGRAM,
            }
            primary = preferred_families[0] if preferred_families else None
            asset_starved_text = (
                primary in asset_heavy
                and item.layout_family == LayoutFamily.TEXTUAL_ARGUMENT.value
                and (
                    (primary == LayoutFamily.HERO and item.layout_variant == "monument")
                    or item.layout_variant == "section_opener"
                    or (
                        primary != LayoutFamily.HERO
                        and item.layout_variant == "lead_and_points"
                    )
                )
            )
            sparse_rank = 0 if asset_starved_text else 1
            if preferred_family_values and item.layout_family in preferred_family_values:
                family_rank = preferred_family_values.index(item.layout_family)
            else:
                family_rank = len(preferred_family_values)
            variant_key = (item.layout_family, item.layout_variant)
            if preferred_variant_keys and variant_key in preferred_variant_keys:
                variant_rank = preferred_variant_keys.index(variant_key)
            else:
                variant_rank = len(preferred_variant_keys)
            closing_rank = (
                0
                if deck_directive is not None
                and deck_directive.pacing_role == PacingRole.CLOSING
                and item.layout_family == LayoutFamily.TEXTUAL_ARGUMENT.value
                and item.layout_variant == "quote_argument"
                else 1
            )
            return (
                section_rank,
                monument_rank,
                sparse_rank,
                family_rank,
                closing_rank,
                variant_rank,
                item.layout_family,
                item.layout_variant,
            )

        pool = sorted(pool, key=sort_key)
        deduped: list[LayoutDecisionDraft] = []
        seen: set[tuple[str, str]] = set()
        for item in pool:
            key = (item.layout_family, item.layout_variant)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        # Give the deck selector one candidate from each family before adding
        # near-identical sibling variants from an already represented family.
        diversified: list[LayoutDecisionDraft] = []
        deferred: list[LayoutDecisionDraft] = []
        seen_families: set[str] = set()
        for item in deduped:
            if item.layout_family in seen_families:
                deferred.append(item)
                continue
            seen_families.add(item.layout_family)
            diversified.append(item)
        diversified.extend(deferred)
        return diversified[:candidate_count]


def format_layout_decision_warnings(warnings: list[dict[str, Any]]) -> list[str]:
    """Human-readable lines for workflow / UI warning lists."""
    lines: list[str] = []
    for item in warnings:
        code = str(item.get("code") or "")
        if code == LAYOUT_DECISION_LLM_FALLBACK:
            lines.append(
                f"{LAYOUT_DECISION_LLM_FALLBACK} "
                f"provider={item.get('provider', '?')} "
                f"model={item.get('model', '?')} "
                f"error_type={item.get('error_type', '?')} "
                f"fallback_family={item.get('fallback_family', '?')}"
                + (f" detail={item['detail']}" if item.get("detail") else "")
            )
            continue
        if code.startswith("CAPACITY."):
            severity = item.get("severity", "info")
            detail = item.get("detail") or code
            action = item.get("recommended_action")
            suffix = f" action={action}" if action else ""
            lines.append(f"{code} [{severity}] {detail}{suffix}")
    return lines


def capacity_blocker_messages(warnings: list[dict[str, Any]]) -> list[str]:
    """Hard-stop messages for capacity gates that block layout candidates."""
    messages: list[str] = []
    for item in warnings:
        code = item.get("code")
        if code not in {CAPACITY_IMPOSSIBLE_RULE, CAPACITY_OVERLOAD_RULE}:
            continue
        if code == CAPACITY_OVERLOAD_RULE and item.get("severity") != "blocker":
            continue
        detail = item.get("detail") or code
        messages.append(f"{code}: {detail}")
    return messages

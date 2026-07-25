"""Map ConceptDirection selection onto Mission DesignIntent (+ spatial layer)."""

from __future__ import annotations

from archium.application.spatial_design_layer import (
    design_rules_from_direction,
    ensure_direction_spatial_layer,
    spatial_intent_from_direction,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.intent.design_intent import DesignIntent


def design_intent_from_direction(
    direction: ConceptDirection,
    *,
    base: DesignIntent | None = None,
) -> DesignIntent:
    from archium.application.intent_evidence_helpers import (
        evidence_from_direction_selection,
    )

    enriched = ensure_direction_spatial_layer(direction)
    seed = base or DesignIntent()
    spatial = enriched.spatial_intent or spatial_intent_from_direction(enriched)
    rules = list(enriched.design_rules) or design_rules_from_direction(enriched)
    # Preserve base spatial if direction had none
    if spatial is None and seed.spatial_intent is not None:
        spatial = seed.spatial_intent
    if not rules and seed.design_rules:
        rules = list(seed.design_rules)

    intent = DesignIntent(
        theme=enriched.theme or enriched.title or seed.theme,
        problem_statement=enriched.summary or seed.problem_statement,
        social_background=seed.social_background,
        cultural_context=seed.cultural_context,
        target_users=list(seed.target_users),
        desired_experience=enriched.experience_focus or seed.desired_experience,
        core_questions=list(enriched.open_questions) or list(seed.core_questions),
        research_needed=list(seed.research_needed),
        working_assumptions=list(seed.working_assumptions),
        evidence=list(seed.evidence),
        design_rationale=enriched.design_rationale or seed.design_rationale,
        spatial_intent=spatial,
        design_rules=rules,
    )
    return intent.with_evidence(evidence_from_direction_selection(enriched))

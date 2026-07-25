"""Map ConceptDirection selection onto Mission DesignIntent."""

from __future__ import annotations

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

    seed = base or DesignIntent()
    intent = DesignIntent(
        theme=direction.theme or direction.title or seed.theme,
        problem_statement=direction.summary or seed.problem_statement,
        social_background=seed.social_background,
        cultural_context=seed.cultural_context,
        target_users=list(seed.target_users),
        desired_experience=direction.experience_focus or seed.desired_experience,
        core_questions=list(direction.open_questions) or list(seed.core_questions),
        research_needed=list(seed.research_needed),
        working_assumptions=list(seed.working_assumptions),
        evidence=list(seed.evidence),
        design_rationale=direction.design_rationale,
    )
    return intent.with_evidence(evidence_from_direction_selection(direction))

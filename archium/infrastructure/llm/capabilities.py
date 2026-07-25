"""LLM capability keys — task intent for routing (not Agent classes).

Maps product tasks onto existing ``ModelRole`` values so Services ask for a
capability, and ``LLMRuntime`` selects the model profile.
"""

from __future__ import annotations

from enum import StrEnum

from archium.domain.model_roles import ModelRole


class LLMCapability(StrEnum):
    """What the caller needs the model to do."""

    CONCEPT_GENERATION = "concept_generation"
    IDEA_SEED = "idea_seed"
    MISSION_GENERATION = "mission_generation"
    RESEARCH_SYNTHESIS = "research_synthesis"
    DESIGN_CRITIQUE = "design_critique"
    CONTEXT_ASSESSMENT = "context_assessment"
    FACT_EXTRACTION = "fact_extraction"
    STRUCTURED_DEFAULT = "structured_default"


# Capability → ModelRole (reuse existing registry; no new Agent roles).
CAPABILITY_TO_MODEL_ROLE: dict[LLMCapability, ModelRole] = {
    LLMCapability.CONCEPT_GENERATION: ModelRole.PLANNING,
    LLMCapability.IDEA_SEED: ModelRole.STRUCTURED_OUTPUT,
    LLMCapability.MISSION_GENERATION: ModelRole.PLANNING,
    LLMCapability.RESEARCH_SYNTHESIS: ModelRole.RESEARCH,
    LLMCapability.DESIGN_CRITIQUE: ModelRole.PLANNING,
    LLMCapability.CONTEXT_ASSESSMENT: ModelRole.STRUCTURED_OUTPUT,
    LLMCapability.FACT_EXTRACTION: ModelRole.STRUCTURED_OUTPUT,
    LLMCapability.STRUCTURED_DEFAULT: ModelRole.STRUCTURED_OUTPUT,
}


def model_role_for_capability(capability: LLMCapability) -> ModelRole:
    return CAPABILITY_TO_MODEL_ROLE.get(capability, ModelRole.STRUCTURED_OUTPUT)

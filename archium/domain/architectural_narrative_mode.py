"""Architectural narrative modes, independent from visual art direction."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.enums import NarrativeStage


class ArchitecturalNarrativeMode(StrEnum):
    DECISION_FIRST = "decision_first"
    PROBLEM_SOLUTION = "problem_solution"
    EVIDENCE_ARGUMENT = "evidence_argument"
    DESIGN_PROCESS = "design_process"
    OPTION_COMPARISON = "option_comparison"
    TECHNICAL_BRIEFING = "technical_briefing"
    PHASED_IMPLEMENTATION = "phased_implementation"
    PUBLIC_STORYTELLING = "public_storytelling"


class NarrativeModeContract(DomainModel):
    mode: ArchitecturalNarrativeMode
    stage_sequence: tuple[NarrativeStage, ...]
    required_questions: tuple[str, ...] = Field(default_factory=tuple)
    suitable_decision_contexts: tuple[str, ...] = Field(default_factory=tuple)


NARRATIVE_MODE_CONTRACTS: dict[ArchitecturalNarrativeMode, NarrativeModeContract] = {
    ArchitecturalNarrativeMode.DECISION_FIRST: NarrativeModeContract(
        mode=ArchitecturalNarrativeMode.DECISION_FIRST,
        stage_sequence=(
            NarrativeStage.DECISION,
            NarrativeStage.EVIDENCE,
            NarrativeStage.STRATEGY,
            NarrativeStage.TENSION,
            NarrativeStage.DECISION,
        ),
        required_questions=("What decision is requested?", "What evidence supports it?"),
        suitable_decision_contexts=("executive_review", "approval", "investment_decision"),
    ),
    ArchitecturalNarrativeMode.PROBLEM_SOLUTION: NarrativeModeContract(
        mode=ArchitecturalNarrativeMode.PROBLEM_SOLUTION,
        stage_sequence=(
            NarrativeStage.CONTEXT,
            NarrativeStage.PROBLEM,
            NarrativeStage.EVIDENCE,
            NarrativeStage.STRATEGY,
            NarrativeStage.RESOLUTION,
            NarrativeStage.DECISION,
        ),
        required_questions=("What is wrong now?", "How does the proposal resolve it?"),
        suitable_decision_contexts=("renovation", "urban_regeneration", "problem_review"),
    ),
    ArchitecturalNarrativeMode.EVIDENCE_ARGUMENT: NarrativeModeContract(
        mode=ArchitecturalNarrativeMode.EVIDENCE_ARGUMENT,
        stage_sequence=(
            NarrativeStage.CONTEXT,
            NarrativeStage.EVIDENCE,
            NarrativeStage.TENSION,
            NarrativeStage.STRATEGY,
            NarrativeStage.DECISION,
        ),
        required_questions=("What can be proven?", "What conclusion follows?"),
        suitable_decision_contexts=("research", "planning_basis", "feasibility"),
    ),
    ArchitecturalNarrativeMode.DESIGN_PROCESS: NarrativeModeContract(
        mode=ArchitecturalNarrativeMode.DESIGN_PROCESS,
        stage_sequence=(
            NarrativeStage.CONTEXT,
            NarrativeStage.PROBLEM,
            NarrativeStage.STRATEGY,
            NarrativeStage.RESOLUTION,
        ),
        suitable_decision_contexts=("design_review", "competition", "concept_report"),
    ),
    ArchitecturalNarrativeMode.OPTION_COMPARISON: NarrativeModeContract(
        mode=ArchitecturalNarrativeMode.OPTION_COMPARISON,
        stage_sequence=(
            NarrativeStage.CONTEXT,
            NarrativeStage.EVIDENCE,
            NarrativeStage.TENSION,
            NarrativeStage.RESOLUTION,
            NarrativeStage.DECISION,
        ),
        required_questions=("Which criteria decide?", "Why is the preferred option stronger?"),
        suitable_decision_contexts=("option_selection", "scheme_comparison"),
    ),
    ArchitecturalNarrativeMode.TECHNICAL_BRIEFING: NarrativeModeContract(
        mode=ArchitecturalNarrativeMode.TECHNICAL_BRIEFING,
        stage_sequence=(
            NarrativeStage.CONTEXT,
            NarrativeStage.EVIDENCE,
            NarrativeStage.STRATEGY,
            NarrativeStage.RESOLUTION,
        ),
        suitable_decision_contexts=("technical_review", "coordination", "compliance"),
    ),
    ArchitecturalNarrativeMode.PHASED_IMPLEMENTATION: NarrativeModeContract(
        mode=ArchitecturalNarrativeMode.PHASED_IMPLEMENTATION,
        stage_sequence=(
            NarrativeStage.CONTEXT,
            NarrativeStage.PROBLEM,
            NarrativeStage.STRATEGY,
            NarrativeStage.RESOLUTION,
            NarrativeStage.DECISION,
        ),
        required_questions=("What is delivered in each phase?", "What unlocks the next phase?"),
        suitable_decision_contexts=("implementation", "delivery_plan", "roadmap"),
    ),
    ArchitecturalNarrativeMode.PUBLIC_STORYTELLING: NarrativeModeContract(
        mode=ArchitecturalNarrativeMode.PUBLIC_STORYTELLING,
        stage_sequence=(
            NarrativeStage.CONTEXT,
            NarrativeStage.PROBLEM,
            NarrativeStage.TENSION,
            NarrativeStage.RESOLUTION,
        ),
        suitable_decision_contexts=("public_consultation", "exhibition", "community"),
    ),
}


def contract_for_narrative_mode(mode: ArchitecturalNarrativeMode) -> NarrativeModeContract:
    return NARRATIVE_MODE_CONTRACTS[mode]


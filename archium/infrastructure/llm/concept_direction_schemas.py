"""Structured LLM output for concept direction drafts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConceptVisualPromptDraft(BaseModel):
    image_prompt: str = Field(
        default="",
        description="English or bilingual scene description for image generation",
    )
    camera: str = Field(
        default="",
        description="e.g. architectural axonometric, eye-level street view",
    )
    style: str = Field(
        default="",
        description="e.g. concept sketch, marker sketch, soft atmosphere",
    )


class DesignRationaleAlternativeDraft(BaseModel):
    label: str = ""
    note: str = ""


class DesignRationaleDraft(BaseModel):
    statement: str = Field(
        default="",
        description="One-sentence design claim this direction makes",
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="2–4 why bullets: climate, typology, user, context",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Cited constraints or facts from user/materials (no invented metrics)",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    alternatives: list[DesignRationaleAlternativeDraft] = Field(
        default_factory=list,
        description="1–2 options considered but not chosen, with brief trade-off",
    )


class ConceptDirectionDraft(BaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    theme: str = ""
    spatial_idea: str = ""
    spatial_strategy: str = Field(
        default="",
        description="Organizational strategy: axis, courtyard, linear, embedded, etc.",
    )
    formal_language: str = Field(
        default="",
        description="Massing/form language: heavy stone, floating volume, continuous roof",
    )
    material_strategy: str = Field(
        default="",
        description="Primary materials and tectonic attitude",
    )
    reference_dna: list[str] = Field(
        default_factory=list,
        description="2–4 reference genes (architects, typologies, atmospheres) — not plagiarism",
    )
    reference_case_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Optional ArchitectureCase seed ids (e.g. ningbo_museum, therme_vals). "
            "Prefer known library ids over inventing names."
        ),
    )
    visual_prompt: ConceptVisualPromptDraft | None = None
    design_rationale: DesignRationaleDraft | None = None
    experience_focus: str = ""
    differentiator: str = ""
    open_questions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class ConceptDirectionBatchDraft(BaseModel):
    directions: list[ConceptDirectionDraft] = Field(default_factory=list)

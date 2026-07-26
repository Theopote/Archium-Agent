"""Reasoning artifact — identity wrapper around DesignRationale.

Phase R2: thin node with id + project_id + typed evidence refs.
No separate Agent; no mandatory table — nests on ConceptDirection JSON.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel
from archium.domain.case_ref import normalize_case_id_list
from archium.domain.design_rationale import DesignRationale

REASONING_ARTIFACT_KIND = "reasoning_artifact"


class ReasoningEvidenceRefs(DomainModel):
    """Typed evidence pointers bound to one reasoning node."""

    case_ids: list[str] = Field(
        default_factory=list,
        description="Bare ArchitectureCase ids (e.g. ningbo_museum).",
    )
    knowledge_item_ids: list[UUID] = Field(
        default_factory=list,
        description="ProjectKnowledgeItem ids cited by this reasoning node.",
    )

    @field_validator("case_ids", mode="before")
    @classmethod
    def _normalize_case_ids(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return normalize_case_id_list([str(item) for item in value])
        return []

    @field_validator("knowledge_item_ids", mode="before")
    @classmethod
    def _normalize_knowledge_ids(cls, value: object) -> list[UUID]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        out: list[UUID] = []
        seen: set[UUID] = set()
        for item in value:
            try:
                uid = item if isinstance(item, UUID) else UUID(str(item))
            except (TypeError, ValueError):
                continue
            if uid in seen:
                continue
            seen.add(uid)
            out.append(uid)
            if len(out) >= 16:
                break
        return out

    def is_empty(self) -> bool:
        return not self.case_ids and not self.knowledge_item_ids


class ReasoningArtifact(IdentifiedModel, TimestampedModel):
    """Addressable design-reasoning node for Critic / lineage (not a new Agent)."""

    project_id: UUID
    rationale: DesignRationale
    evidence_refs: ReasoningEvidenceRefs = Field(default_factory=ReasoningEvidenceRefs)
    source_direction_id: UUID | None = None

    def is_empty(self) -> bool:
        return self.rationale.is_empty()

    def is_proceedable(self) -> bool:
        return self.rationale.is_proceedable_chain()

    def to_prompt_block(self) -> str:
        sections: list[str] = []
        block = self.rationale.to_prompt_block()
        if block:
            sections.append(block)
        if self.evidence_refs.case_ids:
            sections.append(
                "推理依据案例："
                + "；".join(self.evidence_refs.case_ids)
            )
        if self.evidence_refs.knowledge_item_ids:
            sections.append(
                "推理依据知识："
                + "；".join(str(uid) for uid in self.evidence_refs.knowledge_item_ids)
            )
        return "\n".join(sections)

    def to_storage_dict(self) -> dict[str, object]:
        """Envelope for nesting in concept_directions.design_rationale JSON."""
        payload = self.model_dump(mode="json")
        payload["_kind"] = REASONING_ARTIFACT_KIND
        return payload


def parse_reasoning_storage(
    raw: dict[str, object] | None,
    *,
    project_id: UUID,
    direction_id: UUID | None = None,
) -> tuple[DesignRationale | None, ReasoningArtifact | None]:
    """Parse legacy flat DesignRationale or ReasoningArtifact envelope from JSON."""
    if not isinstance(raw, dict) or not raw:
        return None, None

    kind = str(raw.get("_kind") or "").strip()
    if kind == REASONING_ARTIFACT_KIND or isinstance(raw.get("rationale"), dict):
        try:
            payload = {k: v for k, v in raw.items() if k != "_kind"}
            if "project_id" not in payload:
                payload["project_id"] = project_id
            if direction_id is not None and not payload.get("source_direction_id"):
                payload["source_direction_id"] = direction_id
            artifact = ReasoningArtifact.model_validate(payload)
        except Exception:
            artifact = None
        if artifact is None or artifact.is_empty():
            return None, None
        return artifact.rationale, artifact

    try:
        rationale = DesignRationale.model_validate(raw)
    except Exception:
        return None, None
    if rationale.is_empty():
        return None, None
    artifact = ReasoningArtifact(
        project_id=project_id,
        rationale=rationale,
        source_direction_id=direction_id,
    )
    return rationale, artifact


def dump_reasoning_storage(
    *,
    reasoning: ReasoningArtifact | None,
    design_rationale: DesignRationale | None,
) -> dict[str, object] | None:
    """Serialize reasoning envelope when present; else flat rationale (legacy)."""
    if reasoning is not None and not reasoning.is_empty():
        return reasoning.to_storage_dict()
    if design_rationale is not None and not design_rationale.is_empty():
        return design_rationale.model_dump(mode="json")
    return None

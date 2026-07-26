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
    verified: bool = Field(
        default=False,
        description="True when Critic allowed proceed with a complete reasoning chain.",
    )
    # Phase L3 — revision identity (DOM-030)
    revision: int = Field(
        default=1,
        ge=1,
        description="1-based reasoning generation; increments on Critic→Revise apply.",
    )
    parent_reasoning_id: UUID | None = Field(
        default=None,
        description="Prior ReasoningArtifact.id when this node was spawned by revise.",
    )
    last_critique_verdict: str = Field(
        default="",
        max_length=40,
        description="Last DesignCritique verdict attached to this generation.",
    )
    last_critique_summary: str = Field(
        default="",
        max_length=400,
        description="Short summary from the critique that produced this generation.",
    )

    def is_empty(self) -> bool:
        return self.rationale.is_empty()

    def is_proceedable(self) -> bool:
        return self.rationale.is_proceedable_chain()

    def mark_verified(self) -> ReasoningArtifact:
        """Return a copy flagged as Critic-verified (stable id / revision)."""
        copy = self.model_copy(update={"verified": True})
        copy.touch()
        return copy

    def with_critique_meta(self, *, verdict: str, summary: str = "") -> ReasoningArtifact:
        """Stamp critique metadata without changing identity."""
        copy = self.model_copy(
            update={
                "last_critique_verdict": (verdict or "").strip()[:40],
                "last_critique_summary": (summary or "").strip()[:400],
            }
        )
        copy.touch()
        return copy

    def spawn_revision(
        self,
        *,
        rationale: DesignRationale,
        evidence_refs: ReasoningEvidenceRefs | None = None,
        critique_verdict: str = "",
        critique_summary: str = "",
    ) -> ReasoningArtifact:
        """Create a new reasoning generation linked to this node as parent (L3)."""
        from archium.domain._base import new_uuid

        child = ReasoningArtifact(
            id=new_uuid(),
            project_id=self.project_id,
            rationale=rationale,
            evidence_refs=evidence_refs or self.evidence_refs,
            source_direction_id=self.source_direction_id,
            verified=False,
            revision=int(self.revision) + 1,
            parent_reasoning_id=self.id,
            last_critique_verdict=(critique_verdict or "").strip()[:40],
            last_critique_summary=(critique_summary or "").strip()[:400],
        )
        return child

    def lineage_dict(self) -> dict[str, object]:
        return {
            "reasoning_id": str(self.id),
            "revision": self.revision,
            "parent_reasoning_id": (
                str(self.parent_reasoning_id) if self.parent_reasoning_id else None
            ),
            "verified": self.verified,
            "last_critique_verdict": self.last_critique_verdict,
            "last_critique_summary": self.last_critique_summary,
        }

    def to_prompt_block(self) -> str:
        sections: list[str] = []
        if self.revision > 1:
            sections.append(f"推理世代：v{self.revision}")
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

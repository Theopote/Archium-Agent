"""Knowledge state history — Git-like snapshots of what the project knows."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.intent.knowledge_state import KnowledgeState

_MAX_SNAPSHOTS = 48


class KnowledgeStateChangeReason(StrEnum):
    INITIAL_ASSESS = "initial_assess"
    REFRESH = "refresh"
    DOCUMENT_UPLOADED = "document_uploaded"
    FACT_CONFIRMED = "fact_confirmed"
    RESEARCH = "research"
    CLARIFICATION_CONTINUED = "clarification_continued"
    MISSION_APPROVED = "mission_approved"
    DIRECTION_SELECTED = "direction_selected"
    MISSION_DIRECTION_SELECTED = "mission_direction_selected"
    MISSION_COMMITTED = "mission_committed"
    NBA_EXPLORE = "nba_explore"
    NBA_GENERATE_MISSION = "nba_generate_mission"
    MANUAL = "manual"
    OTHER = "other"


_REASON_ALIASES: dict[str, KnowledgeStateChangeReason] = {
    "initial_assess": KnowledgeStateChangeReason.INITIAL_ASSESS,
    "refresh": KnowledgeStateChangeReason.REFRESH,
    "document_uploaded": KnowledgeStateChangeReason.DOCUMENT_UPLOADED,
    "fact_confirmed": KnowledgeStateChangeReason.FACT_CONFIRMED,
    "research": KnowledgeStateChangeReason.RESEARCH,
    "clarification_continued": KnowledgeStateChangeReason.CLARIFICATION_CONTINUED,
    "mission_approved": KnowledgeStateChangeReason.MISSION_APPROVED,
    "direction_selected": KnowledgeStateChangeReason.DIRECTION_SELECTED,
    "mission_direction_selected": KnowledgeStateChangeReason.MISSION_DIRECTION_SELECTED,
    "mission_committed": KnowledgeStateChangeReason.MISSION_COMMITTED,
    "nba_explore": KnowledgeStateChangeReason.NBA_EXPLORE,
    "nba_generate_mission": KnowledgeStateChangeReason.NBA_GENERATE_MISSION,
    "manual": KnowledgeStateChangeReason.MANUAL,
}


def normalize_knowledge_change_reason(raw: str | None) -> KnowledgeStateChangeReason:
    key = (raw or "").strip().lower()
    if not key:
        return KnowledgeStateChangeReason.OTHER
    return _REASON_ALIASES.get(key, KnowledgeStateChangeReason.OTHER)


class KnowledgeStateSnapshot(DomainModel):
    """One point-in-time knowledge checkpoint (diff-friendly, not a full dump)."""

    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version_index: int = Field(ge=1, default=1)
    version_label: str = Field(default="v0.1", min_length=1, max_length=32)
    reason: KnowledgeStateChangeReason = KnowledgeStateChangeReason.OTHER
    reason_detail: str = ""
    completeness_score: float = Field(ge=0.0, le=1.0, default=0.0)
    known: dict[str, str] = Field(default_factory=dict)
    unknown: list[str] = Field(default_factory=list)
    added_known_keys: list[str] = Field(default_factory=list)
    resolved_unknown: list[str] = Field(default_factory=list)
    milestone: str = ""
    summary: str = ""


class KnowledgeStateHistory(DomainModel):
    """Ordered knowledge checkpoints for a project (append-only, capped)."""

    snapshots: list[KnowledgeStateSnapshot] = Field(default_factory=list)

    def latest(self) -> KnowledgeStateSnapshot | None:
        return self.snapshots[-1] if self.snapshots else None

    def append_from_state(
        self,
        state: KnowledgeState,
        *,
        reason: str | KnowledgeStateChangeReason | None = None,
        reason_detail: str = "",
        force: bool = False,
    ) -> KnowledgeStateHistory:
        """Append a snapshot when knowledge content meaningfully changes."""
        typed_reason = (
            reason
            if isinstance(reason, KnowledgeStateChangeReason)
            else normalize_knowledge_change_reason(
                reason if isinstance(reason, str) else None
            )
        )
        known = {
            str(k).strip(): str(v).strip()
            for k, v in (state.known or {}).items()
            if str(k).strip() and str(v).strip()
        }
        unknown = [str(u).strip() for u in (state.unknown or []) if str(u).strip()]
        previous = self.latest()
        if (
            not force
            and previous is not None
            and abs(previous.completeness_score - state.completeness_score) < 0.005
            and previous.known == known
            and previous.unknown == unknown
        ):
            return self

        prev_known_keys = set(previous.known) if previous else set()
        prev_unknown = set(previous.unknown) if previous else set()
        added = sorted(set(known) - prev_known_keys)
        resolved = sorted(prev_unknown - set(unknown))

        version_index = (previous.version_index + 1) if previous else 1
        version_label = _next_version_label(
            previous_label=previous.version_label if previous else None,
            completeness=state.completeness_score,
            fallback_index=version_index,
        )
        milestone = _milestone_for(
            completeness=state.completeness_score,
            previous_completeness=previous.completeness_score if previous else None,
            added_known_keys=added,
            resolved_unknown=resolved,
        )
        summary = _snapshot_summary(
            version_label=version_label,
            completeness=state.completeness_score,
            added=added,
            resolved=resolved,
            milestone=milestone,
        )
        snap = KnowledgeStateSnapshot(
            version_index=version_index,
            version_label=version_label,
            reason=typed_reason,
            reason_detail=(reason_detail or "").strip()[:240],
            completeness_score=max(0.0, min(1.0, float(state.completeness_score))),
            known=known,
            unknown=unknown,
            added_known_keys=added,
            resolved_unknown=resolved,
            milestone=milestone,
            summary=summary,
        )
        snapshots = [*self.snapshots, snap]
        if len(snapshots) > _MAX_SNAPSHOTS:
            snapshots = snapshots[-_MAX_SNAPSHOTS:]
        return KnowledgeStateHistory(snapshots=snapshots)


def _next_version_label(
    *,
    previous_label: str | None,
    completeness: float,
    fallback_index: int,
) -> str:
    """v0.n until completeness crosses ~85%, then v1.0 / v1.1 …"""
    if completeness >= 0.85:
        if previous_label and previous_label.startswith("v1."):
            try:
                minor = int(previous_label.split(".", 1)[1]) + 1
                return f"v1.{minor}"
            except (IndexError, ValueError):
                return "v1.0"
        return "v1.0"
    if previous_label and previous_label.startswith("v0."):
        try:
            minor = int(previous_label.split(".", 1)[1]) + 1
            return f"v0.{minor}"
        except (IndexError, ValueError):
            pass
    return f"v0.{fallback_index}"


def _milestone_for(
    *,
    completeness: float,
    previous_completeness: float | None,
    added_known_keys: list[str],
    resolved_unknown: list[str],
) -> str:
    prev = previous_completeness if previous_completeness is not None else -1.0
    if prev < 0.85 <= completeness:
        return "设计条件较完整"
    if prev < 0.55 <= completeness:
        return "证据与任务理解推进"
    if prev < 0.30 <= completeness:
        return "从想法进入部分知识"
    if added_known_keys and not resolved_unknown:
        return f"新增已知：{'、'.join(added_known_keys[:3])}"
    if resolved_unknown:
        return f"消解未知：{'、'.join(resolved_unknown[:3])}"
    return ""


def _snapshot_summary(
    *,
    version_label: str,
    completeness: float,
    added: list[str],
    resolved: list[str],
    milestone: str,
) -> str:
    pct = int(round(completeness * 100))
    parts = [f"{version_label} · 完整度 {pct}%"]
    if milestone:
        parts.append(milestone)
    elif added:
        parts.append("+" + "、".join(added[:3]))
    elif resolved:
        parts.append("澄清 " + "、".join(resolved[:3]))
    return " · ".join(parts)

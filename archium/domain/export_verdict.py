"""Unified formal-export verdict — single partner-facing gate vocabulary."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ExportVerdictStatus(StrEnum):
    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ExportVerdict:
    """Studio + Deliver shared export decision (wraps readiness + critic + citations)."""

    status: ExportVerdictStatus
    blockers: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    critic_lines: tuple[str, ...] = field(default_factory=tuple)
    citation_gap_count: int = 0
    review_blocker_count: int = 0
    deck_qa_blocker_count: int = 0
    pptx_ready: bool = False
    pdf_ready: bool = False
    evidence_ok: bool = False
    round_trip_status: str | None = None
    # APP-004: which QA/evidence stacks fed this verdict (stacks produce evidence only).
    evidence_stacks: tuple[str, ...] = field(default_factory=tuple)

    @property
    def allows_formal_export(self) -> bool:
        return self.status != ExportVerdictStatus.BLOCKED

    def partner_summary(self) -> str:
        if self.status == ExportVerdictStatus.READY:
            return "可正式导出"
        if self.status == ExportVerdictStatus.READY_WITH_WARNINGS:
            return "可导出（有警告，建议复核）"
        first = self.blockers[0] if self.blockers else "存在阻塞项"
        return f"不可正式导出：{first}"

    def partner_lines(self, *, limit: int = 8) -> list[str]:
        lines: list[str] = [self.partner_summary()]
        for item in self.blockers[:limit]:
            lines.append(f"阻塞 · {item}")
        for item in self.warnings[: max(0, limit - len(lines))]:
            lines.append(f"警告 · {item}")
        for item in self.critic_lines[: max(0, limit - len(lines))]:
            lines.append(f"批判 · {item}")
        return lines

"""Architectural Design Critic — challenge ConceptDirection before it hardens.

Critic role Service: read-only report. Never rewrites the direction or Mission.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_critique import (
    DesignCritiqueChallenge,
    DesignCritiqueItem,
    DesignCritiqueReport,
    DesignCritiqueVerdict,
)
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.exceptions import WorkflowError
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.call import generate_structured as llm_generate_structured
from archium.infrastructure.llm.capabilities import LLMCapability
from archium.infrastructure.llm.design_critique_schemas import (
    DesignCritiqueDraft,
    DesignCritiqueItemDraft,
)
from archium.logging import get_logger
from archium.prompts.design_critique import (
    DESIGN_CRITIQUE_SYSTEM_PROMPT,
    build_design_critique_user_prompt,
)
from archium.prompts.design_critique import (
    PROMPT_VERSION as CRITIQUE_PROMPT_VERSION,
)

logger = get_logger(__name__, operation="design_critique")

_FORMAL_TOKENS = (
    "体量",
    "立面",
    "材质表情",
    "形式语言",
    "造型",
    "几何",
    "韵律",
    "雕塑感",
    "符号",
)
_PROBLEM_TOKENS = (
    "问题",
    "矛盾",
    "需求",
    "使用",
    "流线",
    "场地",
    "规范",
    "消防",
    "红线",
    "礼仪",
    "仪式",
    "社区",
    "功能",
)


@dataclass
class DesignCritiqueGateResult:
    """Outcome of critique + optional selection gate."""

    report: DesignCritiqueReport
    mode: str
    blocked: bool = False
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "blocked": self.blocked,
            "warnings": list(self.warnings),
            "report": self.report.as_dict(),
        }


class DesignCritiqueService:
    """Produce an independent DesignCritiqueReport (Critic seat, not an Agent)."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()

    def critique(
        self,
        direction: ConceptDirection,
        *,
        design_intent: DesignIntent | None = None,
        knowledge_state: KnowledgeState | None = None,
        research_summaries: list[str] | None = None,
    ) -> DesignCritiqueReport:
        """Critique a concept direction against intent + research context."""
        research_block = self._research_block(
            knowledge_state=knowledge_state,
            research_summaries=research_summaries,
        )
        intent_block = (
            design_intent.to_prompt_block()
            if design_intent is not None
            else ""
        )
        direction_block = direction.to_prompt_block()

        draft: DesignCritiqueDraft | None = None
        source = "rules"
        try:
            draft = llm_generate_structured(
                self._llm,
                LLMRequest(
                    system_prompt=DESIGN_CRITIQUE_SYSTEM_PROMPT,
                    user_prompt=build_design_critique_user_prompt(
                        direction_block=direction_block,
                        design_intent_block=intent_block,
                        research_block=research_block,
                    ),
                    temperature=0.25,
                    json_mode=True,
                    metadata={"prompt_version": CRITIQUE_PROMPT_VERSION},
                ),
                DesignCritiqueDraft,
                capability=LLMCapability.DESIGN_CRITIQUE,
                project_id=direction.project_id,
                session=self._session,
                settings=self._settings,
            )
            source = "llm"
        except Exception as exc:  # noqa: BLE001 — critic must degrade, not abort select
            logger.warning("design critique LLM failed, using rules: %s", exc)
            draft = None

        try:
            report = self._from_draft(
                draft,
                direction=direction,
                source=source,
            )
        except Exception as exc:  # noqa: BLE001 — malformed draft must not abort select
            logger.warning("design critique draft invalid, using rules: %s", exc)
            report = self._from_draft(
                None,
                direction=direction,
                source="rules",
            )
        report = self._merge_rule_signals(
            report,
            direction=direction,
            design_intent=design_intent,
            research_block=research_block,
        )
        report.touch_completed()
        return report

    def enforce_on_select(
        self,
        direction: ConceptDirection,
        *,
        design_intent: DesignIntent | None = None,
        knowledge_state: KnowledgeState | None = None,
        research_summaries: list[str] | None = None,
        force: bool = False,
    ) -> DesignCritiqueGateResult:
        """Run critique and apply ``design_critique_on_select`` gate policy.

        Modes: off | warn | block (default warn).
        """
        mode = (self._settings.design_critique_on_select or "warn").strip().lower()
        if mode not in {"off", "warn", "block"}:
            mode = "warn"

        if mode == "off":
            empty = DesignCritiqueReport(
                direction_id=direction.id,
                project_id=direction.project_id,
                verdict=DesignCritiqueVerdict.PROCEED,
                summary="设计批判闸门关闭",
                source="rules",
            )
            return DesignCritiqueGateResult(report=empty, mode=mode)

        report = self.critique(
            direction,
            design_intent=design_intent,
            knowledge_state=knowledge_state,
            research_summaries=research_summaries,
        )
        warnings = report.display_warnings()
        result = DesignCritiqueGateResult(
            report=report,
            mode=mode,
            warnings=warnings,
        )

        if force:
            result.warnings.append("已强制跳过设计批判阻断（force）。")
            return result

        if mode == "block" and report.blocks_selection:
            result.blocked = True
            detail = report.summary or "设计批判判定不宜固化该方向"
            raise WorkflowError(
                f"设计批判阻断选定方向：{detail}。"
                "请补充证据、调整方向，或设置 DESIGN_CRITIQUE_ON_SELECT=warn。"
            )
        return result

    def _from_draft(
        self,
        draft: DesignCritiqueDraft | None,
        *,
        direction: ConceptDirection,
        source: str,
    ) -> DesignCritiqueReport:
        if draft is None:
            return DesignCritiqueReport(
                direction_id=direction.id,
                project_id=direction.project_id,
                verdict=DesignCritiqueVerdict.CAUTION,
                summary="未能完成模型批判，已退回规则检查",
                source="rules",
            )
        return DesignCritiqueReport(
            direction_id=direction.id,
            project_id=direction.project_id,
            verdict=_parse_verdict(draft.verdict),
            summary=(draft.summary or "").strip(),
            strengths=[_item_from_draft(i) for i in draft.strengths if i.text.strip()],
            weaknesses=[_item_from_draft(i) for i in draft.weaknesses if i.text.strip()],
            missing_evidence=[
                _item_from_draft(i) for i in draft.missing_evidence if i.text.strip()
            ],
            alternative_directions=[
                _item_from_draft(i)
                for i in draft.alternative_directions
                if i.text.strip()
            ],
            form_only_risk=bool(draft.form_only_risk),
            source=source,
        )

    def _merge_rule_signals(
        self,
        report: DesignCritiqueReport,
        *,
        direction: ConceptDirection,
        design_intent: DesignIntent | None,
        research_block: str,
    ) -> DesignCritiqueReport:
        """Deterministic challenges that LLM must not soft-pedal away."""
        weaknesses = list(report.weaknesses)
        missing = list(report.missing_evidence)
        alternatives = list(report.alternative_directions)
        form_only = report.form_only_risk
        source = report.source

        rationale = direction.design_rationale
        evidence_bits: list[str] = []
        if rationale is not None:
            evidence_bits.extend(rationale.evidence or [])
        if design_intent is not None:
            evidence_bits.extend(
                e.statement for e in (design_intent.evidence or []) if e.statement.strip()
            )
            if design_intent.design_rationale is not None:
                evidence_bits.extend(design_intent.design_rationale.evidence or [])

        if not any(bit.strip() for bit in evidence_bits):
            missing.append(
                DesignCritiqueItem(
                    text="方向缺少可核验依据（场地/规范/先例/调研），固化前应补研究或事实",
                    challenge=DesignCritiqueChallenge.EVIDENCE,
                    severity="high",
                )
            )
            source = "mixed" if source == "llm" else "rules"

        if not research_block.strip() or research_block.strip().startswith("（"):
            missing.append(
                DesignCritiqueItem(
                    text="尚无研究/知识摘要输入批判；公开研究或项目资料未进入论证链",
                    challenge=DesignCritiqueChallenge.EVIDENCE,
                    severity="medium",
                )
            )
            source = "mixed" if source == "llm" else "rules"

        problem = ""
        if design_intent is not None:
            problem = (design_intent.problem_statement or "").strip()
        blob = " ".join(
            part
            for part in (
                direction.summary,
                direction.spatial_strategy,
                direction.formal_language,
                direction.experience_focus,
                (rationale.statement if rationale else ""),
            )
            if part and str(part).strip()
        )
        formal_hits = sum(1 for token in _FORMAL_TOKENS if token in blob)
        problem_hits = sum(1 for token in _PROBLEM_TOKENS if token in blob)
        if formal_hits >= 2 and problem_hits == 0 and not problem:
            form_only = True
            weaknesses.append(
                DesignCritiqueItem(
                    text="表述偏重形式语言，未见清晰问题陈述或使用/场地矛盾回应",
                    challenge=DesignCritiqueChallenge.FORM_ONLY,
                    severity="high",
                )
            )
            source = "mixed" if source == "llm" else "rules"

        if not alternatives:
            alternatives.append(
                DesignCritiqueItem(
                    text="可并行推演一条更偏问题驱动的方向（先定使用/礼仪/流线矛盾，再定形式）",
                    challenge=DesignCritiqueChallenge.ALTERNATIVE,
                    severity="suggestion",
                )
            )
            source = "mixed" if source == "llm" else "rules"

        verdict = report.verdict
        high_gaps = [
            item
            for item in missing + weaknesses
            if item.severity in {"critical", "high"}
        ]
        if form_only and len(high_gaps) >= 2:
            verdict = DesignCritiqueVerdict.REJECT
        elif high_gaps and verdict == DesignCritiqueVerdict.PROCEED:
            verdict = DesignCritiqueVerdict.CAUTION

        summary = report.summary
        if not summary.strip():
            if verdict == DesignCritiqueVerdict.REJECT:
                summary = "批判结论：证据与问题匹配不足，不建议立即固化该方向"
            elif verdict == DesignCritiqueVerdict.CAUTION:
                summary = "批判结论：可继续，但需正视弱点与缺证"
            else:
                summary = "批判结论：可继续选定"

        return report.model_copy(
            update={
                "weaknesses": _dedupe_items(weaknesses)[:8],
                "missing_evidence": _dedupe_items(missing)[:8],
                "alternative_directions": _dedupe_items(alternatives)[:6],
                "form_only_risk": form_only,
                "verdict": verdict,
                "summary": summary,
                "source": source,
            }
        )

    def _research_block(
        self,
        *,
        knowledge_state: KnowledgeState | None,
        research_summaries: list[str] | None,
    ) -> str:
        lines: list[str] = []
        if research_summaries:
            for item in research_summaries[:8]:
                text = (item or "").strip()
                if text:
                    lines.append(f"- {text[:300]}")
        if knowledge_state is not None:
            known = knowledge_state.known or {}
            for key, value in list(known.items())[:8]:
                if str(value).strip():
                    lines.append(f"- 已知 {key}：{str(value).strip()[:200]}")
            for gap in (knowledge_state.unknown or [])[:5]:
                if str(gap).strip():
                    lines.append(f"- 未知：{str(gap).strip()[:200]}")
            for unknown_ref in (knowledge_state.open_unknowns or [])[:5]:
                if unknown_ref.description.strip():
                    prefix = "阻断未知" if unknown_ref.blocking else "未知"
                    lines.append(f"- {prefix}：{unknown_ref.description.strip()[:200]}")
        if not lines:
            return "（暂无研究摘要）"
        return "\n".join(lines)


def _parse_verdict(raw: str) -> DesignCritiqueVerdict:
    key = (raw or "").strip().lower()
    try:
        return DesignCritiqueVerdict(key)
    except ValueError:
        return DesignCritiqueVerdict.CAUTION


def _parse_challenge(raw: str) -> DesignCritiqueChallenge:
    key = (raw or "").strip().lower()
    try:
        return DesignCritiqueChallenge(key)
    except ValueError:
        return DesignCritiqueChallenge.WHY


def _item_from_draft(draft: DesignCritiqueItemDraft) -> DesignCritiqueItem:
    severity = (draft.severity or "suggestion").strip().lower()
    if severity not in {"critical", "high", "medium", "suggestion"}:
        severity = "suggestion"
    return DesignCritiqueItem(
        text=draft.text.strip()[:500],
        challenge=_parse_challenge(draft.challenge),
        severity=severity,
    )


def _dedupe_items(items: list[DesignCritiqueItem]) -> list[DesignCritiqueItem]:
    seen: set[str] = set()
    out: list[DesignCritiqueItem] = []
    for item in items:
        key = item.text.strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out

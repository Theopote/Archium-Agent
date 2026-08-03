"""Research Critic — challenge research findings before they harden as knowledge.

Critic seat Service: read-only report. Never rewrites ProjectKnowledgeItem text.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.config.settings import Settings, get_settings
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.domain.research_critique import (
    ResearchCritiqueIssue,
    ResearchCritiqueIssueKind,
    ResearchCritiqueReport,
    ResearchCritiqueVerdict,
)
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.call import generate_structured as llm_generate_structured
from archium.infrastructure.llm.capabilities import LLMCapability
from archium.infrastructure.llm.research_critique_schemas import ResearchCritiqueDraft
from archium.logging import get_logger
from archium.prompts.research_critique import (
    PROMPT_VERSION as RESEARCH_CRITIQUE_PROMPT_VERSION,
)
from archium.prompts.research_critique import (
    RESEARCH_CRITIQUE_SYSTEM_PROMPT,
    build_research_critique_user_prompt,
)

logger = get_logger(__name__, operation="research_critique")

_BACKGROUND_TOKENS = ("背景", "综述", "简介", "概述", "介绍", "概况")
_OVER_ANALOGY_TOKENS = (
    "完全适用",
    "直接照搬",
    "一模一样",
    "必须采用",
    "唯一正确",
    "照抄",
)


class ResearchCritiqueService:
    """Produce ResearchCritiqueReport for autonomous research batches."""

    def __init__(
        self,
        session: SessionLike,
        llm: LLMProvider | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        session = session_of(session)
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()

    def critique_items(
        self,
        items: list[ProjectKnowledgeItem],
        *,
        project_id: UUID | None = None,
        mission_id: UUID | None = None,
        design_context: str = "",
        use_llm: bool = True,
    ) -> ResearchCritiqueReport:
        mode = (getattr(self._settings, "research_critique_mode", None) or "warn").strip().lower()
        if mode == "off":
            return ResearchCritiqueReport(
                project_id=project_id,
                mission_id=mission_id,
                validity=1.0,
                design_relevance=1.0,
                verdict=ResearchCritiqueVerdict.ACCEPT,
                summary="研究批判闸门关闭",
                source="rules",
                item_count=len(items),
            )

        report = self._rules_critique(
            items,
            project_id=project_id,
            mission_id=mission_id,
        )
        if use_llm and self._llm is not None and items:
            llm_report = self._llm_critique(
                items,
                design_context=design_context,
                project_id=project_id,
                mission_id=mission_id,
            )
            if llm_report is not None:
                report = self._merge(report, llm_report)

        report.touch_completed()
        return report

    def _rules_critique(
        self,
        items: list[ProjectKnowledgeItem],
        *,
        project_id: UUID | None,
        mission_id: UUID | None,
    ) -> ResearchCritiqueReport:
        if not items:
            return ResearchCritiqueReport(
                project_id=project_id,
                mission_id=mission_id,
                validity=0.2,
                design_relevance=0.1,
                verdict=ResearchCritiqueVerdict.WEAK,
                summary="无研究产物可批判",
                warnings=["研究批量为空"],
                issues=[
                    ResearchCritiqueIssue(
                        text="未产出知识条目，无法支撑设计",
                        kind=ResearchCritiqueIssueKind.LOW_DESIGN_RELEVANCE,
                        severity="high",
                    )
                ],
                source="rules",
                item_count=0,
            )

        issues: list[ResearchCritiqueIssue] = []
        strengths: list[str] = []
        cited = 0
        structured = 0
        backgroundish = 0
        over_analogy = 0

        for item in items:
            has_cite = bool(item.source_citations)
            if has_cite:
                cited += 1
                strengths.append(f"含引用：{(item.statement or '')[:40]}")
            else:
                issues.append(
                    ResearchCritiqueIssue(
                        text=f"条目缺少可核验来源：{(item.statement or '')[:80]}",
                        kind=ResearchCritiqueIssueKind.WEAK_CITATION,
                        severity="high",
                    )
                )

            knowledge = item.design_knowledge
            if knowledge is not None and knowledge.has_substance:
                structured += 1
                if knowledge.principle.strip() and knowledge.spatial_translation.strip():
                    strengths.append(
                        f"结构化知识：{knowledge.principle[:40]}"
                    )
            else:
                issues.append(
                    ResearchCritiqueIssue(
                        text="缺少 DesignKnowledge（原则/空间转译），偏背景摘要",
                        kind=ResearchCritiqueIssueKind.MISSING_STRUCTURE,
                        severity="medium",
                    )
                )

            blob = " ".join(
                part
                for part in (
                    item.statement or "",
                    knowledge.to_prompt_block() if knowledge else "",
                )
                if part
            )
            if self._looks_background_only(blob, knowledge):
                backgroundish += 1
                issues.append(
                    ResearchCritiqueIssue(
                        text="表述偏背景综述，未见对当前设计问题的转化",
                        kind=ResearchCritiqueIssueKind.BACKGROUND_ONLY,
                        severity="medium",
                    )
                )
            if any(token in blob for token in _OVER_ANALOGY_TOKENS):
                over_analogy += 1
                issues.append(
                    ResearchCritiqueIssue(
                        text="存在过度类比措辞（完全适用/照搬等），需降级为可讨论原则",
                        kind=ResearchCritiqueIssueKind.OVER_ANALOGY,
                        severity="high",
                    )
                )
            elif knowledge is not None and knowledge.principle.strip() and not (
                knowledge.applicability or ""
            ).strip():
                issues.append(
                    ResearchCritiqueIssue(
                        text="有原则但未写适用边界，跨项目迁移风险偏高",
                        kind=ResearchCritiqueIssueKind.OVER_ANALOGY,
                        severity="suggestion",
                    )
                )

        n = max(1, len(items))
        validity = 0.35 + 0.55 * (cited / n) + 0.1 * (structured / n)
        design_relevance = (
            0.25
            + 0.45 * (structured / n)
            + 0.2 * max(0.0, 1.0 - backgroundish / n)
            - 0.15 * min(1.0, over_analogy / n)
        )
        validity = max(0.0, min(1.0, validity))
        design_relevance = max(0.0, min(1.0, design_relevance))
        verdict = self._verdict(validity, design_relevance)
        summary = self._summary(verdict, validity, design_relevance)
        warnings = [
            issue.text
            for issue in issues
            if issue.severity in {"critical", "high"}
        ][:5]

        return ResearchCritiqueReport(
            project_id=project_id,
            mission_id=mission_id,
            validity=round(validity, 3),
            design_relevance=round(design_relevance, 3),
            verdict=verdict,
            summary=summary,
            warnings=warnings,
            issues=_dedupe_issues(issues)[:10],
            strengths=_dedupe_strings(strengths)[:5],
            source="rules",
            item_count=len(items),
        )

    def _llm_critique(
        self,
        items: list[ProjectKnowledgeItem],
        *,
        design_context: str,
        project_id: UUID | None,
        mission_id: UUID | None,
    ) -> ResearchCritiqueReport | None:
        assert self._llm is not None
        findings_block = self._findings_block(items)
        try:
            draft = llm_generate_structured(
                self._llm,
                LLMRequest(
                    system_prompt=RESEARCH_CRITIQUE_SYSTEM_PROMPT,
                    user_prompt=build_research_critique_user_prompt(
                        design_context=design_context,
                        findings_block=findings_block,
                    ),
                    temperature=0.2,
                    json_mode=True,
                    metadata={"prompt_version": RESEARCH_CRITIQUE_PROMPT_VERSION},
                ),
                ResearchCritiqueDraft,
                capability=LLMCapability.DESIGN_CRITIQUE,
                project_id=project_id,
                session=self._session,
                settings=self._settings,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("research critique LLM failed: %s", exc)
            return None

        try:
            return self._from_draft(
                draft,
                project_id=project_id,
                mission_id=mission_id,
                item_count=len(items),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("research critique draft invalid: %s", exc)
            return None

    def _from_draft(
        self,
        draft: ResearchCritiqueDraft,
        *,
        project_id: UUID | None,
        mission_id: UUID | None,
        item_count: int,
    ) -> ResearchCritiqueReport:
        issues = [
            ResearchCritiqueIssue(
                text=item.text.strip(),
                kind=_parse_kind(item.kind),
                severity=(item.severity or "medium").strip() or "medium",
            )
            for item in draft.issues
            if item.text.strip()
        ]
        validity = float(draft.validity)
        design_relevance = float(draft.design_relevance)
        verdict = _parse_verdict(draft.verdict, validity, design_relevance)
        return ResearchCritiqueReport(
            project_id=project_id,
            mission_id=mission_id,
            validity=round(validity, 3),
            design_relevance=round(design_relevance, 3),
            verdict=verdict,
            summary=(draft.summary or "").strip(),
            warnings=[w.strip() for w in draft.warnings if w.strip()][:8],
            issues=issues[:10],
            strengths=[s.strip() for s in draft.strengths if s.strip()][:5],
            source="llm",
            item_count=item_count,
        )

    def _merge(
        self,
        rules: ResearchCritiqueReport,
        llm: ResearchCritiqueReport,
    ) -> ResearchCritiqueReport:
        validity = min(rules.validity, llm.validity) * 0.35 + (
            (rules.validity + llm.validity) / 2
        ) * 0.65
        # Prefer the more skeptical design_relevance
        design_relevance = min(rules.design_relevance, llm.design_relevance)
        issues = _dedupe_issues(list(rules.issues) + list(llm.issues))[:10]
        warnings = _dedupe_strings(list(rules.warnings) + list(llm.warnings))[:8]
        strengths = _dedupe_strings(list(rules.strengths) + list(llm.strengths))[:5]
        verdict = self._verdict(validity, design_relevance)
        summary = (llm.summary or rules.summary).strip() or self._summary(
            verdict, validity, design_relevance
        )
        return ResearchCritiqueReport(
            project_id=rules.project_id or llm.project_id,
            mission_id=rules.mission_id or llm.mission_id,
            validity=round(validity, 3),
            design_relevance=round(design_relevance, 3),
            verdict=verdict,
            summary=summary,
            warnings=warnings,
            issues=issues,
            strengths=strengths,
            source="mixed",
            item_count=max(rules.item_count, llm.item_count),
        )

    @staticmethod
    def _looks_background_only(
        blob: str,
        knowledge: DesignKnowledge | None,
    ) -> bool:
        if knowledge is not None and knowledge.principle.strip() and (
            knowledge.spatial_translation.strip() or knowledge.project_link.strip()
        ):
            return False
        hits = sum(1 for token in _BACKGROUND_TOKENS if token in blob)
        return hits >= 2 or (
            hits >= 1
            and (knowledge is None or not knowledge.has_substance)
        )

    @staticmethod
    def _verdict(validity: float, design_relevance: float) -> ResearchCritiqueVerdict:
        if validity >= 0.7 and design_relevance >= 0.65:
            return ResearchCritiqueVerdict.ACCEPT
        if validity < 0.45 or design_relevance < 0.4:
            return ResearchCritiqueVerdict.WEAK
        return ResearchCritiqueVerdict.CAUTION

    @staticmethod
    def _summary(
        verdict: ResearchCritiqueVerdict,
        validity: float,
        design_relevance: float,
    ) -> str:
        return (
            f"研究批判：{verdict.value} "
            f"（validity={validity:.2f}, design_relevance={design_relevance:.2f}）"
        )

    @staticmethod
    def _findings_block(items: list[ProjectKnowledgeItem]) -> str:
        parts: list[str] = []
        for index, item in enumerate(items[:8], start=1):
            cites = ", ".join(
                (c.source_title or c.url or "")[:80]
                for c in item.source_citations[:3]
            )
            dk = ""
            if item.design_knowledge is not None:
                dk = item.design_knowledge.to_prompt_block()
            parts.append(
                f"[{index}]\n{item.statement[:500]}\n"
                f"citations: {cites or '（无）'}\n"
                f"{dk}"
            )
        return "\n\n".join(parts)


def _parse_kind(raw: str) -> ResearchCritiqueIssueKind:
    value = (raw or "").strip().lower()
    try:
        return ResearchCritiqueIssueKind(value)
    except ValueError:
        return ResearchCritiqueIssueKind.OTHER


def _parse_verdict(
    raw: str,
    validity: float,
    design_relevance: float,
) -> ResearchCritiqueVerdict:
    value = (raw or "").strip().lower()
    if value in {"accept", "proceed", "ok"}:
        return ResearchCritiqueVerdict.ACCEPT
    if value in {"weak", "reject", "fail"}:
        return ResearchCritiqueVerdict.WEAK
    if value in {"caution", "warn"}:
        return ResearchCritiqueVerdict.CAUTION
    return ResearchCritiqueService._verdict(validity, design_relevance)


def _dedupe_issues(issues: list[ResearchCritiqueIssue]) -> list[ResearchCritiqueIssue]:
    seen: set[str] = set()
    out: list[ResearchCritiqueIssue] = []
    for item in issues:
        key = f"{item.kind.value}:{item.text.strip()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out

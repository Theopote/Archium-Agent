"""Decompose DesignIntent / KnowledgeState into ResearchQuestion objects.

Deterministic (no LLM): turns “搜文化中心案例” style gaps into problem-framed
questions architects actually research. Not a ResearchAgent.
"""

from __future__ import annotations

import re
from uuid import UUID

from archium.domain.intent.design_intent import DesignIntent
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.project_mission import ProjectMission
from archium.domain.research_question import (
    ResearchQuestion,
    ResearchQuestionCategory,
    ResearchQuestionDepth,
    ResearchQuestionStatus,
)

_CASE_DUMP = re.compile(
    r"(案例|先例|参考项目|类似项目|同类项目)",
    re.IGNORECASE,
)
_WHY_OR_HOW = re.compile(r"(为什么|如何|怎样|怎么|是否|能否|什么问题|何种)")


class ResearchQuestionService:
    """Build ranked ResearchQuestion lists from mission + cognition state."""

    def decompose_mission(
        self,
        mission: ProjectMission,
        *,
        knowledge_state: KnowledgeState | None = None,
        max_questions: int = 8,
    ) -> list[ResearchQuestion]:
        questions: list[ResearchQuestion] = []
        intent = mission.design_intent

        if intent is not None:
            questions.extend(
                self._from_design_intent(
                    intent,
                    project_id=mission.project_id,
                    mission_id=mission.id,
                )
            )
        for raw in mission.research_questions:
            text = (raw or "").strip()
            if not text:
                continue
            questions.append(
                self._normalize_raw(
                    text,
                    source="mission.research_questions",
                    project_id=mission.project_id,
                    mission_id=mission.id,
                    base_priority=0.55,
                )
            )

        if knowledge_state is not None:
            questions.extend(
                self._from_knowledge_state(
                    knowledge_state,
                    project_id=mission.project_id,
                    mission_id=mission.id,
                )
            )

        return self._dedupe_rank(questions, max_questions=max_questions)

    def decompose_project(
        self,
        *,
        project_id: UUID,
        project_name: str = "",
        project_description: str = "",
        knowledge_state: KnowledgeState | None = None,
        max_questions: int = 6,
    ) -> list[ResearchQuestion]:
        questions: list[ResearchQuestion] = []
        if knowledge_state is not None:
            questions.extend(
                self._from_knowledge_state(
                    knowledge_state,
                    project_id=project_id,
                    mission_id=None,
                )
            )
        seed = " ".join(
            part.strip()
            for part in (project_name, project_description)
            if part and str(part).strip()
        )
        if seed and not questions:
            questions.append(
                ResearchQuestion(
                    question=self._problem_frame(
                        f"{seed}需要回应哪些社会与空间问题？"
                    ),
                    category=ResearchQuestionCategory.ARCHITECTURAL,
                    related_intent=seed[:120],
                    priority=0.5,
                    source="project.seed",
                    rationale="尚无 Mission，从项目名称/描述生成问题入口",
                    project_id=project_id,
                )
            )
        return self._dedupe_rank(questions, max_questions=max_questions)

    def _from_design_intent(
        self,
        intent: DesignIntent,
        *,
        project_id: UUID,
        mission_id: UUID,
    ) -> list[ResearchQuestion]:
        out: list[ResearchQuestion] = []
        problem = (intent.problem_statement or "").strip()
        if problem:
            out.append(
                ResearchQuestion(
                    question=self._problem_frame(
                        problem
                        if _WHY_OR_HOW.search(problem)
                        else f"如何用建筑回应：{problem}？"
                    ),
                    category=ResearchQuestionCategory.ARCHITECTURAL,
                    related_intent=problem[:200],
                    priority=0.92,
                    required_depth=ResearchQuestionDepth.DEEP,
                    source="design_intent.problem_statement",
                    rationale="核心问题陈述 → 首要研究问题",
                    project_id=project_id,
                    mission_id=mission_id,
                )
            )
        social = (intent.social_background or "").strip()
        if social:
            out.append(
                ResearchQuestion(
                    question=self._problem_frame(
                        f"当前社会背景下，{social}如何影响公共空间与建筑需求？"
                    ),
                    category=ResearchQuestionCategory.SOCIAL,
                    related_intent=social[:200],
                    priority=0.85,
                    source="design_intent.social_background",
                    rationale="社会背景 → 社会维度研究",
                    project_id=project_id,
                    mission_id=mission_id,
                )
            )
        cultural = (intent.cultural_context or "").strip()
        if cultural:
            out.append(
                ResearchQuestion(
                    question=self._problem_frame(
                        f"{cultural}中有哪些可迁移的空间组织与表达原则？"
                    ),
                    category=ResearchQuestionCategory.CULTURAL,
                    related_intent=cultural[:200],
                    priority=0.8,
                    source="design_intent.cultural_context",
                    rationale="文化语境 → 文化维度研究",
                    project_id=project_id,
                    mission_id=mission_id,
                )
            )
        for user in intent.target_users or []:
            label = (user or "").strip()
            if not label:
                continue
            out.append(
                ResearchQuestion(
                    question=self._problem_frame(
                        f"{label}在场地中缺少哪些行为支持与停留空间？"
                    ),
                    category=ResearchQuestionCategory.BEHAVIORAL,
                    related_intent=label,
                    priority=0.72,
                    source="design_intent.target_users",
                    rationale="使用者 → 行为维度研究",
                    project_id=project_id,
                    mission_id=mission_id,
                )
            )
        for needed in intent.research_needed or []:
            text = (needed or "").strip()
            if not text:
                continue
            out.append(
                self._normalize_raw(
                    text,
                    source="design_intent.research_needed",
                    project_id=project_id,
                    mission_id=mission_id,
                    base_priority=0.88,
                    related_intent=(intent.theme or "")[:120],
                )
            )
        return out

    def _from_knowledge_state(
        self,
        state: KnowledgeState,
        *,
        project_id: UUID,
        mission_id: UUID | None,
    ) -> list[ResearchQuestion]:
        out: list[ResearchQuestion] = []
        research_need = float(state.effective_dimensions().research_need)
        for gap in state.open_unknowns:
            label = (gap.description or "").strip()
            if not label:
                continue
            out.append(
                self._normalize_raw(
                    label,
                    source="knowledge_state.open_unknowns",
                    project_id=project_id,
                    mission_id=mission_id,
                    base_priority=min(0.9, 0.55 + research_need * 0.35 + (0.1 if gap.blocking else 0.0)),
                )
            )
        for item in list(state.unknown or []) + list(state.missing_information or []):
            text = (item or "").strip()
            if not text:
                continue
            out.append(
                self._normalize_raw(
                    text,
                    source="knowledge_state.gap",
                    project_id=project_id,
                    mission_id=mission_id,
                    base_priority=min(0.85, 0.5 + research_need * 0.3),
                )
            )
        return out

    def _normalize_raw(
        self,
        text: str,
        *,
        source: str,
        project_id: UUID,
        mission_id: UUID | None,
        base_priority: float,
        related_intent: str = "",
    ) -> ResearchQuestion:
        category = self._infer_category(text)
        framed = self._rewrite_case_dump(text) if _CASE_DUMP.search(text) else text
        framed = self._problem_frame(framed)
        depth = ResearchQuestionDepth.STANDARD
        if category in {
            ResearchQuestionCategory.TECHNICAL,
            ResearchQuestionCategory.ENVIRONMENTAL,
        }:
            depth = ResearchQuestionDepth.DEEP
        return ResearchQuestion(
            question=framed,
            category=category,
            related_intent=related_intent or text[:160],
            priority=min(1.0, base_priority),
            required_depth=depth,
            status=ResearchQuestionStatus.OPEN,
            source=source,
            rationale="由缺口/意图规范化为问题表述",
            project_id=project_id,
            mission_id=mission_id,
        )

    @staticmethod
    def _rewrite_case_dump(text: str) -> str:
        core = _CASE_DUMP.sub("", text).strip(" ：:，,")
        core = core or text.strip()
        return (
            f"{core}如何解决具体使用/场地矛盾？"
            f"有哪些可迁移的空间组织原则，是否适用于当前项目？"
        )

    @staticmethod
    def _problem_frame(text: str) -> str:
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            return "当前项目应优先研究什么设计问题？"
        if _WHY_OR_HOW.search(cleaned):
            return cleaned if cleaned.endswith(("？", "?")) else f"{cleaned}？"
        if cleaned.endswith(("？", "?")):
            return cleaned
        return f"{cleaned}——关键设计问题与可迁移原则是什么？"

    @staticmethod
    def _infer_category(text: str) -> ResearchQuestionCategory:
        blob = text.lower()
        rules: tuple[tuple[tuple[str, ...], ResearchQuestionCategory], ...] = (
            (("社会", "社区", "人口", "老龄化", "公共性"), ResearchQuestionCategory.SOCIAL),
            (("文化", "礼仪", "民俗", "遗产", "地域"), ResearchQuestionCategory.CULTURAL),
            (("历史", "沿革", "文物", "修缮史"), ResearchQuestionCategory.HISTORICAL),
            (("气候", "生态", "碳", "环境", "地形", "山地"), ResearchQuestionCategory.ENVIRONMENTAL),
            (("流线", "行为", "使用", "访客", "停留"), ResearchQuestionCategory.BEHAVIORAL),
            (("投资", "运营", "成本", "经济"), ResearchQuestionCategory.ECONOMIC),
            (("规范", "消防", "结构", "红线", "指标"), ResearchQuestionCategory.TECHNICAL),
        )
        for tokens, category in rules:
            if any(token in blob for token in tokens):
                return category
        return ResearchQuestionCategory.ARCHITECTURAL

    @staticmethod
    def _dedupe_rank(
        questions: list[ResearchQuestion],
        *,
        max_questions: int,
    ) -> list[ResearchQuestion]:
        seen: set[str] = set()
        ranked = sorted(questions, key=lambda q: q.priority, reverse=True)
        out: list[ResearchQuestion] = []
        for item in ranked:
            key = re.sub(r"\s+", "", item.question)[:80]
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= max_questions:
                break
        return out

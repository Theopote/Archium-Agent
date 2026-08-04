"""Semantic-ish architecture case retrieval (tag/problem overlap — not embeddings).

Cross-type migration example: 「冥想」→ Therme Vals / Bruder Klaus, not only
buildings literally named meditation spaces.

Phase B: optional session + project_id merges writable project cases over seeds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from archium.application.unit_of_work import SessionLike, session_of
from archium.domain.architecture_case import ArchitectureCase
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import ArchitectureCaseStatus
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.research_question import ResearchQuestion
from archium.infrastructure.research.case_library.seeds import all_seed_cases

_TOKEN_SPLIT = re.compile(r"[\s,，、；;|/＋+]+")


@dataclass(frozen=True)
class ArchitectureCaseMatch:
    case: ArchitectureCase
    score: float
    matched_terms: tuple[str, ...] = ()


def merge_seed_and_project_cases(
    *,
    seeds: list[ArchitectureCase],
    project_cases: list[ArchitectureCase],
) -> list[ArchitectureCase]:
    """Project cases override seeds with the same slug."""
    by_id: dict[str, ArchitectureCase] = {case.id: case for case in seeds}
    for case in project_cases:
        by_id[case.id] = case
    # Stable order: seeds first (overridden in place), then project-only
    seed_ids = {case.id for case in seeds}
    ordered: list[ArchitectureCase] = [by_id[case.id] for case in seeds]
    for case in project_cases:
        if case.id not in seed_ids:
            ordered.append(case)
    return ordered


class ArchitectureCaseLibraryService:
    """Retrieve transferable cases for research / concept prompts."""

    def __init__(
        self,
        cases: list[ArchitectureCase] | None = None,
        *,
        session: SessionLike | None = None,
        project_id: UUID | None = None,
        include_drafts: bool = False,
    ) -> None:
        session = session_of(session)
        if cases is not None:
            self._cases = list(cases)
            return
        seeds = all_seed_cases()
        project_cases: list[ArchitectureCase] = []
        if session is not None and project_id is not None:
            from archium.infrastructure.database.repositories import (
                ArchitectureCaseRepository,
            )

            statuses = [ArchitectureCaseStatus.ACTIVE]
            if include_drafts:
                statuses.append(ArchitectureCaseStatus.DRAFT)
            stored = ArchitectureCaseRepository(session).list_by_project(
                project_id, statuses=statuses
            )
            project_cases = [row.to_architecture_case() for row in stored]
        self._cases = merge_seed_and_project_cases(
            seeds=seeds, project_cases=project_cases
        )

    def list_cases(self) -> list[ArchitectureCase]:
        return list(self._cases)

    def get_by_id(self, case_id: str) -> ArchitectureCase | None:
        from archium.domain.case_ref import normalize_case_id

        normalized = normalize_case_id(case_id)
        if normalized is None:
            return None
        for case in self._cases:
            if case.id == normalized:
                return case
        return None

    def resolve_ids(self, case_ids: list[str]) -> list[ArchitectureCase]:
        """Resolve bare / case: ids to ArchitectureCase (skip unknowns)."""
        out: list[ArchitectureCase] = []
        seen: set[str] = set()
        for raw in case_ids:
            case = self.get_by_id(raw)
            if case is None or case.id in seen:
                continue
            seen.add(case.id)
            out.append(case)
        return out

    def search(
        self,
        query: str,
        *,
        limit: int = 3,
        min_score: float = 0.35,
    ) -> list[ArchitectureCaseMatch]:
        tokens = self._tokenize(query)
        if not tokens:
            return []
        ranked: list[ArchitectureCaseMatch] = []
        for case in self._cases:
            score, hits = self._score_case(case, tokens)
            if score < min_score:
                continue
            ranked.append(
                ArchitectureCaseMatch(
                    case=case,
                    score=score,
                    matched_terms=tuple(hits),
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[: max(1, limit)]

    def search_for_intent(
        self,
        intent: DesignIntent | None,
        *,
        extra_queries: list[str] | None = None,
        limit: int = 3,
    ) -> list[ArchitectureCaseMatch]:
        parts: list[str] = []
        if intent is not None:
            parts.extend(
                [
                    intent.theme or "",
                    intent.problem_statement or "",
                    intent.social_background or "",
                    intent.cultural_context or "",
                    intent.desired_experience or "",
                    " ".join(intent.target_users or []),
                    " ".join(intent.research_needed or []),
                ]
            )
        if extra_queries:
            parts.extend(extra_queries)
        return self.search(" ".join(parts), limit=limit)

    def search_for_questions(
        self,
        questions: list[ResearchQuestion],
        *,
        limit: int = 3,
    ) -> list[ArchitectureCaseMatch]:
        blob = " ".join(q.question for q in questions if q.question.strip())
        return self.search(blob, limit=limit)

    def as_design_knowledge(
        self,
        matches: list[ArchitectureCaseMatch],
    ) -> list[DesignKnowledge]:
        return [match.case.to_design_knowledge() for match in matches]

    def format_prompt_block(
        self,
        matches: list[ArchitectureCaseMatch],
        *,
        title: str = "【建筑案例语义参照 ArchitectureCase】（跨类型迁移原则，勿抄袭造型）",
    ) -> str:
        if not matches:
            return ""
        parts = [title]
        for index, match in enumerate(matches, start=1):
            hit = "、".join(match.matched_terms[:6])
            header = f"[{index}] score={match.score:.2f}"
            if hit:
                header += f" · 命中：{hit}"
            parts.append(f"{header}\n{match.case.to_prompt_block()}")
        return "\n\n".join(parts)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        raw = (text or "").strip().casefold()
        if not raw:
            return []
        # Keep CJK bigrams + latin words for lightweight overlap.
        tokens: list[str] = []
        for part in _TOKEN_SPLIT.split(raw):
            part = part.strip()
            if len(part) >= 2:
                tokens.append(part)
        # Character bigrams for Chinese phrases without spaces
        compact = re.sub(r"\s+", "", raw)
        if re.search(r"[\u4e00-\u9fff]", compact):
            for i in range(len(compact) - 1):
                gram = compact[i : i + 2]
                if re.search(r"[\u4e00-\u9fff]", gram):
                    tokens.append(gram)
        # Dedupe preserve order
        seen: set[str] = set()
        out: list[str] = []
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            out.append(token)
        return out[:80]

    @staticmethod
    def _score_case(
        case: ArchitectureCase,
        tokens: list[str],
    ) -> tuple[float, list[str]]:
        fields = {
            "tag": " ".join(case.tags).casefold(),
            "problem": (case.design_problem or "").casefold(),
            "strategy": (case.strategy or "").casefold(),
            "spatial": (case.spatial_logic or "").casefold(),
            "atmosphere": (case.atmosphere or "").casefold(),
            "type": (case.building_type or "").casefold(),
            "principle": " ".join(case.transferable_principles).casefold(),
            "name": (case.name or "").casefold(),
        }
        weights = {
            "tag": 1.0,
            "problem": 0.9,
            "principle": 0.85,
            "spatial": 0.7,
            "strategy": 0.7,
            "atmosphere": 0.55,
            "type": 0.5,
            "name": 0.35,
        }
        score = 0.0
        hits: list[str] = []
        for token in tokens:
            for field_name, blob in fields.items():
                if token in blob:
                    score += weights[field_name]
                    if token not in hits and len(token) >= 2:
                        hits.append(token)
                    break
        # Normalize roughly by token count
        if tokens:
            score = score / max(4.0, len(tokens) * 0.35)
        return min(1.5, score), hits[:8]

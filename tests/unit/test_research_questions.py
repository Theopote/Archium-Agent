"""Unit tests for ResearchQuestion decomposition."""

from __future__ import annotations

from uuid import uuid4

from archium.application.research_question_service import ResearchQuestionService
from archium.application.research_topics import (
    collect_mission_research_questions,
    collect_mission_research_topic_candidates,
)
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.project_mission import ProjectMission
from archium.domain.research_question import ResearchQuestionCategory


def test_case_dump_rewritten_to_problem_question() -> None:
    service = ResearchQuestionService()
    mission = ProjectMission(
        project_id=uuid4(),
        title="文化中心",
        task_statement="探索",
        design_intent=DesignIntent(
            theme="山地公共文化",
            problem_statement="城乡公共交流空间不足",
            social_background="年轻人口外流、公共文化设施薄弱",
            research_needed=["中国乡村文化中心案例"],
        ),
    )
    questions = service.decompose_mission(mission)
    assert questions
    assert any(q.category == ResearchQuestionCategory.SOCIAL for q in questions)
    assert any(q.category == ResearchQuestionCategory.ARCHITECTURAL for q in questions)
    case_q = next(q for q in questions if "案例" in q.related_intent or "乡村" in q.question)
    assert "如何" in case_q.question or "原则" in case_q.question
    assert "案例列表" not in case_q.question


def test_mission_topics_prefer_research_questions() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="山地文化中心",
        task_statement="探索",
        design_intent=DesignIntent(
            theme="山地",
            problem_statement="如何用建筑回应山地乡镇公共空间缺失？",
            cultural_context="台地农耕聚落",
            research_needed=["山地文化建筑案例"],
        ),
    )
    questions = collect_mission_research_questions(mission)
    candidates = collect_mission_research_topic_candidates(mission)
    assert questions
    assert candidates
    assert candidates[0].question is not None
    assert "？" in candidates[0].text or "如何" in candidates[0].text

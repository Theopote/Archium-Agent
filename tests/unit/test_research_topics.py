"""Tests for mission research topic collection."""

from __future__ import annotations

from uuid import uuid4

from archium.application.research_topics import collect_mission_research_topics
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.project_mission import ProjectMission


def test_collect_mission_research_topics_merges_and_deduplicates() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="测试",
        task_statement="探索文化中心",
        design_intent=DesignIntent(
            research_needed=["关中乡村公共文化空间", " 关中乡村公共文化空间 "],
        ),
        research_questions=["中国乡村文化建筑有哪些典型模式？", "关中乡村公共文化空间"],
    )

    topics = collect_mission_research_topics(mission)

    assert topics == [
        "关中乡村公共文化空间",
        "中国乡村文化建筑有哪些典型模式？",
    ]


def test_collect_mission_research_topics_case_insensitive_dedup() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="测试",
        task_statement="探索",
        design_intent=DesignIntent(research_needed=["Public Space"]),
        research_questions=["public space"],
    )

    topics = collect_mission_research_topics(mission)

    assert topics == ["Public Space"]

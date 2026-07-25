"""Unit tests for project-level research topic collection (pre-mission Act)."""

from __future__ import annotations

from archium.application.research_topics import collect_project_research_topics
from archium.domain.intent.knowledge_state import KnowledgeState


def test_temple_case_derives_cultural_topics() -> None:
    state = KnowledgeState(
        known={"location": "秦岭", "type": "寺庙"},
        unknown=["场地条件"],
    )
    topics = collect_project_research_topics(
        project_name="秦岭寺庙",
        project_description="秦岭深处一座寺庙改扩建，强调礼佛轴线与禅意氛围",
        knowledge_state=state,
    )
    blob = " ".join(topics)
    assert topics
    assert "文化" in blob or "礼仪" in blob or "秦岭" in blob

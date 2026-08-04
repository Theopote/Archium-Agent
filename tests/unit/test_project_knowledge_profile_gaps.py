"""Fresh gap overlay must not leave stale '仍缺' rows on the studio panel."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from archium.application.knowledge_gap_detection import KnowledgeGapEntry, KnowledgeGapReport
from archium.application.project_knowledge_display import (
    KnowledgeSituation,
    ProjectKnowledgeDisplay,
)
from archium.ui.project_knowledge_profile import _apply_fresh_gap_report


def _display(**kwargs: object) -> ProjectKnowledgeDisplay:
    base = dict(
        situation=KnowledgeSituation.INTENT_LED,
        situation_label="意图清晰·资料尚少",
        completeness_pct=40,
        stage_label="概念",
        workflow_label="推演概念方向",
        confidence_pct=50,
        headline="test",
        caption="",
        focus="澄清",
        suggested_actions=(),
        known_highlights=("· 项目名称：滨江城市客厅文化中心",),
        missing_highlights=("待补充：项目名称", "待补充：项目位置", "待补充：主要功能"),
        blocking_unknown_count=0,
    )
    base.update(kwargs)
    return ProjectKnowledgeDisplay(**base)  # type: ignore[arg-type]


def test_empty_live_gaps_clear_stale_missing_highlights(monkeypatch) -> None:
    project_id = uuid4()
    report = KnowledgeGapReport(project_id=project_id, gaps=[])

    class _Svc:
        def __init__(self, _session) -> None:
            pass

        def get_view(self, _project_id):
            return SimpleNamespace(gap_report=report)

    monkeypatch.setattr(
        "archium.application.project_knowledge_service.ProjectKnowledgeService",
        _Svc,
    )
    updated = _apply_fresh_gap_report(object(), project_id, _display())
    assert updated.missing_highlights == ()
    assert updated.blocking_unknown_count == 0


def test_filtered_gaps_do_not_fall_back_to_stale_missing(monkeypatch) -> None:
    project_id = uuid4()
    report = KnowledgeGapReport(
        project_id=project_id,
        gaps=[
            KnowledgeGapEntry(
                gap_id="missing:project_name",
                category="missing_fact",
                description="缺少标准事实：项目名称",
                why_it_matters="x",
                related_keys=("project_name",),
            )
        ],
    )

    class _Svc:
        def __init__(self, _session) -> None:
            pass

        def get_view(self, _project_id):
            return SimpleNamespace(gap_report=report)

    monkeypatch.setattr(
        "archium.application.project_knowledge_service.ProjectKnowledgeService",
        _Svc,
    )
    updated = _apply_fresh_gap_report(object(), project_id, _display())
    assert updated.missing_highlights == ()

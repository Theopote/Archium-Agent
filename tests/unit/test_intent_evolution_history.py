"""Unit tests for IntentEvolution Design History Graph fields."""

from __future__ import annotations

from archium.domain.intent.intent_evolution import (
    IntentEvolution,
    IntentEvolutionEvent,
    IntentEvolutionKind,
)


def test_display_line_full_delta() -> None:
    event = IntentEvolutionEvent(
        kind=IntentEvolutionKind.RESEARCH,
        summary="placeholder",
        previous_summary="现代文化中心",
        new_summary="当代院落文化空间",
        reason="发现当地传统聚落形态",
        evidence_refs=["关中院落轴线研究"],
    )
    assert event.display_line() == (
        "因为发现当地传统聚落形态，从「现代文化中心」调整为「当代院落文化空间」"
    )


def test_append_rewrites_summary_from_graph_fields() -> None:
    evo = IntentEvolution().append(
        IntentEvolutionKind.DIRECTION_SELECTED,
        "选定概念方向：院落",
        trigger="选定概念方向",
        previous_summary="现代文化中心",
        new_summary="当代院落文化空间",
        reason="建筑师在概念探索中选定当前方向",
        evidence_refs=["庭院序列"],
    )
    event = evo.events[-1]
    assert "从「现代文化中心」调整为「当代院落文化空间」" in event.summary
    assert event.trigger == "选定概念方向"
    assert event.evidence_refs == ["庭院序列"]


def test_legacy_summary_only_still_loads() -> None:
    event = IntentEvolutionEvent(
        kind=IntentEvolutionKind.SEED,
        summary="初始想法：秦岭寺庙",
    )
    assert event.display_line() == "初始想法：秦岭寺庙"
    assert event.has_history_edge() is False
    loaded = IntentEvolution.model_validate(
        {"events": [{"kind": "seed", "summary": "旧事件仅有 summary"}]}
    )
    assert loaded.events[0].display_line() == "旧事件仅有 summary"

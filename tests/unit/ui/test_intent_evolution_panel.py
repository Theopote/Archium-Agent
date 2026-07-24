"""Unit tests for IntentEvolution timeline UI helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from archium.domain.intent.intent_evolution import (
    IntentEvolution,
    IntentEvolutionEvent,
    IntentEvolutionKind,
)
from archium.ui.intent_evolution_panel import (
    format_intent_event_time,
    intent_evolution_kind_label,
)


def test_intent_evolution_kind_labels() -> None:
    assert intent_evolution_kind_label(IntentEvolutionKind.SEED) == "初始想法"
    assert intent_evolution_kind_label("research") == "研究补充"
    assert intent_evolution_kind_label("unknown_kind") == "unknown_kind"


def test_format_intent_event_time() -> None:
    stamp = datetime(2026, 7, 24, 15, 30, tzinfo=UTC)
    text = format_intent_event_time(stamp)
    assert "07-24" in text
    assert ":" in text


def test_timeline_panel_module_exports_renderers() -> None:
    from archium.ui import intent_evolution_panel as panel

    assert callable(panel.render_intent_evolution_timeline)
    assert callable(panel.render_project_knowledge_and_evolution)
    assert callable(panel.render_knowledge_and_evolution)


def test_concept_exploration_uses_timeline_panel() -> None:
    src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "concept_exploration.py"
    )
    text = src.read_text(encoding="utf-8")
    assert "render_project_knowledge_and_evolution" in text


def test_mission_panel_uses_timeline_panel() -> None:
    src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "mission_panel.py"
    )
    text = src.read_text(encoding="utf-8")
    assert "render_project_knowledge_and_evolution" in text


def test_genesis_shows_intent_timeline() -> None:
    src = (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "ui"
        / "pages"
        / "project_genesis.py"
    )
    text = src.read_text(encoding="utf-8")
    assert "意图演进时间线" in text
    assert "render_project_knowledge_and_evolution" in text


def test_timeline_handles_empty_evolution() -> None:
    """Smoke: empty evolution path does not raise when building event list."""
    evolution = IntentEvolution(events=[])
    assert evolution.latest_summary() is None
    assert list(evolution.events) == []


def test_timeline_preserves_event_order() -> None:
    evolution = IntentEvolution(
        events=[
            IntentEvolutionEvent(
                kind=IntentEvolutionKind.SEED,
                summary="西安文化中心",
                at=datetime(2026, 7, 1, tzinfo=UTC),
            ),
            IntentEvolutionEvent(
                kind=IntentEvolutionKind.DIRECTION_SELECTED,
                summary="选定青年日常方向",
                at=datetime(2026, 7, 2, tzinfo=UTC),
            ),
        ]
    )
    assert [e.kind for e in evolution.events] == [
        IntentEvolutionKind.SEED,
        IntentEvolutionKind.DIRECTION_SELECTED,
    ]

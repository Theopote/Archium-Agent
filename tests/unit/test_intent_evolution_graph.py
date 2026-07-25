"""Unit tests for Design History Graph helpers."""

from __future__ import annotations

from uuid import uuid4

from archium.application.intent_evolution_graph import (
    format_shift_line,
    intent_label_from_mission,
    iter_design_history_edges,
)
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.intent.intent_evolution import IntentEvolution, IntentEvolutionKind
from archium.domain.project_mission import ProjectMission


def test_format_shift_line_matches_product_example() -> None:
    line = format_shift_line(
        previous="现代文化中心",
        new="当代院落文化空间",
        reason="发现当地传统聚落形态",
    )
    assert line == "因为发现当地传统聚落形态，从「现代文化中心」调整为「当代院落文化空间」"


def test_iter_design_history_edges_skips_status_only() -> None:
    evo = (
        IntentEvolution()
        .append(IntentEvolutionKind.SEED, "初始想法：秦岭")
        .append(
            IntentEvolutionKind.RESEARCH,
            "研究",
            previous_summary="现代文化中心",
            new_summary="当代院落文化空间",
            reason="发现当地传统聚落形态",
            evidence_refs=["关中院落"],
        )
    )
    edges = iter_design_history_edges(evo, require_shift=True)
    assert len(edges) == 1
    assert "当代院落文化空间" in edges[0].display_line
    assert edges[0].evidence == ("关中院落",)


def test_intent_label_from_mission_prefers_theme() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="文化中心",
        task_statement="探索青年文化中心",
        design_intent=DesignIntent(theme="当代院落文化空间"),
    )
    assert intent_label_from_mission(mission) == "当代院落文化空间"

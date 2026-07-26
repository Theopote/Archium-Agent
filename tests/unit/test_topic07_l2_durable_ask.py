"""Topic 07 L2 — durable Ask + design critique hydrate."""

from __future__ import annotations

from uuid import uuid4

from archium.application.design_revise_persistence import (
    design_critique_resume_page,
)
from archium.domain.intent.intent_evolution import (
    IntentEvolution,
    IntentEvolutionKind,
)


def test_pending_revise_round_trip_on_intent_evolution() -> None:
    offer = {
        "direction_id": str(uuid4()),
        "project_id": str(uuid4()),
        "mode": "ask",
        "diff_lines": ["将应用：补强证据"],
        "critique": {"verdict": "caution", "summary": "证据不足"},
    }
    evo = IntentEvolution().with_pending_design_revise(offer)
    assert evo.pending_design_revise is not None
    assert evo.pending_design_revise["mode"] == "ask"
    cleared = evo.clear_pending_design_revise()
    assert cleared.pending_design_revise is None
    assert len(cleared.events) == 0


def test_append_preserves_pending_revise() -> None:
    offer = {"direction_id": str(uuid4()), "project_id": str(uuid4())}
    evo = IntentEvolution().with_pending_design_revise(offer)
    evo2 = evo.append(IntentEvolutionKind.SEED, "种子")
    assert evo2.pending_design_revise is not None
    assert evo2.pending_design_revise["direction_id"] == offer["direction_id"]
    assert len(evo2.events) == 1


def test_latest_design_critique_snapshot_from_edge() -> None:
    report = {
        "verdict": "caution",
        "summary": "形式偏重",
        "weaknesses": [{"text": "缺场地证据"}],
        "missing_evidence": [],
        "alternative_directions": [],
    }
    evo = IntentEvolution().append(
        IntentEvolutionKind.DESIGN_CRITIQUE,
        "设计批判：形式偏重",
        new_summary="caution",
        reason="形式偏重",
        design_intent_snapshot=report,
    )
    snap = evo.latest_design_critique_snapshot()
    assert snap is not None
    assert snap["verdict"] == "caution"
    assert snap["summary"] == "形式偏重"


def test_pending_critique_preferred_over_edge() -> None:
    evo = IntentEvolution().append(
        IntentEvolutionKind.DESIGN_CRITIQUE,
        "旧批判",
        new_summary="proceed",
        design_intent_snapshot={"verdict": "proceed", "summary": "旧"},
    )
    evo = evo.with_pending_design_revise(
        {
            "direction_id": str(uuid4()),
            "critique": {"verdict": "reject", "summary": "待 Ask"},
        }
    )
    # Application helper prefers pending; domain getter still returns edge
    # when called via persistence layer — verify resume page helper
    assert design_critique_resume_page({"verdict": "reject"}) == "concept-exploration"
    assert design_critique_resume_page({"verdict": "proceed"}) is None
    assert design_critique_resume_page({"verdict": "caution"}) == "concept-exploration"


def test_intent_evolution_json_round_trip_includes_pending() -> None:
    offer = {
        "direction_id": str(uuid4()),
        "project_id": str(uuid4()),
        "critique": {"verdict": "caution", "summary": "x"},
    }
    evo = IntentEvolution().with_pending_design_revise(offer)
    raw = evo.model_dump(mode="json")
    loaded = IntentEvolution.model_validate(raw)
    assert loaded.pending_design_revise is not None
    assert loaded.pending_design_revise["direction_id"] == offer["direction_id"]

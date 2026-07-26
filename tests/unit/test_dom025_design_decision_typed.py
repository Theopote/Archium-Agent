"""DOM-025 — IntentEvolution.design_decision is typed DesignDecision."""

from __future__ import annotations

from archium.domain.intent.intent_evolution import (
    IntentEvolution,
    IntentEvolutionKind,
    coerce_design_decision,
)
from archium.domain.spatial_design import DesignDecision


def test_append_accepts_typed_design_decision() -> None:
    decision = DesignDecision(
        decision="选定院落策略",
        chosen="内院",
        reason="回应密度与通风",
        alternatives=["外廊", "塔楼"],
        evidence=["场地分析"],
    )
    evo = IntentEvolution().append(
        IntentEvolutionKind.DESIGN_DECISION,
        decision.decision,
        design_decision=decision,
    )
    assert isinstance(evo.events[-1].design_decision, DesignDecision)
    assert evo.events[-1].design_decision.chosen == "内院"
    dumped = evo.model_dump(mode="json")
    reloaded = IntentEvolution.model_validate(dumped)
    assert isinstance(reloaded.events[-1].design_decision, DesignDecision)
    assert reloaded.events[-1].design_decision.decision == "选定院落策略"


def test_legacy_dict_design_decision_still_loads() -> None:
    payload = {
        "events": [
            {
                "kind": "design_decision",
                "summary": "旧决策",
                "design_decision": {
                    "decision": "保留旧树",
                    "chosen": "保留",
                    "reason": "文保",
                    "alternatives": [],
                    "evidence": [],
                    "impact": "",
                    "direction_id": "",
                    "direction_title": "",
                },
            }
        ]
    }
    evo = IntentEvolution.model_validate(payload)
    assert isinstance(evo.events[0].design_decision, DesignDecision)
    assert evo.events[0].design_decision.decision == "保留旧树"


def test_coerce_design_decision_soft_fails_unknown() -> None:
    assert coerce_design_decision({"not_a_field": 1}) is None
    assert coerce_design_decision(None) is None

"""UI helpers for SpatialIntent / DesignRule / DesignDecision."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from archium.domain.spatial_design import DesignDecision, DesignRule, SpatialIntent
from archium.ui.components.spatial_design_details import (
    render_design_decision,
    render_design_rules,
    render_spatial_intent,
    render_spatial_intent_from_snapshot,
)
from archium.ui.intent_evolution_panel import intent_evolution_kind_label
from archium.domain.intent.intent_evolution import IntentEvolutionKind


def test_render_helpers_noop_on_empty() -> None:
    render_spatial_intent(None)
    render_spatial_intent(SpatialIntent())
    render_design_rules([])
    render_design_rules([DesignRule()])
    render_design_decision(None)
    render_design_decision({})
    render_spatial_intent_from_snapshot(None)
    render_spatial_intent_from_snapshot({})


def test_render_spatial_intent_and_rules() -> None:
    intent = SpatialIntent(
        landscape_relation="嵌入山体",
        movement_experience="沿等高线慢行",
        light_strategy="北向柔光",
    )
    rules = [
        DesignRule(
            principle="嵌入而非对峙",
            spatial_translation="体量嵌入台地",
            formal_translation="水平延展",
            evaluation_method="是否削弱对坡地轮廓的打断",
            confidence=0.8,
        )
    ]
    with patch("archium.ui.components.spatial_design_details.st") as st:
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=None)
        ctx.__exit__ = MagicMock(return_value=False)
        st.expander.return_value = ctx
        render_spatial_intent(intent)
        render_design_rules(rules)
        assert st.expander.call_count >= 2
        asserted = " ".join(
            str(call.args[0]) for call in st.markdown.call_args_list if call.args
        )
        assert "嵌入山体" in asserted
        assert "嵌入而非对峙" in asserted


def test_render_design_decision_from_dict() -> None:
    payload = DesignDecision(
        decision="选定山地嵌入方向",
        chosen="山地嵌入",
        reason="弱化体量",
        impact="空间组织沿等高线展开",
    ).as_dict()
    with patch("archium.ui.components.spatial_design_details.st") as st:
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=None)
        ctx.__exit__ = MagicMock(return_value=False)
        st.expander.return_value = ctx
        render_design_decision(payload)
        asserted = " ".join(
            str(call.args[0]) for call in st.markdown.call_args_list if call.args
        )
        assert "山地嵌入" in asserted


def test_snapshot_spatial_layer_renders() -> None:
    snapshot = {
        "theme": "山地嵌入",
        "spatial_intent": {
            "landscape_relation": "嵌入",
            "spatial_relationships": "",
            "movement_experience": "",
            "public_private_structure": "",
            "light_strategy": "",
        },
        "design_rules": [
            {
                "principle": "顺应地形",
                "spatial_translation": "台地展开",
                "formal_translation": "",
                "evaluation_method": "",
                "confidence": 0.6,
            }
        ],
    }
    with patch("archium.ui.components.spatial_design_details.st") as st:
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=None)
        ctx.__exit__ = MagicMock(return_value=False)
        st.expander.return_value = ctx
        render_spatial_intent_from_snapshot(snapshot)
        asserted = " ".join(
            str(call.args[0]) for call in st.markdown.call_args_list if call.args
        )
        assert "嵌入" in asserted
        assert "顺应地形" in asserted


def test_design_decision_kind_label() -> None:
    assert intent_evolution_kind_label(IntentEvolutionKind.DESIGN_DECISION) == "设计决策"
    assert intent_evolution_kind_label(IntentEvolutionKind.DESIGN_CRITIQUE) == "设计批评"

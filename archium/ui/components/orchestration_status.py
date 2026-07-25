"""Minimal orchestration status strip for Mission / Genesis."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.domain.orchestration import (
    HumanGate,
    OrchestrationPlan,
    OrchestrationStageStatus,
    label_for_stage,
)
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.llm_settings import get_ui_effective_settings


def render_orchestration_status(
    project_id: UUID,
    *,
    key_prefix: str = "orch",
) -> None:
    """Show active orchestration run and a Continue button when awaiting user."""
    from archium.application.orchestration import (
        WorkflowOrchestrationService,
    )
    from archium.infrastructure.llm.factory import create_llm_provider

    settings = get_ui_effective_settings()
    with get_session() as session:
        llm = create_llm_provider(settings)
        service = WorkflowOrchestrationService(session, llm, settings=settings)
        run = service.get_active_run(project_id)
        if run is None:
            # Fall back to session-stashed id
            raw_id = st.session_state.get("orchestration_run_id")
            if raw_id:
                try:
                    run = service.get_run(UUID(str(raw_id)))
                except Exception:
                    run = None
        if run is None:
            return
        try:
            plan = OrchestrationPlan.model_validate(run.state.get("orchestration_plan") or {})
        except Exception:
            return
        stage = plan.active_stage()
        if stage is None:
            st.caption(f"工作编排已结束 · run `{str(run.id)[:8]}…`")
            return
        st.info(
            f"当前编排：{label_for_stage(stage.stage)}（{stage.status.value}）"
            f" · 阶段 {plan.active_index + 1}/{len(plan.stages)}"
            f" · run `{str(run.id)[:8]}…`"
        )
        gate_raw = run.state.get("human_gate")
        if isinstance(gate_raw, dict):
            try:
                gate = HumanGate.model_validate(gate_raw)
                st.caption(f"待确认：{gate.label} — {gate.prompt}")
            except Exception:
                pass
        router = run.state.get("decision_router")
        if isinstance(router, dict) and router.get("changed"):
            st.caption(f"决策路由：{router.get('reason') or '已按上下文重规划'}")
        reflection = run.state.get("last_reflection")
        if isinstance(reflection, dict):
            from archium.ui.components.design_reflection_details import (
                render_design_reflection,
            )

            render_design_reflection(reflection, expanded=False)
        if stage.status in {
            OrchestrationStageStatus.AWAITING_USER,
            OrchestrationStageStatus.AWAITING_REVIEW,
        }:
            cols = st.columns([1, 1, 2])
            if cols[0].button(
                "继续编排",
                key=f"{key_prefix}_advance_{run.id}",
                use_container_width=True,
            ):
                try:
                    with get_session() as advance_session:
                        advance_llm = create_llm_provider(settings)
                        advance_service = WorkflowOrchestrationService(
                            advance_session, advance_llm, settings=settings
                        )
                        result = advance_service.advance(run.id)
                        st.session_state["orchestration_run_id"] = str(
                            result.workflow_run.id
                        )
                        st.session_state["orchestration_active_stage"] = (
                            result.active_stage.value if result.active_stage else None
                        )
                        if result.replan_decision and result.replan_decision.get("changed"):
                            st.session_state["orchestration_replan"] = result.replan_decision
                        if result.page_key:
                            from archium.ui.app_navigation import get_app_page

                            st.switch_page(get_app_page(result.page_key))
                        st.rerun()
                except Exception as exc:
                    st.error(format_user_error(exc))
            if cols[1].button(
                "按上下文重规划",
                key=f"{key_prefix}_replan_{run.id}",
                use_container_width=True,
                help="根据当前知识状态改写尚未执行的阶段，不打断当前待确认步骤",
            ):
                try:
                    with get_session() as replan_session:
                        replan_llm = create_llm_provider(settings)
                        replan_service = WorkflowOrchestrationService(
                            replan_session, replan_llm, settings=settings
                        )
                        result = replan_service.replan(run.id, drive=False)
                        st.session_state["orchestration_run_id"] = str(
                            result.workflow_run.id
                        )
                        if result.replan_decision:
                            st.session_state["orchestration_replan"] = (
                                result.replan_decision
                            )
                        st.rerun()
                except Exception as exc:
                    st.error(format_user_error(exc))

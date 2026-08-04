"""Orchestration status strip for Mission / Genesis + compact five-stage chrome."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import streamlit as st

from archium.config.settings import Settings
from archium.domain.orchestration import (
    HumanGate,
    OrchestrationPlan,
    OrchestrationStageStatus,
    label_for_stage,
    list_process_timeline,
)
from archium.domain.workflow import WorkflowRun
from archium.application.unit_of_work import unit_of_work
from archium.ui.error_handlers import report_user_error
from archium.ui.llm_settings import get_ui_effective_settings

_AWAITING = frozenset(
    {
        OrchestrationStageStatus.AWAITING_USER,
        OrchestrationStageStatus.AWAITING_REVIEW,
    }
)


def parse_human_gate(state: dict[str, Any] | None) -> HumanGate | None:
    """Parse ``run.state['human_gate']`` when present and valid."""
    if not isinstance(state, dict):
        return None
    raw = state.get("human_gate")
    if not isinstance(raw, dict):
        return None
    try:
        return HumanGate.model_validate(raw)
    except Exception:
        return None


def human_gate_caption(gate: HumanGate | None) -> str | None:
    """Product chrome line for a pending HumanGate."""
    if gate is None:
        return None
    label = (gate.label or "").strip()
    prompt = (gate.prompt or "").strip()
    if label and prompt:
        return f"待确认：{label} — {prompt}"
    if label:
        return f"待确认：{label}"
    if prompt:
        return f"待确认：{prompt}"
    return None


def should_show_compact_gate(
    run: WorkflowRun | None,
    *,
    plan: OrchestrationPlan | None = None,
) -> bool:
    """True when five-stage chrome should show the compact HumanGate strip."""
    if run is None:
        return False
    gate = parse_human_gate(run.state)
    if gate is not None:
        return True
    resolved = plan
    if resolved is None:
        try:
            resolved = OrchestrationPlan.model_validate(
                run.state.get("orchestration_plan") or {}
            )
        except Exception:
            return False
    stage = resolved.active_stage()
    return stage is not None and stage.status in _AWAITING


def render_orchestration_status(
    project_id: UUID,
    *,
    key_prefix: str = "orch",
    compact: bool = False,
    current_page_key: str | None = None,
) -> None:
    """Show active orchestration run and Continue when awaiting user.

    ``compact=True`` (Topic 07 / UI-009): only gate caption + Continue/Replan
    when a HumanGate / awaiting stage is active — for five-stage chrome.
    """
    from archium.application.orchestration import (
        WorkflowOrchestrationService,
    )
    from archium.infrastructure.llm.factory import create_llm_provider

    settings = get_ui_effective_settings()
    with unit_of_work() as uow:
        session = uow
        llm = create_llm_provider(settings)
        service = WorkflowOrchestrationService(session, llm, settings=settings)
        run = service.get_active_run(project_id)
        if run is None:
            raw_id = st.session_state.get("orchestration_run_id")
            if raw_id:
                try:
                    run = service.get_run(UUID(str(raw_id)))
                except Exception:
                    run = None
        if run is None:
            return
        try:
            plan = OrchestrationPlan.model_validate(
                run.state.get("orchestration_plan") or {}
            )
        except Exception:
            return
        stage = plan.active_stage()
        if stage is None:
            if not compact:
                st.caption(f"工作编排已结束 · run `{str(run.id)[:8]}…`")
            return

        if compact:
            if not should_show_compact_gate(run, plan=plan):
                return
            _render_compact_gate(
                run,
                stage_status=stage.status,
                key_prefix=key_prefix,
                settings=settings,
                current_page_key=current_page_key,
            )
            return

        st.info(
            f"当前编排：{label_for_stage(stage.stage)}（{stage.status.value}）"
            f" · 阶段 {plan.active_index + 1}/{len(plan.stages)}"
            f" · run `{str(run.id)[:8]}…`"
        )
        try:
            from archium.ui.project_event_panel import render_job_progress_strip

            render_job_progress_strip(
                project_id,
                limit=3,
                active_only=True,
                title="相关任务进度",
            )
        except Exception:
            from archium.logging import get_logger

            get_logger(__name__).debug(
                'orchestration human-gate panel unavailable',
                exc_info=True,
            )
        caption = human_gate_caption(parse_human_gate(run.state))
        if caption:
            st.caption(caption)
        router = run.state.get("decision_router")
        if isinstance(router, dict) and router.get("changed"):
            st.caption(f"决策路由：{router.get('reason') or '已按上下文重规划'}")
        timeline = list_process_timeline(run.state, limit=8)
        if timeline:
            with st.expander(f"设计过程史（{len(timeline)}）", expanded=False):
                for event in reversed(timeline):
                    when = ""
                    try:
                        when = event.at.astimezone().strftime("%m-%d %H:%M")
                    except Exception:
                        when = str(event.at)[:16]
                    st.markdown(f"- `{when}` · {event.display_line()}")
                    if event.intent_evolution_kind:
                        st.caption(f"↔ IntentEvolution · {event.intent_evolution_kind}")
        reflection = run.state.get("last_reflection")
        if isinstance(reflection, dict):
            from archium.ui.components.design_reflection_details import (
                render_design_reflection,
            )

            render_design_reflection(reflection, expanded=False)
        if stage.status in _AWAITING:
            _render_advance_replan_buttons(
                run, key_prefix=key_prefix, settings=settings
            )


def _render_compact_gate(
    run: WorkflowRun,
    *,
    stage_status: OrchestrationStageStatus,
    key_prefix: str,
    settings: Settings,
    current_page_key: str | None,
) -> None:
    gate = parse_human_gate(run.state)
    caption = human_gate_caption(gate)
    if caption:
        st.warning(caption)
    elif stage_status in _AWAITING:
        st.warning("编排暂停，等待确认后继续。")
    else:
        return

    if gate is not None:
        page_key = (gate.page_key or "").strip() or None
        if page_key and page_key != (current_page_key or "").strip():
            try:
                from archium.ui.app_navigation import get_app_page

                st.page_link(
                    get_app_page(page_key),
                    label=f"前往：{gate.label or page_key}",
                )
            except Exception:
                from archium.logging import get_logger

                get_logger(__name__).debug(
                    'human-gate page link unavailable',
                    exc_info=True,
                )

    if stage_status in _AWAITING:
        _render_advance_replan_buttons(run, key_prefix=key_prefix, settings=settings)


def _render_advance_replan_buttons(
    run: WorkflowRun,
    *,
    key_prefix: str,
    settings: Settings,
) -> None:
    from archium.application.orchestration import WorkflowOrchestrationService
    from archium.infrastructure.llm.factory import create_llm_provider

    cols = st.columns([1, 1, 2])
    if cols[0].button(
        "继续编排",
        key=f"{key_prefix}_advance_{run.id}",
        use_container_width=True,
    ):
        try:
            with unit_of_work() as uow:
                advance_session = uow
                advance_llm = create_llm_provider(settings)
                advance_service = WorkflowOrchestrationService(
                    advance_session, advance_llm, settings=settings
                )
                result = advance_service.advance(run.id)
                st.session_state["orchestration_run_id"] = str(result.workflow_run.id)
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
            st.error(report_user_error(exc))
    if cols[1].button(
        "按上下文重规划",
        key=f"{key_prefix}_replan_{run.id}",
        use_container_width=True,
        help="根据当前知识状态改写尚未执行的阶段，不打断当前待确认步骤",
    ):
        try:
            with unit_of_work() as uow:
                replan_session = uow
                replan_llm = create_llm_provider(settings)
                replan_service = WorkflowOrchestrationService(
                    replan_session, replan_llm, settings=settings
                )
                result = replan_service.replan(run.id, drive=False)
                st.session_state["orchestration_run_id"] = str(result.workflow_run.id)
                if result.replan_decision:
                    st.session_state["orchestration_replan"] = result.replan_decision
                st.rerun()
        except Exception as exc:
            st.error(report_user_error(exc))

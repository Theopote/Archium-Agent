"""Project genesis — single prompt → KnowledgeState → Next Best Actions."""

from __future__ import annotations

import streamlit as st

from archium.application.project_management_service import ProjectManagementService
from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.enums import ProjectOriginMode
from archium.domain.intent.next_best_action import NextBestActionType
from archium.exceptions import ValidationError, WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.components.chrome import render_page_header
from archium.ui.error_handlers import report_user_error
from archium.ui.llm_settings import get_ui_effective_settings

_ASSESSMENT_KEY = "genesis_context_assessment"
_PROJECT_KEY = "genesis_assessed_project_id"


def render() -> None:
    """Describe the project; Archium assesses knowledge and suggests next steps."""
    render_page_header(
        "开始项目",
        "告诉我你的想法或项目情况——不必先选「有资料还是没资料」。",
    )
    st.caption(
        "建筑设计是知识完整度的连续谱：多数项目介于纯想法与完备资料之间。"
        "系统会判断已知/未知，并建议下一步。"
    )

    assessed_id = st.session_state.get(_PROJECT_KEY)
    assessment_payload = st.session_state.get(_ASSESSMENT_KEY)
    if assessed_id and assessment_payload:
        _render_assessment_card(str(assessed_id), assessment_payload)
        if st.button("重新描述", key="genesis_reset"):
            st.session_state.pop(_PROJECT_KEY, None)
            st.session_state.pop(_ASSESSMENT_KEY, None)
            st.rerun()
        return

    _render_entry_form()


def _render_entry_form() -> None:
    settings = get_ui_effective_settings()
    with st.form("genesis_context_form"):
        name = st.text_input(
            "项目名称（可选）",
            placeholder="例如：秦岭青年文化中心",
        )
        prompt = st.text_area(
            "描述你的建筑项目、问题或灵感",
            placeholder=(
                "例如：我想在西安做一个青年文化中心；"
                "或：医院改扩建，手头有旧总平与部分照片，甲方还没说清功能分区"
            ),
            height=160,
        )
        submit = st.form_submit_button(
            "开始理解项目",
            type="primary",
            use_container_width=True,
        )
        if not submit:
            return
        if not prompt.strip():
            st.error("请描述你的项目情况或想法")
            return
        try:
            from archium.application.exploration_service import ExplorationService
            from archium.infrastructure.llm.factory import create_llm_provider
            from archium.ui.planning_service import (
                assess_project_context,
                start_exploration_session,
            )

            project_name = name.strip() or _default_name_from_prompt(prompt.strip())
            with get_session() as session:
                # Temporary origin; assess_and_persist will refine.
                project = ProjectManagementService(session).create_project(
                    project_name,
                    prompt.strip(),
                    origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
                )
                assessment = assess_project_context(
                    session,
                    project.id,
                    prompt.strip(),
                    settings=settings if settings.llm_configured else settings,
                )
                should_explore = (
                    assessment.project_context is not None
                    and assessment.project_context.recommended_workflow
                    == RecommendedWorkflow.EXPLORE
                )
                if should_explore:
                    if settings.llm_configured:
                        seed_result = start_exploration_session(
                            session,
                            project.id,
                            prompt.strip(),
                            settings=settings,
                            enrich=True,
                        )
                    else:
                        seed_result = ExplorationService(
                            session, create_llm_provider(settings), settings=settings
                        ).start_session(
                            project.id,
                            prompt.strip(),
                            source="genesis",
                            enrich=False,
                        )
                    for warning in seed_result.warnings:
                        st.session_state.setdefault(
                            "exploration_seed_warnings", []
                        ).append(warning)

            st.session_state.selected_project_id = str(project.id)
            st.session_state.genesis_task_description = prompt.strip()
            st.session_state[_PROJECT_KEY] = str(project.id)
            st.session_state[_ASSESSMENT_KEY] = {
                "understanding_summary": assessment.understanding_summary,
                "knowledge_state": assessment.knowledge_state.model_dump(mode="json"),
                "actions": [a.model_dump(mode="json") for a in assessment.actions],
                "suggested_origin_mode": assessment.suggested_origin_mode.value,
                "warnings": list(assessment.warnings),
                "project_context": (
                    assessment.project_context.model_dump(mode="json")
                    if assessment.project_context is not None
                    else None
                ),
            }
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except WorkflowError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(report_user_error(exc))


def _default_name_from_prompt(prompt: str) -> str:
    line = prompt.strip().splitlines()[0].strip()
    return (line[:40] + ("…" if len(line) > 40 else "")) or "未命名项目"


def _render_intent_evidence_summary(project_id: str) -> None:
    from uuid import UUID

    from archium.infrastructure.database.mission_repositories import MissionRepository
    from archium.infrastructure.database.repositories import ProjectRepository

    try:
        project_uuid = UUID(project_id)
    except ValueError:
        return

    evidence_rows = []
    with get_session() as session:
        missions = MissionRepository(session).list_missions_by_project(project_uuid)
        if missions and missions[0].design_intent is not None:
            evidence_rows = list(missions[0].design_intent.evidence[-6:])
        if not evidence_rows:
            project = ProjectRepository(session).get_by_id(project_uuid)
            if project and project.intent_evolution:
                for event in reversed(project.intent_evolution.events):
                    snapshot = event.design_intent_snapshot or {}
                    rows = snapshot.get("evidence")
                    if isinstance(rows, list) and rows:
                        from archium.domain.intent.intent_evidence import IntentEvidence

                        for row in rows[:6]:
                            if isinstance(row, dict):
                                try:
                                    evidence_rows.append(IntentEvidence.model_validate(row))
                                except Exception:
                                    continue
                        break

    if not evidence_rows:
        return

    st.markdown("**意图出处**")
    for entry in evidence_rows:
        conf = int(round(entry.confidence * 100))
        materials = ""
        if entry.supporting_materials:
            materials = " · " + "；".join(entry.supporting_materials[:2])
        st.caption(f"[{entry.source_label()} {conf}%] {entry.statement}{materials}")


def _render_assessment_card(project_id: str, payload: dict) -> None:
    from archium.domain.context.project_context import ProjectContext
    from archium.domain.intent.knowledge_state import KnowledgeState
    from archium.domain.intent.next_best_action import NextBestAction

    st.session_state.selected_project_id = project_id
    for warning in payload.get("warnings") or []:
        st.warning(warning)

    state = KnowledgeState.model_validate(payload["knowledge_state"])
    st.success(state.summary_line())
    ctx_raw = payload.get("project_context")
    if ctx_raw:
        ctx = ProjectContext.model_validate(ctx_raw)
        stage_label = {
            ProjectLifecycleStage.IDEA: "想法",
            ProjectLifecycleStage.CONCEPT: "概念",
            ProjectLifecycleStage.RESEARCH: "研究",
            ProjectLifecycleStage.DESIGN: "设计",
            ProjectLifecycleStage.DOCUMENTATION: "文档化",
        }.get(ctx.lifecycle_stage, ctx.lifecycle_stage.value)
        workflow_label = {
            RecommendedWorkflow.EXPLORE: "概念探索",
            RecommendedWorkflow.RESEARCH: "背景研究",
            RecommendedWorkflow.MATERIALS: "整理资料",
            RecommendedWorkflow.MISSION: "任务理解",
            RecommendedWorkflow.DESIGN: "方案迭代",
            RecommendedWorkflow.DELIVER: "正式交付",
        }.get(ctx.recommended_workflow, ctx.recommended_workflow.value)
        st.caption(
            f"阶段判断：**{stage_label}** · 建议优先：**{workflow_label}** "
            f"· 把握度约 {int(round(ctx.confidence * 100))}%"
        )
        if ctx.assumptions:
            with st.expander("当前假设（待证实）", expanded=False):
                for item in ctx.assumptions[:6]:
                    st.markdown(f"- {item}")
    if payload.get("understanding_summary"):
        st.markdown(payload["understanding_summary"])

    known = state.known or {}
    if known:
        st.markdown("**目前了解到**")
        for key, value in known.items():
            st.markdown(f"- {key}：{value}")
    unknown = state.unknown or state.missing_information
    if unknown:
        st.markdown("**尚不清楚**")
        for item in unknown[:8]:
            st.markdown(f"- {item}")

    _render_intent_evidence_summary(project_id)

    st.markdown("**建议下一步**")
    actions = [NextBestAction.model_validate(item) for item in payload.get("actions") or []]
    if not actions:
        st.caption("暂无建议，可手动进入概念探索或资料。")
    for index, action in enumerate(actions):
        label = _action_label(action.action)
        help_text = action.reason
        if action.question:
            help_text = f"{help_text}（问：{action.question}）" if help_text else action.question
        if st.button(
            label,
            key=f"nba_{index}_{action.action.value}",
            use_container_width=True,
            type="primary" if index == 0 else "secondary",
            help=help_text or None,
        ):
            _dispatch_action(action.action)
            return

    settings = get_ui_effective_settings()
    if st.button(
        "刷新知识状态",
        key="genesis_reassess",
        use_container_width=True,
    ):
        from archium.ui.planning_service import reassess_project_context
        from uuid import UUID

        with st.spinner("正在重新评估知识状态…"):
            try:
                with get_session() as session:
                    assessment = reassess_project_context(
                        session,
                        UUID(project_id),
                        user_text=st.session_state.get("genesis_task_description"),
                        settings=settings,
                    )
                st.session_state[_ASSESSMENT_KEY] = {
                    "understanding_summary": assessment.understanding_summary,
                    "knowledge_state": assessment.knowledge_state.model_dump(mode="json"),
                    "actions": [a.model_dump(mode="json") for a in assessment.actions],
                    "suggested_origin_mode": assessment.suggested_origin_mode.value,
                    "warnings": list(assessment.warnings),
                    "project_context": (
                        assessment.project_context.model_dump(mode="json")
                        if assessment.project_context is not None
                        else None
                    ),
                }
                st.rerun()
            except WorkflowError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))

    from uuid import UUID

    from archium.ui.intent_evolution_panel import render_project_knowledge_and_evolution

    render_project_knowledge_and_evolution(
        UUID(project_id),
        expanded=False,
        key_prefix="genesis_ks_evo",
        title="意图演进时间线",
        show_knowledge=False,
    )

    st.markdown("---")
    link_cols = st.columns(3)
    with link_cols[0]:
        st.page_link(
            get_app_page("concept-exploration"),
            label="概念探索",
            icon=":material/explore:",
        )
    with link_cols[1]:
        st.page_link(get_app_page("materials"), label="资料", icon=":material/folder:")
    with link_cols[2]:
        st.page_link(
            get_app_page("project-mission"),
            label="项目任务",
            icon=":material/flag:",
        )


def _action_label(action: NextBestActionType) -> str:
    from archium.application.context_intelligence_service import ContextIntelligenceService

    pending, conflicts = _pending_fact_counts()
    return (
        ContextIntelligenceService.resolve_action_target(
            action,
            pending_fact_count=pending,
            conflict_fact_count=conflicts,
        ).label
        or action.value
    )


def _pending_fact_counts() -> tuple[int, int]:
    from uuid import UUID

    from archium.application.fact_ledger_service import FactLedgerService

    project_raw = st.session_state.get("selected_project_id") or st.session_state.get(
        _PROJECT_KEY
    )
    if not project_raw:
        return 0, 0
    try:
        with get_session() as session:
            ledger = FactLedgerService(session).get_ledger(UUID(str(project_raw)))
        return ledger.pending_count, ledger.conflict_count
    except Exception:
        return 0, 0


def _apply_action_dispatch(target) -> None:
    if target.mission_step is not None:
        st.session_state.mission_step = target.mission_step
    if getattr(target, "focus", None):
        st.session_state["materials_focus"] = target.focus


def _dispatch_action(action: NextBestActionType) -> None:
    from uuid import UUID

    from archium.application.context_intelligence_service import ContextIntelligenceService
    from archium.domain.intent.next_best_action import NextBestActionType as ActionType
    from archium.ui.planning_service import try_execute_research_for_project

    project_raw = st.session_state.get("selected_project_id") or st.session_state.get(
        _PROJECT_KEY
    )
    if action == ActionType.RESEARCH and project_raw:
        settings = get_ui_effective_settings()
        with st.spinner("正在启动自主研究…"):
            try:
                with get_session() as session:
                    ok, message = try_execute_research_for_project(
                        session,
                        UUID(str(project_raw)),
                        settings=settings,
                    )
                if ok:
                    st.success(message)
                    st.session_state.pop(_ASSESSMENT_KEY, None)
                    st.session_state.pop(_PROJECT_KEY, None)
                    st.session_state.mission_step = 2
                    st.switch_page(get_app_page("project-mission"))
                    return
                st.info(message)
            except Exception as exc:
                st.warning(report_user_error(exc))

    pending, conflicts = _pending_fact_counts()
    st.session_state.pop(_ASSESSMENT_KEY, None)
    st.session_state.pop(_PROJECT_KEY, None)
    target = ContextIntelligenceService.resolve_action_target(
        action,
        pending_fact_count=pending,
        conflict_fact_count=conflicts,
    )
    _apply_action_dispatch(target)
    st.switch_page(get_app_page(target.page_key))

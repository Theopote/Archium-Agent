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
        go_studio_after = st.checkbox(
            "完成后直接进入工作室预览封面",
            value=True,
            key="genesis_go_studio_after",
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
            from archium.application.context.next_action_selector import resolve_workflow_entry
            from archium.application.context.workflow_navigation import (
                apply_workflow_entry,
                as_session_state,
            )
            from archium.application.fact_ledger_service import FactLedgerService
            from archium.domain.intent.next_best_action import NextBestActionType
            from archium.infrastructure.llm.factory import create_llm_provider
            from archium.ui.planning_service import (
                assess_project_context,
                start_exploration_session,
            )

            project_name = name.strip() or _default_name_from_prompt(prompt.strip())
            with get_session() as session:
                from archium.ui.session_actor import get_current_actor_id

                project = ProjectManagementService(session).create_project(
                    project_name,
                    prompt.strip(),
                    origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
                    actor_id=get_current_actor_id(),
                )
                assessment = assess_project_context(
                    session,
                    project.id,
                    prompt.strip(),
                    settings=settings if settings.llm_configured else settings,
                )
                if assessment.project_context is not None:
                    ledger = FactLedgerService(session).get_ledger(project.id)
                    entry = resolve_workflow_entry(
                        assessment.project_context,
                        pending_fact_count=ledger.pending_count,
                        conflict_fact_count=ledger.conflict_count,
                    )
                    apply_workflow_entry(as_session_state(st.session_state), entry)
                should_explore = (
                    assessment.project_context is not None
                    and (
                        assessment.project_context.recommended_workflow
                        == RecommendedWorkflow.EXPLORE
                        or (
                            assessment.actions
                            and assessment.actions[0].action
                            == NextBestActionType.EXPLORE_DIRECTIONS
                        )
                        or assessment.project_context.lifecycle_stage
                        in {
                            ProjectLifecycleStage.IDEA,
                            ProjectLifecycleStage.RESEARCH,
                            ProjectLifecycleStage.CONCEPT,
                        }
                    )
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
                        from archium.application.exploration_service import ExplorationService

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

                from archium.application.genesis_starter_service import (
                    ensure_genesis_starter_draft,
                )

                starter = ensure_genesis_starter_draft(
                    session,
                    project.id,
                    prompt=prompt.strip(),
                    project_name=project.name,
                    understanding_summary=assessment.understanding_summary or "",
                )

            st.session_state.selected_project_id = str(project.id)
            st.session_state.selected_presentation_id = str(starter.presentation_id)
            st.session_state.genesis_task_description = prompt.strip()
            st.session_state[_PROJECT_KEY] = str(project.id)
            st.session_state[_ASSESSMENT_KEY] = {
                "understanding_summary": assessment.understanding_summary,
                "knowledge_state": assessment.knowledge_state.model_dump(mode="json"),
                "actions": [a.model_dump(mode="json") for a in assessment.actions],
                "reasons": [r.model_dump(mode="json") for r in assessment.reasons],
                "suggested_origin_mode": assessment.suggested_origin_mode.value,
                "warnings": list(assessment.warnings),
                "project_context": (
                    assessment.project_context.model_dump(mode="json")
                    if assessment.project_context is not None
                    else None
                ),
                "starter_draft": {
                    "created": starter.created,
                    "presentation_id": str(starter.presentation_id),
                    "outline_id": str(starter.outline_id) if starter.outline_id else None,
                    "page_count": starter.page_count,
                    "has_first_slide": starter.has_first_slide,
                    "slides_ready_count": starter.slides_ready_count,
                    "layout_ready_count": starter.layout_ready_count,
                    "has_cover_layout": starter.has_cover_layout,
                    "cover_preview_path": starter.cover_preview_path,
                    "summary": starter.summary,
                },
            }
            if go_studio_after and starter.has_first_slide:
                st.session_state.studio_selected_slide_index = 0
                if starter.layout_ready_count >= max(1, starter.page_count):
                    st.session_state.studio_center_mode = "overview"
                st.session_state.studio_genesis_welcome = starter.summary
                st.switch_page(get_app_page("edit"))
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


def _starter_from_payload(payload: dict, project_id: str) -> object | None:
    from uuid import UUID

    from archium.application.genesis_starter_service import (
        GenesisStarterResult,
        ensure_genesis_starter_draft,
    )

    raw = payload.get("starter_draft")
    if isinstance(raw, dict) and raw.get("presentation_id"):
        return GenesisStarterResult(
            created=bool(raw.get("created")),
            presentation_id=UUID(str(raw["presentation_id"])),
            outline_id=UUID(str(raw["outline_id"])) if raw.get("outline_id") else None,
            page_count=int(raw.get("page_count") or 0),
            has_first_slide=bool(raw.get("has_first_slide")),
            slides_ready_count=int(raw.get("slides_ready_count") or 0),
            layout_ready_count=int(raw.get("layout_ready_count") or 0),
            has_cover_layout=bool(raw.get("has_cover_layout")),
            cover_preview_path=str(raw["cover_preview_path"])
            if raw.get("cover_preview_path")
            else None,
            summary=str(raw.get("summary") or ""),
        )
    prompt = st.session_state.get("genesis_task_description") or ""
    understanding = str(payload.get("understanding_summary") or "")
    with get_session() as session:
        from archium.infrastructure.database.repositories import ProjectRepository

        project = ProjectRepository(session).get_by_id(UUID(project_id))
        name = project.name if project is not None else "新汇报"
        return ensure_genesis_starter_draft(
            session,
            UUID(project_id),
            prompt=prompt,
            project_name=name,
            understanding_summary=understanding,
        )


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
        from archium.application.project_knowledge_display import build_project_knowledge_display

        display = build_project_knowledge_display(ctx)
        st.info(display.headline)
        st.caption(display.caption)
        if ctx.assumptions:
            with st.expander("当前假设（待证实）", expanded=False):
                for item in ctx.assumptions[:6]:
                    st.markdown(f"- {item}")
    if payload.get("understanding_summary"):
        st.markdown(payload["understanding_summary"])

    starter = _starter_from_payload(payload, project_id)
    if starter is not None:
        from archium.ui.components.genesis_draft_card import render_genesis_draft_card

        render_genesis_draft_card(starter)
        st.session_state.selected_presentation_id = str(starter.presentation_id)
        st.divider()

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

    from uuid import UUID as _UUID

    from archium.ui.components.orchestration_status import render_orchestration_status

    render_orchestration_status(_UUID(project_id), key_prefix="genesis_orch")

    st.markdown("**下一步行动**")
    actions = [NextBestAction.model_validate(item) for item in payload.get("actions") or []]
    _render_assessment_reasons(payload, knowledge_state=state)
    from archium.ui.components.first_run_guide import render_genesis_next_steps

    render_genesis_next_steps(
        project_id=project_id,
        has_draft=bool(starter is not None and starter.has_first_slide),
        wireframe_ready=bool(
            starter is not None
            and starter.layout_ready_count >= max(1, starter.page_count)
        ),
    )
    st.divider()
    if not actions:
        st.caption("暂无行动，可继续描述项目或补充资料。")
    for index, action in enumerate(actions):
        label = _action_label(action.action, reason=action.reason)
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
        from uuid import UUID

        from archium.ui.planning_service import reassess_project_context

        with st.spinner("正在重新评估知识状态…"):
            try:
                with get_session() as session:
                    assessment = reassess_project_context(
                        session,
                        UUID(project_id),
                        user_text=st.session_state.get("genesis_task_description"),
                        settings=settings,
                    )
                    from archium.application.genesis_starter_service import (
                        GenesisStarterResult,
                        ensure_genesis_starter_draft,
                    )
                    from archium.infrastructure.database.repositories import ProjectRepository

                    project = ProjectRepository(session).get_by_id(UUID(project_id))
                    starter = ensure_genesis_starter_draft(
                        session,
                        UUID(project_id),
                        prompt=st.session_state.get("genesis_task_description") or "",
                        project_name=project.name if project is not None else "新汇报",
                        understanding_summary=assessment.understanding_summary or "",
                    )
                st.session_state[_ASSESSMENT_KEY] = {
                    "understanding_summary": assessment.understanding_summary,
                    "knowledge_state": assessment.knowledge_state.model_dump(mode="json"),
                    "actions": [a.model_dump(mode="json") for a in assessment.actions],
                    "reasons": [r.model_dump(mode="json") for r in assessment.reasons],
                    "suggested_origin_mode": assessment.suggested_origin_mode.value,
                    "warnings": list(assessment.warnings),
                    "project_context": (
                        assessment.project_context.model_dump(mode="json")
                        if assessment.project_context is not None
                        else None
                    ),
                    "starter_draft": {
                        "created": starter.created,
                        "presentation_id": str(starter.presentation_id),
                        "outline_id": str(starter.outline_id) if starter.outline_id else None,
                        "page_count": starter.page_count,
                        "has_first_slide": starter.has_first_slide,
                        "slides_ready_count": starter.slides_ready_count,
                        "layout_ready_count": starter.layout_ready_count,
                        "has_cover_layout": starter.has_cover_layout,
                        "cover_preview_path": starter.cover_preview_path,
                        "summary": starter.summary,
                    },
                }
                st.session_state.selected_presentation_id = str(starter.presentation_id)
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


def _action_label(action: NextBestActionType, *, reason: str = "") -> str:
    from archium.application.context.nba_action_executor import nba_execute_label

    pending, conflicts = _pending_fact_counts()
    has_pending = pending > 0 or conflicts > 0
    return nba_execute_label(
        action,
        has_pending_facts=has_pending and action == NextBestActionType.ASK,
        reason=reason,
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


def _render_assessment_reasons(payload: dict, *, knowledge_state) -> None:
    from archium.domain.intent.context_assessment_reason import ContextAssessmentReason
    from archium.domain.intent.knowledge_state import KnowledgeState

    state = (
        knowledge_state
        if isinstance(knowledge_state, KnowledgeState)
        else KnowledgeState.model_validate(knowledge_state)
    )
    raw = payload.get("reasons") or []
    reasons: list[ContextAssessmentReason] = []
    for item in raw:
        try:
            reasons.append(ContextAssessmentReason.model_validate(item))
        except Exception:
            continue
    if not reasons:
        reasons = list(state.assessment_reasons or [])
    if not reasons:
        return
    with st.expander("判断依据（为何这样行动）", expanded=True):
        for reason in reasons[:5]:
            mark = {
                "support": "＋",
                "block": "−",
                "nuance": "·",
            }.get(reason.polarity.value, "·")
            st.markdown(f"- {mark} {reason.display_line()}")


def _assessment_payload_from_project(session, project_id) -> dict | None:
    from archium.application.project_context_builder import build_project_context

    ctx = build_project_context(session, project_id)
    if ctx is None:
        return None
    state = ctx.knowledge_state
    return {
        "understanding_summary": ctx.understanding_summary,
        "knowledge_state": state.model_dump(mode="json"),
        "actions": [a.model_dump(mode="json") for a in ctx.next_actions],
        "reasons": [r.model_dump(mode="json") for r in state.assessment_reasons],
        "suggested_origin_mode": ctx.suggested_origin_mode.value,
        "warnings": [],
        "project_context": ctx.model_dump(mode="json"),
    }


def _dispatch_action(action: NextBestActionType) -> None:
    from uuid import UUID

    from archium.application.context.nba_action_executor import NbaExecutionResult
    from archium.application.context.workflow_navigation import as_session_state
    from archium.ui.context_navigation import dispatch_next_best_action
    from archium.ui.llm_settings import get_ui_effective_settings

    project_raw = st.session_state.get("selected_project_id") or st.session_state.get(
        _PROJECT_KEY
    )
    if not project_raw:
        return
    settings = get_ui_effective_settings()
    project_id = UUID(str(project_raw))
    with get_session() as session:
        result = dispatch_next_best_action(
            session,
            as_session_state(st.session_state),
            action,
            project_id=project_id,
            settings=settings,
        )
        if isinstance(result, NbaExecutionResult) and result.stay_after_execute and result.success:
            payload = _assessment_payload_from_project(session, project_id)
            if payload is not None:
                st.session_state[_ASSESSMENT_KEY] = payload
                st.session_state[_PROJECT_KEY] = str(project_id)
            st.rerun()
            return
    # Navigated away or navigate-only — clear ephemeral genesis card
    st.session_state.pop(_ASSESSMENT_KEY, None)
    st.session_state.pop(_PROJECT_KEY, None)

"""Mission understanding panel — structured editable fields, not a single AI blob."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.project_mission_service import MissionPatch, suggest_narrative_mode
from archium.domain.architectural_narrative_mode import ArchitecturalNarrativeMode
from archium.domain.enums import (
    InterventionScale,
    ProjectDomain,
    ServiceDepth,
    TaskNature,
    UncertaintyLevel,
)
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.project_mission import (
    EvaluationCriterion,
    MissionConstraint,
    ProjectMission,
    Stakeholder,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.planning_service import update_mission_fields

TASK_NATURE_LABELS = {
    TaskNature.NEW_BUILD: "新建",
    TaskNature.RECONSTRUCTION: "重建",
    TaskNature.RENOVATION: "改造",
    TaskNature.ADAPTIVE_REUSE: "适应性再利用",
    TaskNature.EXPANSION: "扩建",
    TaskNature.RESTORATION: "修复",
    TaskNature.CONSERVATION: "保护",
    TaskNature.URBAN_RENEWAL: "城市更新",
    TaskNature.RESEARCH: "研究",
    TaskNature.PLANNING: "策划",
    TaskNature.CONSULTING: "咨询",
    TaskNature.ASSESSMENT: "评估",
    TaskNature.STRATEGY: "策略",
    TaskNature.DESIGN_REVIEW: "设计评审",
    TaskNature.PRESENTATION_SYNTHESIS: "汇报综合",
    TaskNature.TECHNICAL_STUDY: "技术专题",
    TaskNature.OTHER: "其他",
}

SCALE_LABELS = {
    InterventionScale.REGION: "区域",
    InterventionScale.CITY: "城市",
    InterventionScale.DISTRICT: "片区",
    InterventionScale.CAMPUS: "园区/校园",
    InterventionScale.VILLAGE: "村庄",
    InterventionScale.SITE: "场地",
    InterventionScale.BUILDING_COMPLEX: "建筑群",
    InterventionScale.BUILDING: "单体建筑",
    InterventionScale.FLOOR: "楼层",
    InterventionScale.SPACE: "空间",
    InterventionScale.COMPONENT: "构件/细部",
    InterventionScale.SYSTEM: "系统",
}

DEPTH_LABELS = {
    ServiceDepth.TASK_INTERPRETATION: "任务解读",
    ServiceDepth.INFORMATION_COLLECTION: "资料收集",
    ServiceDepth.PRELIMINARY_RESEARCH: "前期研究",
    ServiceDepth.PROJECT_DIAGNOSIS: "项目诊断",
    ServiceDepth.FEASIBILITY: "可行性",
    ServiceDepth.PROGRAMMING: "功能策划",
    ServiceDepth.CONCEPT_PLANNING: "概念策划",
    ServiceDepth.CONCEPT_DESIGN: "概念设计",
    ServiceDepth.SCHEMATIC_SUPPORT: "方案支持",
    ServiceDepth.CASE_STUDY: "案例研究",
    ServiceDepth.TECHNICAL_PROPOSAL: "技术建议",
    ServiceDepth.IMPLEMENTATION_STRATEGY: "实施策略",
    ServiceDepth.DECISION_SUPPORT: "决策支持",
    ServiceDepth.PRESENTATION_PRODUCTION: "汇报制作",
}

DOMAIN_LABELS = {
    ProjectDomain.ARCHITECTURE: "建筑",
    ProjectDomain.URBAN: "城市",
    ProjectDomain.LANDSCAPE: "景观",
    ProjectDomain.INTERIOR: "室内",
    ProjectDomain.HERITAGE: "遗产",
    ProjectDomain.HEALTHCARE: "医疗",
    ProjectDomain.EDUCATION: "教育",
    ProjectDomain.CULTURE: "文化",
    ProjectDomain.HOUSING: "居住",
    ProjectDomain.COMMERCIAL: "商业",
    ProjectDomain.INDUSTRIAL: "工业",
    ProjectDomain.TRANSPORT: "交通",
    ProjectDomain.SUSTAINABILITY: "可持续",
    ProjectDomain.OPERATIONS: "运营",
    ProjectDomain.OTHER: "其他",
}

NARRATIVE_MODE_LABELS = {
    ArchitecturalNarrativeMode.DECISION_FIRST: "决策优先",
    ArchitecturalNarrativeMode.PROBLEM_SOLUTION: "问题解决",
    ArchitecturalNarrativeMode.EVIDENCE_ARGUMENT: "证据论证",
    ArchitecturalNarrativeMode.DESIGN_PROCESS: "设计过程",
    ArchitecturalNarrativeMode.OPTION_COMPARISON: "方案比较",
    ArchitecturalNarrativeMode.TECHNICAL_BRIEFING: "技术简报",
    ArchitecturalNarrativeMode.PHASED_IMPLEMENTATION: "分期实施",
    ArchitecturalNarrativeMode.PUBLIC_STORYTELLING: "公众叙事",
}

UNCERTAINTY_LABELS = {
    UncertaintyLevel.LOW: "低",
    UncertaintyLevel.MEDIUM: "中",
    UncertaintyLevel.HIGH: "高",
    UncertaintyLevel.CRITICAL: "关键",
}


def _lines_to_list(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _list_to_lines(items: list[str]) -> str:
    return "\n".join(items)


def _stakeholders_to_text(items: list[Stakeholder]) -> str:
    lines: list[str] = []
    for item in items:
        concerns = "、".join(item.concerns)
        lines.append(f"{item.name} | {item.role} | {concerns}")
    return "\n".join(lines)


def _parse_stakeholders(text: str) -> list[Stakeholder]:
    result: list[Stakeholder] = []
    for line in _lines_to_list(text):
        parts = [part.strip() for part in line.split("|")]
        name = parts[0] if parts else ""
        role = parts[1] if len(parts) > 1 and parts[1] else "相关方"
        concerns_raw = parts[2] if len(parts) > 2 else ""
        concerns = [c.strip() for c in concerns_raw.replace("、", ",").split(",") if c.strip()]
        if name:
            result.append(Stakeholder(name=name, role=role, concerns=concerns))
    return result


def _constraints_to_text(items: list[MissionConstraint]) -> str:
    return "\n".join(f"{item.name} | {item.value} | {item.importance}" for item in items)


def _parse_constraints(text: str) -> list[MissionConstraint]:
    result: list[MissionConstraint] = []
    for line in _lines_to_list(text):
        parts = [part.strip() for part in line.split("|")]
        name = parts[0] if parts else ""
        value = parts[1] if len(parts) > 1 else ""
        importance = parts[2] if len(parts) > 2 and parts[2] else "medium"
        if name and value:
            result.append(MissionConstraint(name=name, value=value, importance=importance))
    return result


def _criteria_to_text(items: list[EvaluationCriterion]) -> str:
    lines: list[str] = []
    for item in items:
        weight = "" if item.weight is None else str(item.weight)
        lines.append(f"{item.name} | {item.description} | {weight}")
    return "\n".join(lines)


def _parse_criteria(text: str) -> list[EvaluationCriterion]:
    result: list[EvaluationCriterion] = []
    for line in _lines_to_list(text):
        parts = [part.strip() for part in line.split("|")]
        name = parts[0] if parts else ""
        description = parts[1] if len(parts) > 1 else ""
        weight: float | None = None
        if len(parts) > 2 and parts[2]:
            try:
                weight = float(parts[2])
            except ValueError:
                weight = None
        if name and description:
            result.append(
                EvaluationCriterion(name=name, description=description, weight=weight)
            )
    return result


def _default_design_intent(mission: ProjectMission) -> DesignIntent:
    return mission.design_intent or DesignIntent()


def _truncate_statement(statement: str, *, max_chars: int = 160) -> str:
    text = " ".join(statement.strip().split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _render_research_knowledge_preview(project_id: UUID, *, key_prefix: str) -> None:
    from archium.application.project_knowledge_service import ProjectKnowledgeService

    with get_session() as session:
        items = ProjectKnowledgeService(session).list_research_knowledge_items(
            project_id,
            pending_only=True,
            limit=5,
        )

    if not items:
        return

    st.markdown("**公开研究摘要（待确认）**")
    for item in items:
        summary = _truncate_statement(item.statement)
        st.markdown(f"- {summary}")
        if item.source_citations:
            citation = item.source_citations[0]
            if citation.url:
                title = citation.source_title or citation.url
                st.caption(f"来源：{title}")
        cols = st.columns(2)
        if cols[0].button("确认", key=f"{key_prefix}_confirm_research_{item.id}"):
            with get_session() as session:
                ProjectKnowledgeService(session).confirm_item(item.id)
                session.commit()
            st.rerun()
        if cols[1].button("驳回", key=f"{key_prefix}_reject_research_{item.id}"):
            with get_session() as session:
                ProjectKnowledgeService(session).reject_item(item.id)
                session.commit()
            st.rerun()


def _render_mission_reapproval_prompt(mission: ProjectMission, *, key_prefix: str) -> None:
    from archium.application.project_mission_service import (
        ProjectMissionService,
        is_mission_approval_current,
    )
    from archium.domain.enums import ApprovalStatus
    from archium.infrastructure.llm.factory import create_llm_provider
    from archium.ui.llm_settings import get_ui_effective_settings
    from archium.ui.planning_service import approve_mission_and_continue

    if is_mission_approval_current(mission):
        return

    if mission.approval_status == ApprovalStatus.APPROVED:
        st.warning("任务理解内容已变更，审批已失效。请重新批准后再继续下游规划。")
    else:
        st.info("建议批准任务理解，以便进入工作路径与汇报生成。")

    settings = get_ui_effective_settings()
    workflow_run_id = st.session_state.get("planning_workflow_run_id")
    approve_col, continue_col = st.columns(2)

    if approve_col.button(
        "批准任务理解",
        key=f"{key_prefix}_approve_mission",
        use_container_width=True,
    ):
        try:
            with get_session() as session:
                ProjectMissionService(
                    session,
                    create_llm_provider(settings),
                    settings=settings,
                ).approve_mission(mission.id, note="研究写回后重新批准")
                session.commit()
            st.success("任务理解已批准。")
            st.rerun()
        except WorkflowError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(format_user_error(exc))

    if workflow_run_id and continue_col.button(
        "批准并继续规划",
        key=f"{key_prefix}_approve_mission_continue",
        use_container_width=True,
    ):
        try:
            with get_session() as session:
                approve_mission_and_continue(
                    session,
                    UUID(str(workflow_run_id)),
                    note="研究写回后重新批准",
                    settings=settings,
                )
                session.commit()
            st.success("任务理解已批准，规划工作流已继续。")
            st.rerun()
        except WorkflowError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(format_user_error(exc))


def _render_written_back_research_summary(mission: ProjectMission, *, key_prefix: str) -> None:
    from archium.application.mission_research_enrichment_service import (
        MissionResearchEnrichmentService,
    )
    from archium.infrastructure.llm.factory import create_llm_provider
    from archium.ui.llm_settings import get_ui_effective_settings

    settings = get_ui_effective_settings()
    with get_session() as session:
        written = MissionResearchEnrichmentService(
            session,
            create_llm_provider(settings) if settings.llm_configured else None,
            settings=settings,
        ).list_written_back_items(mission.id)

    if not written:
        return

    st.markdown("**已写回任务理解**")
    for item in written[:5]:
        st.markdown(f"- {_truncate_statement(item.statement)}")
    if len(written) > 5:
        st.caption(f"另有 {len(written) - 5} 条，见工作台「资料与事实」。")


def _render_mission_revision_action(mission: ProjectMission, *, key_prefix: str) -> None:
    from archium.application.mission_research_enrichment_service import (
        MissionResearchEnrichmentService,
    )
    from archium.infrastructure.llm.factory import create_llm_provider
    from archium.ui.llm_settings import get_ui_effective_settings

    settings = get_ui_effective_settings()
    if not settings.llm_configured:
        return

    with get_session() as session:
        service = MissionResearchEnrichmentService(
            session,
            create_llm_provider(settings),
            settings=settings,
        )
        if not service.list_written_back_items(mission.id):
            return

    if st.button(
        "AI 修订任务理解",
        key=f"{key_prefix}_revise_mission_research",
        use_container_width=True,
        help="基于已写回公开研究，轻量更新任务陈述与开放问题。",
    ):
        try:
            with get_session() as session:
                service = MissionResearchEnrichmentService(
                    session,
                    create_llm_provider(settings),
                    settings=settings,
                )
                result = service.revise_mission_from_written_research(mission.id)
                session.commit()
            st.success("已根据公开研究修订任务理解。")
            if result.needs_reapproval:
                st.warning("任务理解审批已失效，请重新批准。")
            st.rerun()
        except WorkflowError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(format_user_error(exc))


def _render_research_enrichment_action(mission: ProjectMission, *, key_prefix: str) -> None:
    from archium.application.mission_research_enrichment_service import (
        MissionResearchEnrichmentService,
    )
    from archium.infrastructure.llm.factory import create_llm_provider
    from archium.ui.llm_settings import get_ui_effective_settings

    settings = get_ui_effective_settings()
    with get_session() as session:
        pending = MissionResearchEnrichmentService(
            session,
            create_llm_provider(settings) if settings.llm_configured else None,
            settings=settings,
        ).list_pending_items(mission.id)

    if not pending:
        return

    st.caption(f"已有 {len(pending)} 条已确认研究可写回任务理解。")
    if st.button(
        f"写回任务理解（{len(pending)} 条）",
        key=f"{key_prefix}_enrich_mission_research",
        use_container_width=True,
    ):
        try:
            with get_session() as session:
                service = MissionResearchEnrichmentService(
                    session,
                    create_llm_provider(settings) if settings.llm_configured else None,
                    settings=settings,
                )
                result = service.enrich_mission(mission.id)
                session.commit()
            mode = "AI 整合" if result.used_llm else "追加"
            st.success(f"已将 {result.items_enriched} 条公开研究写回任务理解（{mode}）。")
            if result.needs_reapproval:
                st.warning("任务理解审批已失效，请重新批准。")
            for warning in result.warnings:
                st.warning(warning)
            st.rerun()
        except WorkflowError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(format_user_error(exc))


def _render_autonomous_research_section(mission: ProjectMission, *, key_prefix: str) -> None:
    from archium.application.autonomous_research_service import AutonomousResearchService
    from archium.application.research_topics import collect_mission_research_topics
    from archium.application.web_research_settings_service import (
        WebResearchSettingsService,
        apply_web_research_preferences,
    )
    from archium.infrastructure.llm.factory import create_llm_provider
    from archium.infrastructure.research.web_search.service import WebResearchSearchService
    from archium.ui.llm_settings import get_ui_effective_settings
    from archium.ui.web_research_settings import session_tavily_api_key, tavily_credential_status

    topics = collect_mission_research_topics(mission)
    if not topics:
        return

    st.markdown("**待研究项**")
    for topic in topics:
        st.markdown(f"- {topic}")

    _render_research_knowledge_preview(mission.project_id, key_prefix=key_prefix)
    _render_research_enrichment_action(mission, key_prefix=key_prefix)
    _render_written_back_research_summary(mission, key_prefix=key_prefix)
    _render_mission_revision_action(mission, key_prefix=key_prefix)
    _render_mission_reapproval_prompt(mission, key_prefix=key_prefix)

    st.caption("确认后的公开资料可 enrich 任务理解与汇报；完整列表见工作台「资料与事实」。")
    settings = get_ui_effective_settings()
    if not settings.llm_configured:
        st.warning("配置 LLM 后可启动自主研究。")
        return

    with get_session() as session:
        prefs = WebResearchSettingsService(session).get_preferences(base_settings=settings)
    effective_settings = apply_web_research_preferences(settings, prefs)

    if not prefs.enabled:
        st.warning("联网研究已在设置中关闭。")
        return

    tavily_configured, _, _ = tavily_credential_status()
    if effective_settings.web_research_provider == "tavily":
        if tavily_configured or (effective_settings.tavily_api_key or "").strip():
            st.caption("联网检索：Tavily")
        else:
            st.caption("联网检索：DuckDuckGo（未配置 Tavily，可在设置页配置 API Key）")
    else:
        st.caption("联网检索：DuckDuckGo")

    if st.button(
        "启动自主研究（写入公开资料）",
        key=f"{key_prefix}_autonomous_research",
        use_container_width=True,
    ):
        try:
            with get_session() as session:
                service = AutonomousResearchService(
                    session,
                    create_llm_provider(settings),
                    settings=effective_settings,
                    web_research=WebResearchSearchService(
                        effective_settings,
                        session_tavily_api_key=session_tavily_api_key(),
                    ),
                )
                result = service.research_for_mission(mission.id)
                session.commit()
            st.success(
                f"已生成 {len(result.items)} 条公开研究摘要。"
                + (
                    f"（联网检索 {result.search_hit_count} 条，来源：{result.search_provider}）"
                    if result.search_hit_count and result.search_provider
                    else ""
                )
            )
            for warning in result.warnings:
                st.warning(warning)
            st.rerun()
        except WorkflowError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(format_user_error(exc))


def render_mission_panel(mission: ProjectMission, *, key_prefix: str = "mission") -> None:
    """Render structured mission understanding with per-field editing."""
    st.markdown("#### 我对任务的理解")
    st.caption(f"{mission.title} · v{mission.version} · 置信度 {mission.confidence:.0%}")
    st.caption("可纠正 AI 对任务性质、服务深度、利益相关方等关键分类，避免误判无法回改。")

    intent = _default_design_intent(mission)
    from archium.application.research_topics import collect_mission_research_topics

    research_topics = collect_mission_research_topics(mission)
    has_design_block = (
        mission.design_intent is not None or intent.theme or intent.problem_statement
    )
    if has_design_block:
        with st.expander("设计使命", expanded=mission.design_intent is not None):
            st.caption("概念探索的核心：问题、社会文化语境、目标体验与待研究项。")
            if intent.working_assumptions:
                st.markdown("**工作假设（待确认）**")
                for item in intent.working_assumptions:
                    st.markdown(f"- {item}")
            if research_topics:
                _render_autonomous_research_section(mission, key_prefix=key_prefix)
    elif research_topics:
        with st.expander("自主研究", expanded=True):
            _render_autonomous_research_section(mission, key_prefix=key_prefix)

    narrative_suggestion = suggest_narrative_mode(mission)
    st.info(
        f"建议叙事模式：{NARRATIVE_MODE_LABELS[narrative_suggestion.mode]}\n\n"
        f"原因：{narrative_suggestion.reason}"
    )

    with st.form(f"{key_prefix}_edit_form"):
        title = st.text_input("标题", value=mission.title)
        task_statement = st.text_area("任务陈述", value=mission.task_statement, height=90)

        nature_options = list(TASK_NATURE_LABELS.keys())
        selected_natures = st.multiselect(
            "任务性质（可多选）",
            options=nature_options,
            default=[item for item in mission.task_natures if item in TASK_NATURE_LABELS],
            format_func=lambda item: TASK_NATURE_LABELS.get(item, item.value),
        )
        domain_options = list(DOMAIN_LABELS.keys())
        selected_domains = st.multiselect(
            "领域（可多选）",
            options=domain_options,
            default=[item for item in mission.domains if item in DOMAIN_LABELS],
            format_func=lambda item: DOMAIN_LABELS.get(item, item.value),
        )
        scale_options = list(SCALE_LABELS.keys())
        selected_scales = st.multiselect(
            "干预尺度（可多选）",
            options=scale_options,
            default=[item for item in mission.intervention_scales if item in SCALE_LABELS],
            format_func=lambda item: SCALE_LABELS.get(item, item.value),
        )
        depth_options = list(DEPTH_LABELS.keys())
        selected_depths = st.multiselect(
            "服务深度（可多选）",
            options=depth_options,
            default=[
                item for item in mission.requested_service_depths if item in DEPTH_LABELS
            ],
            format_func=lambda item: DEPTH_LABELS.get(item, item.value),
        )
        uncertainty = st.selectbox(
            "不确定性",
            options=list(UNCERTAINTY_LABELS.keys()),
            index=list(UNCERTAINTY_LABELS.keys()).index(mission.uncertainty_level)
            if mission.uncertainty_level in UNCERTAINTY_LABELS
            else 1,
            format_func=lambda item: UNCERTAINTY_LABELS.get(item, item.value),
        )
        narrative_options = list(NARRATIVE_MODE_LABELS)
        narrative_mode = st.selectbox(
            "叙事模式（决定内容组织，不决定视觉风格）",
            options=narrative_options,
            index=narrative_options.index(mission.narrative_mode)
            if mission.narrative_mode in narrative_options
            else narrative_options.index(narrative_suggestion.mode),
            format_func=lambda item: NARRATIVE_MODE_LABELS[item],
        )

        st.markdown("##### 设计使命")
        intent_theme = st.text_input("主题", value=intent.theme, key=f"{key_prefix}_intent_theme")
        intent_problem = st.text_area(
            "问题陈述",
            value=intent.problem_statement,
            height=70,
            key=f"{key_prefix}_intent_problem",
        )
        col_intent_a, col_intent_b = st.columns(2)
        with col_intent_a:
            intent_social = st.text_area(
                "社会背景",
                value=intent.social_background,
                height=70,
                key=f"{key_prefix}_intent_social",
            )
            intent_users = st.text_area(
                "目标用户（每行一项）",
                value=_list_to_lines(intent.target_users),
                height=70,
                key=f"{key_prefix}_intent_users",
            )
            intent_core_q = st.text_area(
                "核心追问（每行一项）",
                value=_list_to_lines(intent.core_questions),
                height=70,
                key=f"{key_prefix}_intent_core_q",
            )
        with col_intent_b:
            intent_cultural = st.text_area(
                "文化语境",
                value=intent.cultural_context,
                height=70,
                key=f"{key_prefix}_intent_cultural",
            )
            intent_experience = st.text_area(
                "期望体验",
                value=intent.desired_experience,
                height=70,
                key=f"{key_prefix}_intent_experience",
            )
            intent_research = st.text_area(
                "待研究项（每行一项）",
                value=_list_to_lines(intent.research_needed),
                height=70,
                key=f"{key_prefix}_intent_research",
            )
        intent_assumptions = st.text_area(
            "工作假设（每行一项，待后续确认）",
            value=_list_to_lines(intent.working_assumptions),
            height=70,
            key=f"{key_prefix}_intent_assumptions",
        )

        current_situation = st.text_area(
            "当前情况", value=mission.current_situation or "", height=70
        )
        col_a, col_b = st.columns(2)
        with col_a:
            primary_problems = st.text_area(
                "主要问题（每行一项）",
                value=_list_to_lines(mission.primary_problems),
                height=100,
            )
            in_scope = st.text_area(
                "工作范围（每行一项）",
                value=_list_to_lines(mission.in_scope),
                height=100,
            )
            decisions_required = st.text_area(
                "关键决策（每行一项）",
                value=_list_to_lines(mission.decisions_required),
                height=80,
            )
        with col_b:
            desired_changes = st.text_area(
                "希望产生的改变（每行一项）",
                value=_list_to_lines(mission.desired_changes),
                height=100,
            )
            out_of_scope = st.text_area(
                "不包含内容（每行一项）",
                value=_list_to_lines(mission.out_of_scope),
                height=100,
            )
            design_questions = st.text_area(
                "设计命题（每行一项）",
                value=_list_to_lines(mission.design_questions),
                height=80,
            )

        stakeholders_text = st.text_area(
            "利益相关方（每行：姓名 | 角色 | 关注点，逗号/顿号分隔）",
            value=_stakeholders_to_text(mission.stakeholders),
            height=90,
        )
        constraints_text = st.text_area(
            "已知约束（每行：名称 | 值 | 重要性）",
            value=_constraints_to_text(mission.known_constraints),
            height=90,
        )
        criteria_text = st.text_area(
            "评价标准（每行：名称 | 描述 | 权重可选）",
            value=_criteria_to_text(mission.evaluation_criteria),
            height=90,
        )

        saved = st.form_submit_button("保存修改", use_container_width=True)

    if saved:
        patch = MissionPatch(
            title=title.strip() or None,
            task_statement=task_statement.strip() or None,
            design_intent=DesignIntent(
                theme=intent_theme.strip(),
                problem_statement=intent_problem.strip(),
                social_background=intent_social.strip(),
                cultural_context=intent_cultural.strip(),
                target_users=_lines_to_list(intent_users),
                desired_experience=intent_experience.strip(),
                core_questions=_lines_to_list(intent_core_q),
                research_needed=_lines_to_list(intent_research),
                working_assumptions=_lines_to_list(intent_assumptions),
            ),
            current_situation=current_situation.strip() or None,
            primary_problems=_lines_to_list(primary_problems),
            desired_changes=_lines_to_list(desired_changes),
            in_scope=_lines_to_list(in_scope),
            out_of_scope=_lines_to_list(out_of_scope),
            decisions_required=_lines_to_list(decisions_required),
            design_questions=_lines_to_list(design_questions),
            task_natures=selected_natures,
            domains=selected_domains,
            intervention_scales=selected_scales,
            requested_service_depths=selected_depths,
            uncertainty_level=uncertainty,
            narrative_mode=narrative_mode,
            stakeholders=_parse_stakeholders(stakeholders_text),
            known_constraints=_parse_constraints(constraints_text),
            evaluation_criteria=_parse_criteria(criteria_text),
        )
        try:
            with get_session() as session:
                update_mission_fields(session, mission.id, patch)
            st.success("任务理解已更新。")
            st.rerun()
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        except Exception as exc:
            st.error(format_user_error(exc))

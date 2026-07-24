"""Resolve and describe the four Architectural Workspace modes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.project_context_builder import build_project_context
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.enums import (
    ArchitecturalWorkspaceMode,
    ConceptDirectionStatus,
    ProjectOriginMode,
)
from archium.domain.project import Project
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    ConceptDirectionRepository,
    ProjectRepository,
)

_SESSION_OVERRIDE_KEY = "architectural_workspace_mode_override"


@dataclass(frozen=True)
class WorkspaceModeProfile:
    """UI-facing description of the active workspace mode."""

    mode: ArchitecturalWorkspaceMode
    title: str
    caption: str
    focus: str
    primary_page_key: str
    suggested_actions: tuple[str, ...]
    stage_captions: dict[str, str]


_PROFILES: dict[ArchitecturalWorkspaceMode, WorkspaceModeProfile] = {
    ArchitecturalWorkspaceMode.EXISTING_PROJECT: WorkspaceModeProfile(
        mode=ArchitecturalWorkspaceMode.EXISTING_PROJECT,
        title="已有项目",
        caption="资料驱动：上传图纸与说明，整理事实后再形成汇报。",
        focus="事实账本与证据完备",
        primary_page_key="materials",
        suggested_actions=(
            "上传 PDF / 图纸 / 照片",
            "确认事实账本",
            "进入项目任务与大纲",
        ),
        stage_captions={
            "materials": "上传并整理项目资料与事实。",
            "outline": "基于资料确认汇报结构与必出内容。",
            "generate": "生成页面内容与版式预览。",
            "edit": "在工作室调整页面与图文。",
            "deliver": "导出并检查正式交付。",
        },
    ),
    ArchitecturalWorkspaceMode.CONCEPT_EXPLORATION: WorkspaceModeProfile(
        mode=ArchitecturalWorkspaceMode.CONCEPT_EXPLORATION,
        title="概念探索",
        caption="意图驱动：从一句话想法推演方向，再建立设计使命；资料可后续补充。",
        focus="概念方向与设计使命",
        primary_page_key="concept-exploration",
        suggested_actions=(
            "推演 2–3 个概念方向并选定",
            "提交生成设计使命与项目任务",
            "启动自主研究 enrich 背景",
        ),
        stage_captions={
            "materials": "可选：补充研究资料 enrich 概念。",
            "outline": "围绕设计使命确认概念汇报结构。",
            "generate": "生成概念草稿预览（正式交付仍需资料）。",
            "edit": "调整概念叙事与版式。",
            "deliver": "草稿可导出；正式交付前请补资料。",
        },
    ),
    ArchitecturalWorkspaceMode.RESEARCH_PROGRAMMING: WorkspaceModeProfile(
        mode=ArchitecturalWorkspaceMode.RESEARCH_PROGRAMMING,
        title="研究策划",
        caption="决策驱动：梳理定位、未知项与投资人沟通路径，未必先做方案 PPT。",
        focus="问题清单、工作路径与备忘录",
        primary_page_key="project-mission",
        suggested_actions=(
            "分析策划任务与决策背景",
            "生成问题清单 / 备忘录 / 工作大纲",
            "需要时再启动概念汇报",
        ),
        stage_captions={
            "materials": "可选：补充政策、市场或业主资料。",
            "outline": "若选汇报成果，确认沟通提纲结构。",
            "generate": "生成汇报或继续非汇报成果。",
            "edit": "调整沟通材料。",
            "deliver": "导出备忘录路径产物或汇报。",
        },
    ),
    ArchitecturalWorkspaceMode.DESIGN_ITERATION: WorkspaceModeProfile(
        mode=ArchitecturalWorkspaceMode.DESIGN_ITERATION,
        title="设计迭代",
        caption="方案比较：在同一 Mission 下推演、选择概念方向，并注入汇报链。",
        focus="多方向草稿与当前选中方向",
        primary_page_key="project-mission",
        suggested_actions=(
            "推演 2–3 个概念方向",
            "选中当前方向并写回设计使命",
            "进入大纲 / 生成，带入【当前概念方向】",
        ),
        stage_captions={
            "materials": "可选：用研究资料支撑方向比较。",
            "outline": "按选中方向组织大纲与核心信息。",
            "generate": "生成体现当前方向的预览。",
            "edit": "迭代叙事与视觉表达。",
            "deliver": "导出比较后的概念稿。",
        },
    ),
}


def profile_for(mode: ArchitecturalWorkspaceMode) -> WorkspaceModeProfile:
    return _PROFILES[mode]


def origin_to_default_workspace_mode(
    origin: ProjectOriginMode,
) -> ArchitecturalWorkspaceMode:
    mapping = {
        ProjectOriginMode.EXISTING_PROJECT: ArchitecturalWorkspaceMode.EXISTING_PROJECT,
        ProjectOriginMode.CONCEPT_EXPLORATION: ArchitecturalWorkspaceMode.CONCEPT_EXPLORATION,
        ProjectOriginMode.RESEARCH_PROGRAMMING: ArchitecturalWorkspaceMode.RESEARCH_PROGRAMMING,
    }
    return mapping.get(origin, ArchitecturalWorkspaceMode.EXISTING_PROJECT)


def workspace_mode_from_context(
    context: ProjectContext,
    *,
    origin: ProjectOriginMode,
) -> ArchitecturalWorkspaceMode:
    """Route workspace from knowledge state + NBA, not origin alone."""
    workflow = context.recommended_workflow
    page = context.primary_page_key
    if workflow == RecommendedWorkflow.DESIGN:
        return ArchitecturalWorkspaceMode.DESIGN_ITERATION
    if workflow == RecommendedWorkflow.DELIVER:
        return ArchitecturalWorkspaceMode.EXISTING_PROJECT
    if workflow == RecommendedWorkflow.MATERIALS:
        return ArchitecturalWorkspaceMode.EXISTING_PROJECT
    if workflow == RecommendedWorkflow.EXPLORE:
        return ArchitecturalWorkspaceMode.CONCEPT_EXPLORATION
    if workflow in (RecommendedWorkflow.RESEARCH, RecommendedWorkflow.MISSION):
        if origin == ProjectOriginMode.RESEARCH_PROGRAMMING:
            return ArchitecturalWorkspaceMode.RESEARCH_PROGRAMMING
        if page == "materials":
            return ArchitecturalWorkspaceMode.EXISTING_PROJECT
        return ArchitecturalWorkspaceMode.CONCEPT_EXPLORATION
    return origin_to_default_workspace_mode(origin)


class WorkspaceModeService:
    """Derive the active Architectural Workspace mode for a project."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._projects = ProjectRepository(session)
        self._missions = MissionRepository(session)
        self._directions = ConceptDirectionRepository(session)

    def resolve_mode(
        self,
        project_id: UUID,
        *,
        override: ArchitecturalWorkspaceMode | None = None,
    ) -> ArchitecturalWorkspaceMode:
        project = self._require_project(project_id)
        if override is not None:
            if not self._override_allowed(project.origin_mode, override):
                raise WorkflowError(
                    f"当前项目起源（{project.origin_mode.value}）不能切换到 {override.value}"
                )
            return override

        if self._has_concept_directions(project_id):
            return ArchitecturalWorkspaceMode.DESIGN_ITERATION

        context = build_project_context(self._session, project)
        if context is not None:
            return workspace_mode_from_context(
                context,
                origin=project.origin_mode,
            )

        return origin_to_default_workspace_mode(project.origin_mode)

    def resolve_profile(
        self,
        project_id: UUID,
        *,
        override: ArchitecturalWorkspaceMode | None = None,
    ) -> WorkspaceModeProfile:
        return profile_for(self.resolve_mode(project_id, override=override))

    def resolve_primary_page_key(
        self,
        project_id: UUID,
        *,
        override: ArchitecturalWorkspaceMode | None = None,
    ) -> str:
        """Primary navigation page — prefers ProjectContext over origin default."""
        context = build_project_context(self._session, project_id)
        if context is not None and context.primary_page_key:
            return context.primary_page_key
        return self.resolve_profile(project_id, override=override).primary_page_key

    def available_modes(self, project_id: UUID) -> list[ArchitecturalWorkspaceMode]:
        project = self._require_project(project_id)
        base = origin_to_default_workspace_mode(project.origin_mode)
        modes = [base]
        if base in {
            ArchitecturalWorkspaceMode.CONCEPT_EXPLORATION,
            ArchitecturalWorkspaceMode.RESEARCH_PROGRAMMING,
        }:
            modes.append(ArchitecturalWorkspaceMode.DESIGN_ITERATION)
        return modes

    def _has_concept_directions(self, project_id: UUID) -> bool:
        missions = self._missions.list_missions_by_project(project_id)
        if not missions:
            return False
        for direction in self._directions.list_by_mission(missions[0].id):
            if direction.status != ConceptDirectionStatus.ARCHIVED:
                return True
        return False

    def _override_allowed(
        self,
        origin: ProjectOriginMode,
        override: ArchitecturalWorkspaceMode,
    ) -> bool:
        if override == origin_to_default_workspace_mode(origin):
            return True
        if override == ArchitecturalWorkspaceMode.DESIGN_ITERATION:
            return origin.skips_default_clarification
        return False

    def _require_project(self, project_id: UUID) -> Project:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise WorkflowError(f"项目 {project_id} 不存在")
        return project


def session_mode_override_key(project_id: UUID) -> str:
    return f"{_SESSION_OVERRIDE_KEY}_{project_id}"

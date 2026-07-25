"""Design process pointer — ConceptDirection / VisualConceptBrief aware."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import (
    ApprovalStatus,
    ConceptDirectionStatus,
    ExplorationSessionStatus,
)
from archium.domain.exploration_session import ExplorationSession
from archium.domain.process import (
    DesignProcessFocus,
    ProcessPointer,
    ProjectProcessKind,
    ProjectProcessPhase,
)
from archium.domain.project_mission import ProjectMission
from archium.domain.visual.visual_concept_brief import VisualConceptBrief


def build_design_pointer(session: Session, project_id: UUID) -> ProcessPointer:
    """Derive Design process focus from exploration → direction → visual → mission."""
    from archium.infrastructure.database.mission_repositories import MissionRepository
    from archium.infrastructure.database.repositories import (
        ConceptDirectionRepository,
        ExplorationSessionRepository,
        VisualConceptBriefRepository,
    )

    explorations = ExplorationSessionRepository(session).list_by_project(project_id)
    missions = MissionRepository(session).list_missions_by_project(project_id)
    directions_repo = ConceptDirectionRepository(session)
    briefs_repo = VisualConceptBriefRepository(session)
    now = datetime.now(UTC)

    if explorations:
        latest = max(explorations, key=lambda item: item.updated_at)
        directions = directions_repo.list_by_exploration(latest.id)
        selected = _resolve_selected_direction(directions_repo, latest, directions)
        if latest.status == ExplorationSessionStatus.COMMITTED:
            return _committed_pointer(latest, selected, missions, now)
        if selected is not None:
            brief = briefs_repo.get_latest_for_direction(selected.id)
            return _pointer_from_selected_direction(
                exploration=latest,
                selected=selected,
                directions=directions,
                brief=brief,
                now=now,
            )
        if directions:
            return ProcessPointer(
                kind=ProjectProcessKind.DESIGN,
                phase=ProjectProcessPhase.ACTIVE,
                focus=DesignProcessFocus.COMPARING_DIRECTIONS.value,
                active_id=latest.id,
                secondary_id=directions[0].id,
                label=f"比较 {len(directions)} 个概念方向",
                detail="；".join(d.title for d in directions[:3]),
                updated_at=latest.updated_at,
            )
        if latest.status == ExplorationSessionStatus.DIRECTION_SELECTED:
            return ProcessPointer(
                kind=ProjectProcessKind.DESIGN,
                phase=ProjectProcessPhase.READY,
                focus=DesignProcessFocus.DIRECTION_SELECTED.value,
                active_id=latest.id,
                secondary_id=latest.selected_direction_id,
                label="方向已选定",
                detail="可示意出图或提交 Mission",
                updated_at=latest.updated_at,
            )
        return ProcessPointer(
            kind=ProjectProcessKind.DESIGN,
            phase=ProjectProcessPhase.ACTIVE,
            focus=DesignProcessFocus.EXPLORING.value,
            active_id=latest.id,
            label="概念探索中",
            detail="尚未生成方向草稿",
            updated_at=latest.updated_at,
        )

    if missions:
        mission = missions[0]
        mission_dirs = directions_repo.list_by_mission(mission.id)
        selected = next(
            (d for d in mission_dirs if d.status == ConceptDirectionStatus.SELECTED),
            None,
        )
        if selected is not None:
            brief = briefs_repo.get_latest_for_direction(selected.id)
            return _pointer_from_selected_direction(
                exploration=None,
                selected=selected,
                directions=mission_dirs,
                brief=brief,
                now=now,
                mission=mission,
            )
        if mission_dirs:
            return ProcessPointer(
                kind=ProjectProcessKind.DESIGN,
                phase=ProjectProcessPhase.ACTIVE,
                focus=DesignProcessFocus.COMPARING_DIRECTIONS.value,
                active_id=mission.id,
                secondary_id=mission_dirs[0].id,
                label=f"Mission 下比较 {len(mission_dirs)} 个方向",
                detail="；".join(d.title for d in mission_dirs[:3]),
                updated_at=getattr(mission, "updated_at", now),
            )
        return _mission_only_pointer(mission, now)

    return ProcessPointer(
        kind=ProjectProcessKind.DESIGN,
        phase=ProjectProcessPhase.IDLE,
        focus=DesignProcessFocus.IDLE.value,
        label="尚未进入设计过程",
        updated_at=now,
    )


def _resolve_selected_direction(
    directions_repo,
    exploration: ExplorationSession,
    directions: list[ConceptDirection],
) -> ConceptDirection | None:
    selected = next(
        (d for d in directions if d.status == ConceptDirectionStatus.SELECTED),
        None,
    )
    if selected is not None:
        return selected
    if exploration.selected_direction_id is None:
        return None
    loaded = directions_repo.get(exploration.selected_direction_id)
    if loaded is None or loaded.status == ConceptDirectionStatus.ARCHIVED:
        return None
    return loaded


def _pointer_from_selected_direction(
    *,
    exploration: ExplorationSession | None,
    selected: ConceptDirection,
    directions: list[ConceptDirection],
    brief: VisualConceptBrief | None,
    now: datetime,
    mission: ProjectMission | None = None,
) -> ProcessPointer:
    stamp = selected.updated_at
    if brief is not None and brief.updated_at > stamp:
        stamp = brief.updated_at
    if exploration is not None and exploration.updated_at > stamp:
        stamp = exploration.updated_at

    draft_count = sum(
        1 for d in directions if d.status == ConceptDirectionStatus.DRAFT
    )
    peer = f"另有 {draft_count} 个草稿" if draft_count else ""

    if brief is not None and brief.status == "failed":
        return ProcessPointer(
            kind=ProjectProcessKind.DESIGN,
            phase=ProjectProcessPhase.BLOCKED,
            focus=DesignProcessFocus.VISUAL_FAILED.value,
            active_id=selected.id,
            secondary_id=brief.id,
            label=f"出图受阻 · 「{selected.title}」",
            detail=(brief.error_message or "视觉简报出图失败，文字稿仍可用")[:300],
            updated_at=stamp or now,
        )
    if brief is not None and brief.status in {"ready", "imaged"}:
        visual_bit = "已示意出图" if brief.status == "imaged" else "文字简报就绪"
        detail_parts = [visual_bit, f"简报「{brief.title}」"]
        if peer:
            detail_parts.append(peer)
        if mission is not None and mission.approval_status == ApprovalStatus.APPROVED:
            detail_parts.append("可注入 Brief / 汇报")
        return ProcessPointer(
            kind=ProjectProcessKind.DESIGN,
            phase=ProjectProcessPhase.READY,
            focus=DesignProcessFocus.VISUAL_READY.value,
            active_id=selected.id,
            secondary_id=brief.id,
            label=f"视觉就绪 · 「{selected.title}」",
            detail=" · ".join(detail_parts)[:300],
            updated_at=stamp or now,
        )
    if brief is not None and brief.status == "draft":
        return ProcessPointer(
            kind=ProjectProcessKind.DESIGN,
            phase=ProjectProcessPhase.ACTIVE,
            focus=DesignProcessFocus.VISUAL_DRAFT.value,
            active_id=selected.id,
            secondary_id=brief.id,
            label=f"视觉简报草稿 · 「{selected.title}」",
            detail="可继续合成或示意出图",
            updated_at=stamp or now,
        )

    detail_parts = ["可示意出图或提交 Mission"]
    if peer:
        detail_parts.append(peer)
    return ProcessPointer(
        kind=ProjectProcessKind.DESIGN,
        phase=ProjectProcessPhase.READY,
        focus=DesignProcessFocus.DIRECTION_SELECTED.value,
        active_id=selected.id,
        secondary_id=exploration.id if exploration is not None else (
            mission.id if mission is not None else None
        ),
        label=f"已选方向「{selected.title}」",
        detail=" · ".join(detail_parts)[:300],
        updated_at=stamp or now,
    )


def _committed_pointer(
    exploration: ExplorationSession,
    selected: ConceptDirection | None,
    missions: list[ProjectMission],
    now: datetime,
) -> ProcessPointer:
    mission = None
    if exploration.mission_id is not None:
        mission = next((m for m in missions if m.id == exploration.mission_id), None)
    if mission is None and missions:
        mission = missions[0]
    if mission is not None:
        overlay = _mission_only_pointer(mission, now)
        return overlay.model_copy(
            update={
                "secondary_id": selected.id if selected is not None else exploration.id,
                "detail": (
                    f"探索已提交 · {overlay.detail}"
                    if overlay.detail
                    else "探索已提交 Mission"
                )[:300],
                "updated_at": max(exploration.updated_at, overlay.updated_at),
            }
        )
    return ProcessPointer(
        kind=ProjectProcessKind.DESIGN,
        phase=ProjectProcessPhase.COMPLETE,
        focus=DesignProcessFocus.COMMITTED.value,
        active_id=exploration.id,
        secondary_id=selected.id if selected is not None else exploration.mission_id,
        label="探索已提交 Mission",
        detail=f"mission={exploration.mission_id}" if exploration.mission_id else "",
        updated_at=exploration.updated_at or now,
    )


def _mission_only_pointer(mission: ProjectMission, now: datetime) -> ProcessPointer:
    stamp = getattr(mission, "updated_at", now)
    if mission.approval_status == ApprovalStatus.APPROVED:
        return ProcessPointer(
            kind=ProjectProcessKind.DESIGN,
            phase=ProjectProcessPhase.READY,
            focus=DesignProcessFocus.MISSION_APPROVED.value,
            active_id=mission.id,
            label="Mission 已批准",
            detail=mission.title[:80],
            updated_at=stamp,
        )
    if mission.approval_status == ApprovalStatus.REJECTED:
        return ProcessPointer(
            kind=ProjectProcessKind.DESIGN,
            phase=ProjectProcessPhase.BLOCKED,
            focus=DesignProcessFocus.MISSION_CLARIFYING.value,
            active_id=mission.id,
            label="Mission 已驳回",
            detail=mission.title[:80],
            updated_at=stamp,
        )
    return ProcessPointer(
        kind=ProjectProcessKind.DESIGN,
        phase=ProjectProcessPhase.ACTIVE,
        focus=DesignProcessFocus.MISSION_CLARIFYING.value,
        active_id=mission.id,
        label="Mission 澄清中",
        detail=mission.title[:80],
        updated_at=stamp,
    )

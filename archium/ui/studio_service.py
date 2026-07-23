"""UI-facing facade for Presentation Studio."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.content_adaptation_service import ContentAdaptationService
from archium.application.ingestion_service import ImportItemResult
from archium.application.visual.slide_preview_service import SlidePreviewService
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.application.visual.visual_edit_service import VisualEditResult
from archium.config.settings import Settings
from archium.domain.content_adaptation import ContentAdaptationSuggestion
from archium.domain.enums import ProjectType, SlideStatus, SlideType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.render import RenderResult
from archium.domain.revision import EntityRevision
from archium.domain.scene_revision_summary import SceneRevisionRestoreResult
from archium.domain.slide import SlideSpec, build_slide_logical_key
from archium.domain.visual.deck_repair import DeckRepairSuggestion
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.scene_change_proposal import SceneChangeProposal
from archium.domain.visual.slide_capacity_budget import SlideCapacityBudget
from archium.domain.visual.theme_change_proposal import ThemeChangeProposal
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.renderers.pptx_pdf import convert_pptx_to_pdf
from archium.ui.visual_service import (
    PresentationVisualSnapshot,
    SlideVisualSnapshot,
    export_presentation_pptx_from_layout_plans,
    get_presentation_visual_snapshot,
    presentation_has_visual_layout,
)
from archium.ui.workspace_service import (
    ProjectOverview,
    _resolve_runtime_settings,
    create_project,
    get_project_overview,
    import_uploaded_file,
    list_project_presentations,
    list_projects,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StudioPresentationContext:
    """Loaded context for the Studio three-column layout."""

    project: Project
    presentation: Presentation
    snapshot: PresentationVisualSnapshot
    ready_for_export: bool
    slide_count: int
    layout_ready_count: int
    preview_ready_count: int
    warnings: tuple[str, ...] = ()


def list_studio_projects(session: Session) -> list[Project]:
    return list_projects(session)


def list_studio_presentations(session: Session, project_id: UUID) -> list[Presentation]:
    return list_project_presentations(session, project_id)


def create_studio_project(
    session: Session,
    *,
    name: str,
    project_type: ProjectType,
    description: str = "",
) -> Project:
    return create_project(
        session,
        name=name,
        project_type=project_type,
        description=description,
    )


def get_studio_project_overview(session: Session, project_id: UUID) -> ProjectOverview | None:
    return get_project_overview(session, project_id)


def import_studio_file(
    session: Session,
    project_id: UUID,
    *,
    filename: str,
    data: bytes,
    settings: Settings | None = None,
) -> ImportItemResult:
    return import_uploaded_file(
        session,
        project_id,
        filename=filename,
        data=data,
        settings=settings,
    )


def load_studio_context(
    session: Session,
    project_id: UUID,
    presentation_id: UUID,
    *,
    visual_critic_reports: list[dict] | None = None,
    deck_qa_report: dict | None = None,
    preview_paths: list[str] | None = None,
    workflow_output_dir: str | Path | None = None,
) -> StudioPresentationContext | None:
    overview = get_project_overview(session, project_id)
    if overview is None:
        return None

    presentations = list_project_presentations(session, project_id)
    presentation = next((item for item in presentations if item.id == presentation_id), None)
    if presentation is None:
        return None

    snapshot = get_presentation_visual_snapshot(
        session,
        presentation_id,
        visual_critic_reports=visual_critic_reports,
        deck_qa_report=deck_qa_report,
        preview_paths=preview_paths,
    )
    settings = _resolve_runtime_settings(None)
    scene_service = StudioSceneService(session, settings=settings)
    scene_preview_by_index: dict[int, str | None] = {}
    enriched_with_scenes: list[SlideVisualSnapshot] = []
    scene_warnings: list[str] = []
    for index, item in enumerate(snapshot.slides):
        scene_result = None
        if item.layout_plan is not None:
            compile_failed = False
            try:
                scene_result = scene_service.ensure_scene_for_slide(item.slide.id)
            except Exception as exc:
                compile_failed = True
                logger.warning(
                    "ensure_scene_for_slide failed for slide %s: %s",
                    item.slide.id,
                    exc,
                    exc_info=True,
                )
                scene_warnings.append(
                    f"第 {item.slide.order + 1} 页 RenderScene 编译失败：{exc}"
                )
                scene_result = None
            if scene_result is None and not compile_failed:
                scene_warnings.append(
                    f"第 {item.slide.order + 1} 页有版式但未能得到 RenderScene"
                )
        if scene_result is not None:
            scene_preview_by_index[index] = str(scene_result.preview_path)
            enriched_with_scenes.append(
                replace(
                    item,
                    render_scene=scene_result.scene,
                    deferred_scene_repairs=list(scene_result.deferred_repair_findings),
                )
            )
        else:
            enriched_with_scenes.append(item)
    snapshot = replace(snapshot, slides=enriched_with_scenes)

    preview_service = SlidePreviewService(settings)
    existing_preview_by_index = {
        index: item.preview_image for index, item in enumerate(snapshot.slides)
    }
    resolutions = preview_service.resolve_previews(
        presentation_id=presentation_id,
        layout_plans=[item.layout_plan for item in snapshot.slides],
        existing_preview_by_index=existing_preview_by_index,
        render_paths=list(preview_paths or []),
        workflow_output_dir=workflow_output_dir,
        scene_preview_by_index=scene_preview_by_index,
    )
    enriched_slides: list[SlideVisualSnapshot] = []
    for item, resolution in zip(snapshot.slides, resolutions, strict=True):
        enriched_slides.append(
            replace(
                item,
                preview_image=resolution.path,
                preview_kind=resolution.kind,
            )
        )
    snapshot = replace(snapshot, slides=enriched_slides)

    layout_ready_count = sum(1 for item in snapshot.slides if item.layout_plan is not None)
    preview_ready_count = sum(
        1
        for item in snapshot.slides
        if item.preview_image and Path(item.preview_image).is_file()
    )
    ready_for_export = presentation_has_visual_layout(session, presentation_id)

    return StudioPresentationContext(
        project=overview.project,
        presentation=presentation,
        snapshot=snapshot,
        ready_for_export=ready_for_export,
        slide_count=len(snapshot.slides),
        layout_ready_count=layout_ready_count,
        preview_ready_count=preview_ready_count,
        warnings=tuple(scene_warnings),
    )


def get_selected_slide_snapshot(
    context: StudioPresentationContext,
    slide_index: int,
) -> SlideVisualSnapshot | None:
    slides = context.snapshot.slides
    if not slides:
        return None
    index = max(0, min(slide_index, len(slides) - 1))
    return slides[index]


def export_presentation_from_studio(
    session: Session,
    presentation_id: UUID,
    *,
    settings: object | None = None,
    chart_export_mode: object | None = None,
) -> RenderResult:
    return export_presentation_pptx_from_layout_plans(
        session,
        presentation_id,
        settings=settings,  # type: ignore[arg-type]
        chart_export_mode=chart_export_mode,  # type: ignore[arg-type]
    )


def export_presentation_pdf_from_studio(
    session: Session,
    presentation_id: UUID,
    *,
    settings: object | None = None,
) -> RenderResult:
    """Export PDF by rendering Scene PPTX then converting with LibreOffice."""
    pptx_result = export_presentation_from_studio(
        session,
        presentation_id,
        settings=settings,
    )
    pptx_path = pptx_result.editable_pptx_path
    if pptx_path is None:
        raise WorkflowError("PPTX 导出失败，无法继续生成 PDF。")
    pdf_path = convert_pptx_to_pdf(pptx_path, pptx_path.parent)
    if pdf_path is None:
        pptx_result.warnings.append(
            "未检测到 LibreOffice，无法将 PPTX 转为 PDF。请安装 LibreOffice 后重试。"
        )
        return pptx_result
    return RenderResult(
        editable_pptx_path=pptx_path,
        pdf_path=pdf_path,
        warnings=list(pptx_result.warnings),
    )


def add_studio_slide(
    session: Session,
    presentation_id: UUID,
    *,
    after_index: int | None = None,
) -> SlideSpec:
    """Insert a blank slide after ``after_index`` (or append when None)."""
    presentations = PresentationRepository(session)
    slides = presentations.list_slides(presentation_id)
    if not slides:
        chapter_id = "ch1"
        order = 0
    elif after_index is None:
        last = slides[-1]
        chapter_id = last.chapter_id
        order = last.order + 1
    else:
        index = max(0, min(after_index, len(slides) - 1))
        anchor = slides[index]
        chapter_id = anchor.chapter_id
        order = anchor.order + 1
        for slide in reversed(slides):
            if slide.order >= order:
                presentations.save_slide(
                    slide.model_copy(
                        update={
                            "order": slide.order + 1,
                            "logical_key": build_slide_logical_key(
                                slide.chapter_id,
                                slide.order + 1,
                            ),
                        }
                    )
                )

    new_slide = SlideSpec(
        presentation_id=presentation_id,
        chapter_id=chapter_id,
        order=order,
        title="新页面",
        message="请填写本页核心信息。",
        slide_type=SlideType.CONTENT,
        status=SlideStatus.PLANNED,
    )
    return presentations.save_slide(new_slide)


def delete_studio_slide(session: Session, slide_id: UUID) -> None:
    """Delete one slide; raises when it is the last page in the deck."""
    presentations = PresentationRepository(session)
    slide = presentations.get_slide(slide_id)
    if slide is None:
        raise WorkflowError("页面不存在。")
    remaining = presentations.list_slides(slide.presentation_id)
    if len(remaining) <= 1:
        raise WorkflowError("至少保留一页，无法删除。")
    presentations.delete_slide(slide_id)


def reorder_studio_slide(
    session: Session,
    presentation_id: UUID,
    *,
    from_index: int,
    to_index: int,
) -> None:
    """Move one slide from ``from_index`` to ``to_index`` (0-based list positions)."""
    presentations = PresentationRepository(session)
    slides = presentations.list_slides(presentation_id)
    if not slides:
        raise WorkflowError("当前汇报没有页面。")
    if from_index == to_index:
        return

    start = max(0, min(from_index, len(slides) - 1))
    end = max(0, min(to_index, len(slides) - 1))
    reordered = list(slides)
    moving = reordered.pop(start)
    reordered.insert(end, moving)
    for order, slide in enumerate(reordered):
        if slide.order == order:
            continue
        presentations.save_slide(
            slide.model_copy(
                update={
                    "order": order,
                    "logical_key": build_slide_logical_key(slide.chapter_id, order),
                }
            )
        )


def apply_slide_edit_command(session: Session, command: object) -> object:
    """Execute one unified SlideEditCommand."""
    from archium.application.visual.slide_edit_execution_service import SlideEditExecutionService
    from archium.domain.visual.slide_edit_command import SlideEditCommand, SlideEditScope
    from archium.ui.studio.undo_stack import clear_content_redo_stack, clear_visual_redo_stack

    if not isinstance(command, SlideEditCommand):
        raise WorkflowError("无效的编辑命令。")
    if command.scope == SlideEditScope.VISUAL:
        clear_visual_redo_stack(command.slide_id)
    elif command.scope == SlideEditScope.CONTENT:
        clear_content_redo_stack(command.slide_id)
    return SlideEditExecutionService().execute(session, command)


def analyze_slide_content_adaptation(
    session: Session,
    slide_id: UUID,
    *,
    layout_report: object | None = None,
) -> list[ContentAdaptationSuggestion]:
    return ContentAdaptationService(session).analyze(
        slide_id,
        layout_report=layout_report,  # type: ignore[arg-type]
    )


def estimate_slide_capacity(
    session: Session,
    slide_id: UUID,
) -> SlideCapacityBudget | None:
    """Return ``SlideCapacityBudget`` for the Studio capacity gauge, or None."""
    return ContentAdaptationService(session).estimate_capacity(slide_id)


def create_slide_scene_proposal_from_text(
    session: Session,
    slide_id: UUID,
    text: str,
) -> SceneChangeProposal:
    """Parse NL text into Studio commands and return a SceneChangeProposal."""
    from archium.application.visual.studio_nl_proposal_service import StudioNLProposalService

    settings = _resolve_runtime_settings(None)
    return StudioNLProposalService(
        session,
        settings=settings,
        use_llm=settings.llm_configured,
    ).create_proposal_from_text(slide_id, text)


def load_presentation_design_system(
    session: Session,
    presentation_id: UUID,
) -> DesignSystem | None:
    """Return the DesignSystem bound to this presentation's ArtDirection, if any."""
    from archium.infrastructure.database.repositories import PresentationRepository
    from archium.infrastructure.database.visual_repositories import (
        ArtDirectionRepository,
        DesignSystemRepository,
    )

    presentation = PresentationRepository(session).get_presentation(presentation_id)
    if presentation is None:
        return None
    arts = ArtDirectionRepository(session).list_by_project(presentation.project_id)
    art = next((item for item in arts if item.presentation_id == presentation_id), None)
    if art is None and arts:
        art = arts[0]
    if art is None or art.design_system_id is None:
        return None
    return DesignSystemRepository(session).get(art.design_system_id)


def create_theme_proposal(
    session: Session,
    presentation_id: UUID,
    tokens: object,
    *,
    preferred_slide_id: UUID | None = None,
) -> ThemeChangeProposal:
    """Create a deck-wide ThemeChangeProposal from Studio token controls."""
    from archium.application.visual.theme_proposal_service import ThemeProposalService
    from archium.domain.visual.deck_theme_tokens import DeckThemeTokens

    if not isinstance(tokens, DeckThemeTokens):
        raise WorkflowError("无效的风格 Token。")
    settings = _resolve_runtime_settings(None)
    return ThemeProposalService(session, settings=settings).create_proposal(
        presentation_id,
        tokens,
        preferred_slide_id=preferred_slide_id,
    )


def get_active_theme_proposal(
    session: Session,
    presentation_id: UUID,
) -> ThemeChangeProposal | None:
    from archium.application.visual.theme_proposal_service import ThemeProposalService

    settings = _resolve_runtime_settings(None)
    return ThemeProposalService(session, settings=settings).get_active(presentation_id)


def accept_theme_proposal(
    session: Session,
    proposal: object,
    *,
    notes: str = "",
    allow_blockers: bool = False,
) -> ThemeChangeProposal:
    from archium.application.visual.theme_proposal_service import ThemeProposalService
    from archium.ui.studio.undo_stack import clear_all_visual_redo_stacks

    if not isinstance(proposal, ThemeChangeProposal):
        raise WorkflowError("无效的风格提案。")
    settings = _resolve_runtime_settings(None)
    result = ThemeProposalService(session, settings=settings).accept_proposal(
        proposal,
        notes=notes,
        allow_blockers=allow_blockers,
    )
    clear_all_visual_redo_stacks()
    return result


def reject_theme_proposal(
    session: Session,
    proposal: object,
    *,
    notes: str = "",
) -> ThemeChangeProposal:
    from archium.application.visual.theme_proposal_service import ThemeProposalService

    if not isinstance(proposal, ThemeChangeProposal):
        raise WorkflowError("无效的风格提案。")
    settings = _resolve_runtime_settings(None)
    return ThemeProposalService(session, settings=settings).reject_proposal(
        proposal,
        notes=notes,
    )


def create_slide_scene_proposal_from_element_comment(
    session: Session,
    slide_id: UUID,
    *,
    node_id: str,
    note: str,
    layout_element_id: str | None = None,
    scope: str = "node",
    scope_node_ids: list[str] | None = None,
    region_bbox: dict[str, float] | None = None,
) -> SceneChangeProposal:
    """Bind an NL note to a RenderScene node and create a SceneChangeProposal."""
    from archium.application.visual.element_comment_service import ElementCommentService

    settings = _resolve_runtime_settings(None)
    _comment, proposal = ElementCommentService(
        session,
        settings=settings,
        use_llm=settings.llm_configured,
    ).create_and_propose(
        slide_id=slide_id,
        node_id=node_id,
        note=note,
        layout_element_id=layout_element_id,
        scope=scope,
        scope_node_ids=scope_node_ids,
        region_bbox=region_bbox,
    )
    return proposal


def resolve_selected_render_node_id(
    slide_snapshot: object,
    selected_element_id: str | None,
) -> tuple[str | None, str | None]:
    """Map Studio selection (layout element id) to a RenderScene node id.

    Returns ``(node_id, layout_element_id)``. Either may be None when unresolved.
    """
    if not selected_element_id or not selected_element_id.strip():
        return None, None
    layout_element_id = selected_element_id.strip()
    scene = getattr(slide_snapshot, "render_scene", None)
    if scene is None:
        return None, layout_element_id
    node = scene.node_by_layout_element_id(layout_element_id) or scene.node_by_id(
        layout_element_id
    )
    if node is None:
        return None, layout_element_id
    return node.id, layout_element_id


def create_slide_scene_proposal_from_intent(
    session: Session,
    slide_id: UUID,
    intent: object,
    *,
    params: dict[str, object] | None = None,
) -> SceneChangeProposal:
    """Map a preset visual intent to Studio commands and return a SceneChangeProposal."""
    from archium.application.visual.studio_nl_proposal_service import StudioNLProposalService
    from archium.domain.visual.edit_intent import VisualEditIntent

    if not isinstance(intent, VisualEditIntent):
        raise WorkflowError("无效的 Scene 提案意图。")
    settings = _resolve_runtime_settings(None)
    return StudioNLProposalService(
        session,
        settings=settings,
        use_llm=settings.llm_configured,
    ).create_proposal_from_intent(slide_id, intent, params=params)


def create_slide_overflow_repair_proposal(
    session: Session,
    slide_id: UUID,
    *,
    node_ids: list[str] | None = None,
) -> SceneChangeProposal:
    """Create a SceneChangeProposal for deferred semantic overflow repair."""
    from archium.application.visual.studio_nl_proposal_service import StudioNLProposalService

    settings = _resolve_runtime_settings(None)
    return StudioNLProposalService(
        session,
        settings=settings,
        use_llm=settings.llm_configured,
    ).create_overflow_repair_proposal(slide_id, node_ids=node_ids)


def apply_slide_visual_edit(
    session: Session,
    slide_id: UUID,
    *,
    text: str | None = None,
    intent: str | None = None,
    params: dict[str, object] | None = None,
) -> object:
    """Apply NL or preset visual edit intent for the current slide."""
    from archium.application.visual.visual_edit_service import VisualEditService
    from archium.domain.visual.edit_intent import intent_from_preset
    from archium.ui.studio.undo_stack import clear_visual_redo_stack

    clear_visual_redo_stack(slide_id)
    service = VisualEditService(session, settings=_resolve_runtime_settings(None))
    if text:
        return service.apply_text(slide_id, text)
    resolved = intent_from_preset(intent or "")
    if resolved is None:
        raise WorkflowError(f"Unsupported visual edit intent: {intent}")
    return service.apply_intent(slide_id, resolved, params=params or {})


def apply_slide_element_move(
    session: Session,
    slide_id: UUID,
    *,
    element_id: str,
    x: float,
    y: float,
) -> object:
    """Move a layout element via canvas drag or property panel."""
    from archium.application.visual.studio_scene_edit_service import StudioSceneEditService
    from archium.ui.studio.undo_stack import clear_visual_redo_stack

    clear_visual_redo_stack(slide_id)
    return StudioSceneEditService(session, settings=_resolve_runtime_settings(None)).move_layout_element(
        slide_id,
        element_id=element_id,
        x=x,
        y=y,
    )


def apply_slide_element_moves(
    session: Session,
    slide_id: UUID,
    *,
    moves: list[tuple[str, float, float]],
) -> object:
    """Batch-move layout elements (one Scene revision)."""
    from archium.application.visual.studio_scene_edit_service import StudioSceneEditService
    from archium.ui.studio.undo_stack import clear_visual_redo_stack

    clear_visual_redo_stack(slide_id)
    return StudioSceneEditService(
        session, settings=_resolve_runtime_settings(None)
    ).move_layout_elements(slide_id, moves=moves)


def apply_slide_element_text(
    session: Session,
    slide_id: UUID,
    *,
    element_id: str,
    text: str,
) -> object:
    """Rewrite element text via Studio command chain (canvas inline edit)."""
    from archium.application.visual.studio_scene_edit_service import StudioSceneEditService
    from archium.ui.studio.undo_stack import clear_visual_redo_stack

    clear_visual_redo_stack(slide_id)
    return StudioSceneEditService(
        session, settings=_resolve_runtime_settings(None)
    ).rewrite_layout_element_text(slide_id, element_id=element_id, new_text=text)


def apply_slide_element_resize(
    session: Session,
    slide_id: UUID,
    *,
    element_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    preserve_aspect_ratio: bool = False,
) -> object:
    """Resize a layout element via canvas handles."""
    from archium.application.visual.studio_scene_edit_service import StudioSceneEditService
    from archium.ui.studio.undo_stack import clear_visual_redo_stack

    clear_visual_redo_stack(slide_id)
    return StudioSceneEditService(
        session, settings=_resolve_runtime_settings(None)
    ).resize_layout_element(
        slide_id,
        element_id=element_id,
        x=x,
        y=y,
        width=width,
        height=height,
        preserve_aspect_ratio=preserve_aspect_ratio,
    )


def apply_slide_element_align(
    session: Session,
    slide_id: UUID,
    *,
    element_ids: list[str],
    alignment: str,
    reference_element_id: str | None = None,
) -> object:
    """Align selected layout elements through the Studio command chain."""
    from archium.application.visual.studio_scene_edit_service import StudioSceneEditService
    from archium.ui.studio.undo_stack import clear_visual_redo_stack

    clear_visual_redo_stack(slide_id)
    return StudioSceneEditService(
        session, settings=_resolve_runtime_settings(None)
    ).align_layout_elements(
        slide_id,
        element_ids=element_ids,
        alignment=alignment,  # type: ignore[arg-type]
        reference_element_id=reference_element_id,
    )


def apply_slide_element_delete(
    session: Session,
    slide_id: UUID,
    *,
    element_id: str,
) -> object:
    """Delete (hide) a layout element through the Studio command chain."""
    from archium.application.visual.studio_scene_edit_service import StudioSceneEditService
    from archium.ui.studio.undo_stack import clear_visual_redo_stack

    clear_visual_redo_stack(slide_id)
    return StudioSceneEditService(
        session, settings=_resolve_runtime_settings(None)
    ).delete_layout_element(slide_id, element_id=element_id)


def apply_slide_element_visibility(
    session: Session,
    slide_id: UUID,
    *,
    element_id: str,
    visible: bool,
) -> object:
    """Show or hide a layout element through the Studio command chain."""
    from archium.application.visual.studio_scene_edit_service import StudioSceneEditService
    from archium.ui.studio.undo_stack import clear_visual_redo_stack

    clear_visual_redo_stack(slide_id)
    return StudioSceneEditService(
        session, settings=_resolve_runtime_settings(None)
    ).set_layout_element_visibility(
        slide_id,
        element_id=element_id,
        visible=visible,
    )


def apply_slide_element_reorder(
    session: Session,
    slide_id: UUID,
    *,
    element_id: str,
    direction: str,
) -> object:
    """Change element stacking order through the Studio command chain."""
    from archium.application.visual.studio_scene_edit_service import StudioSceneEditService
    from archium.ui.studio.undo_stack import clear_visual_redo_stack

    clear_visual_redo_stack(slide_id)
    return StudioSceneEditService(
        session, settings=_resolve_runtime_settings(None)
    ).reorder_layout_element(
        slide_id,
        element_id=element_id,
        direction=direction,  # type: ignore[arg-type]
    )


def apply_slide_element_lock(
    session: Session,
    slide_id: UUID,
    *,
    element_id: str,
    locked: bool,
    lock_scopes: list[str] | None = None,
) -> object:
    """Lock or unlock a layout element through the Studio command chain."""
    from archium.application.visual.studio_scene_edit_service import StudioSceneEditService
    from archium.ui.studio.undo_stack import clear_visual_redo_stack

    clear_visual_redo_stack(slide_id)
    return StudioSceneEditService(
        session, settings=_resolve_runtime_settings(None)
    ).set_layout_element_lock(
        slide_id,
        element_id=element_id,
        locked=locked,
        lock_scopes=lock_scopes,
    )


def restore_slide_content_adaptation(session: Session, slide_id: UUID) -> object:
    return undo_slide_content_adaptation(session, slide_id)


def undo_slide_content_adaptation(session: Session, slide_id: UUID) -> object:
    from archium.application.content_adaptation_service import ContentAdaptationService
    from archium.application.slide_history_service import SlideHistoryService
    from archium.infrastructure.database.repositories import PresentationRepository
    from archium.ui.studio.undo_stack import push_content_redo_revision

    presentations = PresentationRepository(session)
    slide = presentations.get_slide(slide_id)
    if slide is None:
        raise WorkflowError("页面不存在。")
    redo_revision_id = SlideHistoryService(session).revision_id_matching_current(slide)
    result = ContentAdaptationService(session).restore_previous(slide_id)
    if redo_revision_id is not None:
        push_content_redo_revision(slide_id, redo_revision_id)
    return result


def redo_slide_content_adaptation(session: Session, slide_id: UUID) -> object:
    from archium.ui.studio.undo_stack import pop_content_redo_revision

    revision_id = pop_content_redo_revision(slide_id)
    if revision_id is None:
        raise WorkflowError("没有可重做的内容修改。")
    return restore_slide_content_at_revision(session, slide_id, revision_id)


def restore_slide_visual_edit(session: Session, slide_id: UUID) -> object:
    return undo_slide_visual_edit(session, slide_id)


def undo_slide_visual_edit(
    session: Session,
    slide_id: UUID,
) -> SceneRevisionRestoreResult | VisualEditResult:
    from archium.application.visual.scene_undo_service import SceneUndoService
    from archium.application.visual.visual_edit_service import VisualEditService
    from archium.application.visual.visual_history_service import VisualHistoryService
    from archium.infrastructure.database.repositories import PresentationRepository
    from archium.infrastructure.database.visual_repositories import (
        LayoutPlanRepository,
        VisualIntentRepository,
    )
    from archium.ui.studio.canvas_command_bridge import bump_canvas_generation
    from archium.ui.studio.undo_stack import push_visual_redo_revision

    presentations = PresentationRepository(session)
    slide = presentations.get_slide(slide_id)
    if slide is None:
        raise WorkflowError("页面不存在。")

    settings = _resolve_runtime_settings(None)
    scene_undo = SceneUndoService(session, settings=settings)
    if scene_undo.count_undo_steps(slide) > 0:
        undo_result, redo_revision_id = scene_undo.undo(slide)
        if redo_revision_id is not None:
            push_visual_redo_revision(slide_id, redo_revision_id)
        bump_canvas_generation(slide_id)
        return undo_result

    history = VisualHistoryService(session)
    intents = VisualIntentRepository(session)
    plans = LayoutPlanRepository(session)
    intent = intents.get(slide.visual_intent_id) if slide.visual_intent_id else None
    plan = plans.get(slide.layout_plan_id) if slide.layout_plan_id else None
    redo_revision_id = history.revision_id_matching_current(
        slide,
        visual_intent=intent,
        layout_plan=plan,
    )
    service = VisualEditService(session, settings=settings)
    restore_result = service.restore_previous(slide_id)
    if redo_revision_id is not None:
        push_visual_redo_revision(slide_id, redo_revision_id)
    bump_canvas_generation(slide_id)
    return restore_result


def redo_slide_visual_edit(session: Session, slide_id: UUID) -> object:
    from archium.application.revision_service import RevisionService
    from archium.application.visual.scene_history_service import SCENE_STATE_SNAPSHOT_KIND
    from archium.application.visual.scene_undo_service import SceneUndoService
    from archium.ui.studio.canvas_command_bridge import bump_canvas_generation
    from archium.ui.studio.undo_stack import pop_visual_redo_revision

    revision_id = pop_visual_redo_revision(slide_id)
    if revision_id is None:
        raise WorkflowError("没有可重做的视觉修改。")

    presentations = PresentationRepository(session)
    slide = presentations.get_slide(slide_id)
    if slide is None:
        raise WorkflowError("页面不存在。")

    revisions = RevisionService(session)
    revision = revisions.get_revision(revision_id)
    if revision is not None and revision.snapshot.get("kind") == SCENE_STATE_SNAPSHOT_KIND:
        result = SceneUndoService(
            session,
            settings=_resolve_runtime_settings(None),
        ).redo(slide, revision_id)
        bump_canvas_generation(slide_id)
        return result
    return restore_slide_visual_at_revision(session, slide_id, revision_id)


def apply_slide_content_adaptation(
    session: Session,
    slide_id: UUID,
    *,
    text: str | None = None,
    action: str | None = None,
) -> object:
    from archium.application.content_adaptation_service import ContentAdaptationService
    from archium.application.content_adaptation_heuristics import parse_content_adaptation_text
    from archium.domain.content_adaptation import action_from_value
    from archium.ui.studio.undo_stack import clear_content_redo_stack

    clear_content_redo_stack(slide_id)
    service = ContentAdaptationService(session)
    if text:
        resolved = parse_content_adaptation_text(text)
        if resolved is None:
            raise WorkflowError("无法识别内容适配意图。")
        return service.apply(slide_id, resolved)
    resolved = action_from_value(action or "")
    if resolved is None:
        raise WorkflowError(f"Unsupported content adaptation: {action}")
    return service.apply(slide_id, resolved)


def apply_deck_repair_suggestion(session: Session, suggestion: DeckRepairSuggestion) -> object:
    """Apply one deck-level repair suggestion via existing visual edit service."""
    return apply_slide_visual_edit(
        session,
        suggestion.slide_id,
        intent=suggestion.intent,
        params=dict(suggestion.params),
    )


def restore_slide_visual_at_revision(
    session: Session,
    slide_id: UUID,
    revision_id: UUID,
) -> object:
    from archium.application.visual.visual_edit_service import VisualEditService

    service = VisualEditService(session, settings=_resolve_runtime_settings(None))
    return service.restore_at_revision(slide_id, revision_id)


def restore_slide_content_at_revision(
    session: Session,
    slide_id: UUID,
    revision_id: UUID,
) -> object:
    from archium.application.content_adaptation_service import ContentAdaptationService

    return ContentAdaptationService(session).restore_at_revision(slide_id, revision_id)


def list_slide_visual_revisions(session: Session, slide_id: UUID) -> list[EntityRevision]:
    from archium.application.visual.visual_history_service import VisualHistoryService
    from archium.infrastructure.database.repositories import PresentationRepository

    slide = PresentationRepository(session).get_slide(slide_id)
    if slide is None:
        return []
    return VisualHistoryService(session).list_slide_visual_revisions(slide)


def list_slide_content_revisions(session: Session, slide_id: UUID) -> list[EntityRevision]:
    from archium.application.content_adaptation_service import ContentAdaptationService

    return ContentAdaptationService(session).list_content_revisions(slide_id)


def count_visual_revisions(session: Session, slide_id: UUID) -> int:
    from archium.application.visual.visual_history_service import VisualHistoryService
    from archium.infrastructure.database.repositories import PresentationRepository

    slide = PresentationRepository(session).get_slide(slide_id)
    if slide is None:
        return 0
    return len(VisualHistoryService(session).list_slide_visual_revisions(slide))


def count_scene_revisions(session: Session, slide_id: UUID) -> int:
    from archium.application.scene_revision_timeline_service import SceneRevisionTimelineService
    from archium.infrastructure.database.repositories import PresentationRepository

    slide = PresentationRepository(session).get_slide(slide_id)
    if slide is None:
        return 0
    return len(
        SceneRevisionTimelineService(session).list_summaries(
            slide,
            include_rejected_proposals=False,
        )
    )


def count_visual_undo_steps(session: Session, slide_id: UUID) -> int:
    from archium.application.visual.scene_undo_service import SceneUndoService
    from archium.application.visual.visual_edit_service import VisualEditService
    from archium.infrastructure.database.repositories import PresentationRepository

    slide = PresentationRepository(session).get_slide(slide_id)
    if slide is None:
        return 0
    settings = _resolve_runtime_settings(None)
    scene_steps = SceneUndoService(session, settings=settings).count_undo_steps(slide)
    visual_steps = VisualEditService(session, settings=settings).count_undo_steps(slide_id)
    return scene_steps + visual_steps


def count_content_undo_steps(session: Session, slide_id: UUID) -> int:
    from archium.application.slide_history_service import SlideHistoryService
    from archium.infrastructure.database.repositories import PresentationRepository

    slide = PresentationRepository(session).get_slide(slide_id)
    if slide is None:
        return 0
    return SlideHistoryService(session).count_available_undo_steps(slide)


def studio_readiness_label(context: StudioPresentationContext) -> str:
    if context.slide_count == 0:
        return "empty"
    if context.ready_for_export:
        return "ready"
    if context.layout_ready_count > 0:
        return "has_issues"
    return "needs_visual"

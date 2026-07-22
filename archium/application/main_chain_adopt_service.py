"""Evaluate technology-radar adopt concepts against main-chain project state."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.deck_coherence_qa_service import DeckCoherenceQAService
from archium.application.main_chain_adopt_catalog import MAIN_CHAIN_ADOPT_BINDINGS
from archium.domain.main_chain_adopt import (
    AdoptLandingStatus,
    MainChainAdoptBinding,
    MainChainAdoptCheckpoint,
    MainChainAdoptReport,
)
from archium.infrastructure.database.repositories import (
    DeliveryRecordRepository,
    PresentationRepository,
    ProjectRepository,
    WorkflowRunRepository,
)


class MainChainAdoptService:
    """Verify adopt concepts are landed on the main chain for a project."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._projects = ProjectRepository(session)
        self._presentations = PresentationRepository(session)
        self._deliveries = DeliveryRecordRepository(session)
        self._workflows = WorkflowRunRepository(session)
        self._deck_qa = DeckCoherenceQAService()

    def evaluate(
        self,
        project_id: UUID,
        *,
        presentation_id: UUID | None = None,
    ) -> MainChainAdoptReport:
        project = self._projects.get_by_id(project_id)
        if project is None:
            return MainChainAdoptReport(project_id=str(project_id), checkpoints=[])

        presentation = self._resolve_presentation(project_id, presentation_id)
        if presentation is None:
            checkpoints = [
                MainChainAdoptCheckpoint(
                    binding=binding,
                    status=AdoptLandingStatus.PLATFORM if binding.platform_builtin else AdoptLandingStatus.GAP,
                    detail_zh="主链已内置" if binding.platform_builtin else "尚未创建汇报",
                )
                for binding in MAIN_CHAIN_ADOPT_BINDINGS
            ]
            return MainChainAdoptReport(
                project_id=str(project_id),
                presentation_id=None,
                checkpoints=checkpoints,
            )

        slides = self._presentations.list_slides(presentation.id)
        outline = None
        if presentation.current_outline_id:
            outline = self._presentations.get_outline(presentation.current_outline_id)
        if outline is None:
            outlines = self._presentations.list_outlines(presentation.id)
            outline = outlines[0] if outlines else None

        storyline = None
        if presentation.current_storyline_id:
            storyline = self._presentations.get_storyline(presentation.current_storyline_id)
        if storyline is None:
            storylines = self._presentations.list_storylines(presentation.id)
            storyline = storylines[0] if storylines else None

        checkpoints = [
            self._evaluate_binding(
                binding,
                project_id=project_id,
                presentation_id=presentation.id,
                slides=slides,
                outline=outline,
                storyline=storyline,
            )
            for binding in MAIN_CHAIN_ADOPT_BINDINGS
        ]
        return MainChainAdoptReport(
            project_id=str(project_id),
            presentation_id=str(presentation.id),
            checkpoints=checkpoints,
        )

    def _resolve_presentation(
        self,
        project_id: UUID,
        presentation_id: UUID | None,
    ) -> object | None:
        presentations = self._presentations.list_by_project(project_id)
        if not presentations:
            return None
        if presentation_id is not None:
            matched = next((item for item in presentations if item.id == presentation_id), None)
            if matched is not None:
                return matched
        return max(presentations, key=lambda item: item.updated_at)

    def _evaluate_binding(
        self,
        binding: MainChainAdoptBinding,
        *,
        project_id: UUID,
        presentation_id: UUID,
        slides: list[object],
        outline: object | None,
        storyline: object | None,
    ) -> MainChainAdoptCheckpoint:
        if binding.platform_builtin:
            return MainChainAdoptCheckpoint(
                binding=binding,
                status=AdoptLandingStatus.PLATFORM,
                detail_zh="主链已内置",
            )

        evaluator = _EVALUATORS.get(binding.concept_id)
        if evaluator is None:
            return MainChainAdoptCheckpoint(
                binding=binding,
                status=AdoptLandingStatus.GAP,
                detail_zh=binding.gate_hint_zh or "待接入",
            )
        return evaluator(
            self,
            binding=binding,
            project_id=project_id,
            presentation_id=presentation_id,
            slides=slides,
            outline=outline,
            storyline=storyline,
        )

    def _platform_or_gap(
        self,
        binding: MainChainAdoptBinding,
        *,
        landed: bool,
        detail: str,
    ) -> MainChainAdoptCheckpoint:
        if binding.platform_builtin:
            return MainChainAdoptCheckpoint(
                binding=binding,
                status=AdoptLandingStatus.PLATFORM,
                detail_zh="主链已内置",
            )
        return MainChainAdoptCheckpoint(
            binding=binding,
            status=AdoptLandingStatus.LANDED if landed else AdoptLandingStatus.GAP,
            detail_zh=detail,
        )


def _checkpoint(
    binding: MainChainAdoptBinding,
    *,
    status: AdoptLandingStatus,
    detail_zh: str,
    blocks: bool = False,
) -> MainChainAdoptCheckpoint:
    return MainChainAdoptCheckpoint(
        binding=binding,
        status=status,
        detail_zh=detail_zh,
        blocks_stage_advance=blocks,
    )


def _eval_multi_step_reflection(
    service: MainChainAdoptService,
    *,
    binding: MainChainAdoptBinding,
    project_id: UUID,
    presentation_id: UUID,
    slides: list[object],
    outline: object | None,
    storyline: object | None,
) -> MainChainAdoptCheckpoint:
    del project_id
    runs = service._workflows.list_by_presentation(presentation_id)
    multi_step = any(
        len((run.state or {}).get("step_log") or []) >= 3 for run in runs
    )
    if multi_step:
        return _checkpoint(binding, status=AdoptLandingStatus.LANDED, detail_zh="工作流含多步 step_log")

    if slides and outline is not None and storyline is not None:
        report = service._deck_qa.evaluate(slides, outline=outline, storyline=storyline)
        if report.findings:
            return _checkpoint(
                binding,
                status=AdoptLandingStatus.PARTIAL,
                detail_zh=f"已运行 deck 叙事 QA（{len(report.findings)} 项待处理）",
            )
        return _checkpoint(binding, status=AdoptLandingStatus.LANDED, detail_zh="deck 叙事 QA 已通过")

    if slides:
        return _checkpoint(
            binding,
            status=AdoptLandingStatus.PARTIAL,
            detail_zh="已有页面，建议运行 deck 叙事 QA",
        )
    return _checkpoint(binding, status=AdoptLandingStatus.GAP, detail_zh=binding.gate_hint_zh)


def _eval_template_induction(
    service: MainChainAdoptService,
    *,
    binding: MainChainAdoptBinding,
    project_id: UUID,
    presentation_id: UUID,
    slides: list[object],
    outline: object | None,
    storyline: object | None,
) -> MainChainAdoptCheckpoint:
    del presentation_id, slides, storyline
    profiles = service._projects.list_reference_style_profiles(project_id)
    if profiles:
        return _checkpoint(binding, status=AdoptLandingStatus.LANDED, detail_zh="已绑定参考风格档案")
    if outline is not None and getattr(outline, "page_design_briefs", None):
        return _checkpoint(
            binding,
            status=AdoptLandingStatus.PARTIAL,
            detail_zh="使用页面设计摘要驱动版式（未绑定参考模板）",
        )
    return _checkpoint(
        binding,
        status=AdoptLandingStatus.PARTIAL,
        detail_zh="可使用模板库/模板归纳补充参考结构",
    )


def _eval_reference_structure(
    service: MainChainAdoptService,
    *,
    binding: MainChainAdoptBinding,
    project_id: UUID,
    presentation_id: UUID,
    slides: list[object],
    outline: object | None,
    storyline: object | None,
) -> MainChainAdoptCheckpoint:
    del presentation_id, slides, storyline
    profiles = service._projects.list_reference_style_profiles(project_id)
    approved = [profile for profile in profiles if getattr(profile, "is_approved", False)]
    if approved:
        return _checkpoint(binding, status=AdoptLandingStatus.LANDED, detail_zh="已有已批准参考风格")
    if profiles:
        return _checkpoint(binding, status=AdoptLandingStatus.PARTIAL, detail_zh="参考风格待批准")
    return _checkpoint(binding, status=AdoptLandingStatus.GAP, detail_zh=binding.gate_hint_zh)


def _eval_narrative_arc(
    service: MainChainAdoptService,
    *,
    binding: MainChainAdoptBinding,
    project_id: UUID,
    presentation_id: UUID,
    slides: list[object],
    outline: object | None,
    storyline: object | None,
) -> MainChainAdoptCheckpoint:
    del service, project_id, presentation_id, slides
    if storyline is None or getattr(storyline, "narrative_arc", None) is None:
        return _checkpoint(
            binding,
            status=AdoptLandingStatus.GAP,
            detail_zh="Storyline 缺少 narrative_arc",
            blocks=True,
        )
    if outline is None:
        return _checkpoint(
            binding,
            status=AdoptLandingStatus.PARTIAL,
            detail_zh="已有叙事弧线，待生成大纲章节",
        )
    sections = getattr(outline, "sections", []) or []
    if not sections:
        return _checkpoint(binding, status=AdoptLandingStatus.PARTIAL, detail_zh="大纲章节为空")
    positioned = sum(1 for section in sections if getattr(section, "narrative_position", None))
    if positioned >= len(sections):
        return _checkpoint(binding, status=AdoptLandingStatus.LANDED, detail_zh="全部章节已标注 narrative_position")
    return _checkpoint(
        binding,
        status=AdoptLandingStatus.PARTIAL,
        detail_zh=f"{positioned}/{len(sections)} 章已标注 narrative_position",
    )


def _eval_per_page_binding(
    service: MainChainAdoptService,
    *,
    binding: MainChainAdoptBinding,
    project_id: UUID,
    presentation_id: UUID,
    slides: list[object],
    outline: object | None,
    storyline: object | None,
) -> MainChainAdoptCheckpoint:
    del service, project_id, presentation_id, storyline
    if not slides:
        return _checkpoint(binding, status=AdoptLandingStatus.GAP, detail_zh="尚无页面")
    bindings = list(getattr(outline, "page_asset_bindings", None) or []) if outline else []
    if bindings:
        slide_ids = {str(slide.id) for slide in slides}
        covered = {str(item.slide_id) for item in bindings if getattr(item, "slide_id", None)}
        if covered & slide_ids:
            return _checkpoint(
                binding,
                status=AdoptLandingStatus.LANDED,
                detail_zh=f"已绑定 {len(bindings)} 条 page_asset_bindings",
            )
    visual_bound = sum(
        1
        for slide in slides
        if getattr(slide, "visual_requirements", None)
        and any(getattr(req, "asset_id", None) for req in slide.visual_requirements)
    )
    if visual_bound > 0:
        return _checkpoint(
            binding,
            status=AdoptLandingStatus.PARTIAL,
            detail_zh=f"{visual_bound}/{len(slides)} 页通过 visual_requirements 绑定素材",
        )
    return _checkpoint(binding, status=AdoptLandingStatus.GAP, detail_zh=binding.gate_hint_zh)


def _eval_native_layout(
    service: MainChainAdoptService,
    *,
    binding: MainChainAdoptBinding,
    project_id: UUID,
    presentation_id: UUID,
    slides: list[object],
    outline: object | None,
    storyline: object | None,
) -> MainChainAdoptCheckpoint:
    del service, project_id, outline, storyline
    if not slides:
        return _checkpoint(binding, status=AdoptLandingStatus.GAP, detail_zh="尚无页面")
    with_layout = sum(1 for slide in slides if getattr(slide, "layout_plan_id", None))
    if with_layout <= 0:
        return _checkpoint(binding, status=AdoptLandingStatus.GAP, detail_zh="尚无 LayoutPlan")
    if with_layout >= len(slides):
        return _checkpoint(binding, status=AdoptLandingStatus.LANDED, detail_zh="全部页面已有 LayoutPlan")
    return _checkpoint(
        binding,
        status=AdoptLandingStatus.PARTIAL,
        detail_zh=f"{with_layout}/{len(slides)} 页已编译 LayoutPlan",
    )


def _eval_fault_tolerant_export(
    service: MainChainAdoptService,
    *,
    binding: MainChainAdoptBinding,
    project_id: UUID,
    presentation_id: UUID,
    slides: list[object],
    outline: object | None,
    storyline: object | None,
) -> MainChainAdoptCheckpoint:
    del slides, outline, storyline
    return _eval_delivery_qa(service, binding=binding, project_id=project_id, presentation_id=presentation_id)


def _eval_render_qa(
    service: MainChainAdoptService,
    *,
    binding: MainChainAdoptBinding,
    project_id: UUID,
    presentation_id: UUID,
    slides: list[object],
    outline: object | None,
    storyline: object | None,
) -> MainChainAdoptCheckpoint:
    del slides, outline, storyline
    records = service._deliveries.list_by_presentation(presentation_id)
    for record in records:
        if record.round_trip_report_json:
            return _checkpoint(binding, status=AdoptLandingStatus.LANDED, detail_zh="最近导出含 Round-trip QA")
    return _checkpoint(binding, status=AdoptLandingStatus.GAP, detail_zh=binding.gate_hint_zh)


def _eval_file_integrity(
    service: MainChainAdoptService,
    *,
    binding: MainChainAdoptBinding,
    project_id: UUID,
    presentation_id: UUID,
    slides: list[object],
    outline: object | None,
    storyline: object | None,
) -> MainChainAdoptCheckpoint:
    del slides, outline, storyline
    records = service._deliveries.list_by_presentation(presentation_id)
    for record in records:
        if record.qa_status and record.qa_status not in {"", "unknown"}:
            return _checkpoint(binding, status=AdoptLandingStatus.LANDED, detail_zh=f"导出 QA：{record.qa_status}")
        if record.round_trip_report_json:
            return _checkpoint(binding, status=AdoptLandingStatus.PARTIAL, detail_zh="含 Round-trip，保真度 Manifest 待补齐")
    return _checkpoint(binding, status=AdoptLandingStatus.GAP, detail_zh=binding.gate_hint_zh)


def _eval_delivery_qa(
    service: MainChainAdoptService,
    *,
    binding: MainChainAdoptBinding,
    project_id: UUID,
    presentation_id: UUID,
) -> MainChainAdoptCheckpoint:
    del project_id
    records = service._deliveries.list_by_presentation(presentation_id)
    if not records:
        return _checkpoint(binding, status=AdoptLandingStatus.GAP, detail_zh="尚无导出记录")
    latest = records[0]
    has_round_trip = bool(latest.round_trip_report_json)
    has_qa = bool(latest.qa_status and latest.qa_status not in {"", "unknown"})
    if has_qa and has_round_trip:
        return _checkpoint(binding, status=AdoptLandingStatus.LANDED, detail_zh="QA 状态 + Round-trip 齐全")
    if has_qa or has_round_trip:
        return _checkpoint(binding, status=AdoptLandingStatus.PARTIAL, detail_zh="部分交付 QA 已记录")
    return _checkpoint(binding, status=AdoptLandingStatus.GAP, detail_zh=binding.gate_hint_zh)


_EVALUATORS = {
    "pptagent_multi_step_reflection": _eval_multi_step_reflection,
    "pptagent_template_induction": _eval_template_induction,
    "pptagent_reference_structure": _eval_reference_structure,
    "slide_deck_narrative_arc": _eval_narrative_arc,
    "slidebot_per_page_binding": _eval_per_page_binding,
    "slideweaver_native_layout": _eval_native_layout,
    "slide_deck_fault_tolerant_export": _eval_fault_tolerant_export,
    "slideweaver_render_qa": _eval_render_qa,
    "slideweaver_file_integrity": _eval_file_integrity,
}

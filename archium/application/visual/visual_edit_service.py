"""Apply Studio natural-language visual edit intents with revision support."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.asset_reference import (
    AssetReferenceContext,
    AssetReferenceResolver,
    build_asset_reference_context,
    content_refs_from_plan,
)
from archium.application.visual.composite_operation_policy import (
    assert_composite_operations_supported,
)
from archium.application.visual.layout_planning_service import LayoutPlanningService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.operation_decomposer import OperationDecomposer
from archium.application.visual.transaction_executor import (
    TransactionExecutionContext,
    TransactionExecutor,
)
from archium.application.visual.visual_history_service import VisualHistoryService
from archium.application.visual.visual_intent_presets import (
    apply_hero_asset,
    apply_layout_family_preference,
    apply_visual_intent_preset,
    remove_primary_asset,
)
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.atomic_operation import AtomicOperation, OperationType
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.edit_intent import (
    VisualEditIntent,
    intent_from_preset,
    parse_natural_language,
)
from archium.domain.visual.element_lock import (
    ElementEditOperation,
    assert_element_editable,
)
from archium.domain.visual.enums import LayoutElementRole, LayoutFamily, LayoutIssueSeverity
from archium.domain.visual.hybrid_parser import create_hybrid_parser
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.nlp_parser import ParsedIntent
from archium.domain.visual.slide_edit_snapshot import SlideEditSnapshot
from archium.domain.visual.visual_intent import VisualIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.llm.factory import create_llm_provider


@dataclass(frozen=True)
class VisualEditResult:
    slide_id: UUID
    intent: VisualEditIntent | None
    visual_intent: VisualIntent | None
    layout_plan: LayoutPlan | None
    validation: object | None
    restored: bool = False
    message: str = ""


class VisualEditService:
    """Parse and apply the eight supported slide visual edit intents."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        use_llm: bool = False,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._use_llm = use_llm and self._settings.llm_configured
        self._presentations = PresentationRepository(session)
        self._intents = VisualIntentRepository(session)
        self._plans = LayoutPlanRepository(session)
        self._design_repo = DesignSystemRepository(session)
        self._history = VisualHistoryService(session)

        # 初始化混合解析器
        llm_provider = create_llm_provider(self._settings) if self._use_llm else None
        self._hybrid_parser = create_hybrid_parser(llm_provider, use_llm=self._use_llm)

        # 初始化事务执行组件
        self._decomposer = OperationDecomposer()
        self._transaction_executor = TransactionExecutor(session, self._history)

    def apply_text(
        self,
        slide_id: UUID,
        text: str,
        *,
        candidate_count: int = 3,
    ) -> VisualEditResult:
        # 使用混合解析器
        parsed = self._hybrid_parser.parse(text)

        if parsed is None:
            # 回退到原始解析器
            intent, params = parse_natural_language(text)
            if intent is None:
                raise WorkflowError("无法识别修改意图。请使用预设按钮或更明确的描述。")
            # 单一意图，使用原有路径
            return self.apply_intent(
                slide_id,
                intent,
                params=params,
                candidate_count=candidate_count,
            )

        # 检查是否为复合操作
        has_constraints = any(m.type.value == "constraint" for m in parsed.modifiers)
        has_multi_step = any(m.type.value == "multi_step" for m in parsed.modifiers)
        is_composite = has_constraints or has_multi_step or "multi_step_operations" in parsed.params

        if is_composite:
            # 使用事务执行路径处理复合操作
            return self._apply_composite_operation(
                slide_id,
                parsed,
                candidate_count=candidate_count,
            )
        else:
            # 单一意图，使用原有路径
            intent = parsed.intent
            params = parsed.params
            return self.apply_intent(
                slide_id,
                intent,
                params=params,
                candidate_count=candidate_count,
            )

    def apply_intent(
        self,
        slide_id: UUID,
        intent: VisualEditIntent | str,
        *,
        params: dict[str, object] | None = None,
        candidate_count: int = 3,
    ) -> VisualEditResult:
        resolved = intent_from_preset(str(intent)) if not isinstance(intent, VisualEditIntent) else intent
        if resolved is None:
            raise WorkflowError(f"Unsupported visual edit intent: {intent}")
        if resolved == VisualEditIntent.RESTORE_PREVIOUS:
            return self.restore_previous(slide_id)

        if resolved in {VisualEditIntent.LOCK_ELEMENT, VisualEditIntent.UNLOCK_ELEMENT}:
            slide = self._require_slide(slide_id)
            locked = resolved == VisualEditIntent.LOCK_ELEMENT
            return self._apply_element_lock_state(
                slide,
                self._load_intent(slide),
                self._load_plan(slide),
                params or {},
                locked=locked,
                edit_intent=resolved,
            )

        slide = self._require_slide(slide_id)
        current_intent = self._load_intent(slide)
        current_plan = self._load_plan(slide)
        self._history.record_state(
            slide=slide,
            visual_intent=current_intent,
            layout_plan=current_plan,
            change_source=RevisionSource.MANUAL_EDIT,
            note=resolved.value,
        )

        if resolved in {
            VisualEditIntent.UPDATE_ELEMENT_TEXT,
            VisualEditIntent.SET_ELEMENT_ASSET,
        }:
            return self._apply_element_direct_edit(
                slide,
                current_intent,
                current_plan,
                resolved,
                params or {},
            )

        self._assert_replan_intent_allowed(current_plan, resolved, params or {})
        updated_intent = self._mutate_intent(current_intent, slide, resolved, params or {})
        replanned = self._replan(
            slide,
            updated_intent,
            candidate_count=candidate_count,
            edit_intent=resolved,
        )
        self._invalidate_preview_cache(slide.presentation_id, replanned.layout_plan)
        return replanned

    def restore_at_revision(self, slide_id: UUID, revision_id: UUID) -> VisualEditResult:
        slide = self._require_slide(slide_id)
        current_intent = self._load_intent(slide)
        current_plan = self._load_plan(slide)
        self._history.record_state(
            slide=slide,
            visual_intent=current_intent,
            layout_plan=current_plan,
            change_source=RevisionSource.MANUAL_EDIT,
            note="before_restore_at_revision",
        )
        intent, plan = self._history.restore_at_revision(
            slide_id,
            revision_id,
            intents=self._intents,
            plans=self._plans,
            presentations=self._presentations,
        )
        validation = None
        design = self._resolve_design_system(slide, intent)
        if plan is not None and design is not None:
            validation = LayoutValidationService().validate(
                plan,
                design,
                require_source=True,
                drawing_hero=plan.layout_family == LayoutFamily.DRAWING_FOCUS,
            )
        if plan is not None:
            self._invalidate_preview_cache(slide.presentation_id, plan)
        return VisualEditResult(
            slide_id=slide.id,
            intent=VisualEditIntent.RESTORE_PREVIOUS,
            visual_intent=intent,
            layout_plan=plan,
            validation=validation,
            restored=True,
            message="已恢复到所选视觉版本。",
        )

    def restore_previous(self, slide_id: UUID) -> VisualEditResult:
        slide = self._require_slide(slide_id)
        current_intent = self._load_intent(slide)
        current_plan = self._load_plan(slide)
        revision = self._history.latest_restorable_revision(
            slide,
            visual_intent=current_intent,
            layout_plan=current_plan,
        )
        if revision is None:
            raise WorkflowError("没有可恢复的视觉修订。")

        intent, plan = self._history.restore_revision(
            revision,
            intents=self._intents,
            plans=self._plans,
            presentations=self._presentations,
        )
        validation = None
        design = self._resolve_design_system(slide, intent)
        if plan is not None and design is not None:
            validation = LayoutValidationService().validate(
                plan,
                design,
                require_source=True,
                drawing_hero=plan.layout_family == LayoutFamily.DRAWING_FOCUS,
            )
        if plan is not None:
            self._invalidate_preview_cache(slide.presentation_id, plan)
        return VisualEditResult(
            slide_id=slide.id,
            intent=VisualEditIntent.RESTORE_PREVIOUS,
            visual_intent=intent,
            layout_plan=plan,
            validation=validation,
            restored=True,
            message="已恢复到上一版视觉状态。",
        )

    def apply_element_move(
        self,
        slide_id: UUID,
        element_id: str,
        *,
        x: float,
        y: float,
        candidate_count: int = 3,
    ) -> VisualEditResult:
        """Move one layout element to absolute page coordinates."""
        slide = self._require_slide(slide_id)
        current_intent = self._load_intent(slide)
        current_plan = self._load_plan(slide)
        if current_plan is None:
            raise WorkflowError("当前页面尚无版式，无法移动元素。")

        self._history.record_state(
            slide=slide,
            visual_intent=current_intent,
            layout_plan=current_plan,
            change_source=RevisionSource.MANUAL_EDIT,
            note=VisualEditIntent.MOVE_ELEMENT.value,
        )

        slide_snapshot = SlideEditSnapshot(
            slide_id=slide.id,
            presentation_id=slide.presentation_id,
            visual_intent=current_intent,
            layout_plan=current_plan,
        )
        operation = AtomicOperation(
            operation_type=OperationType.MOVE,
            target_element_id=element_id,
            params={"position": "absolute", "x": x, "y": y, "preserve_size": True},
        )
        execution_context = self._build_transaction_execution_context(
            slide,
            candidate_count=candidate_count,
        )
        result = self._transaction_executor.execute_transaction(
            operations=[operation],
            slide_id=slide_id,
            slide_snapshot=slide_snapshot,
            intents_repo=self._intents,
            plans_repo=self._plans,
            presentations_repo=self._presentations,
            execution_context=execution_context,
        )
        if not result.success:
            error_msg = "移动元素失败"
            if result.error:
                error_msg = f"{error_msg}: {result.error}"
            raise WorkflowError(error_msg)

        slide = self._require_slide(slide_id)
        updated_intent = self._load_intent(slide)
        updated_plan = self._load_plan(slide)
        validation = None
        design = self._resolve_design_system(slide, updated_intent)
        if updated_plan is not None and design is not None:
            asset_context = self._asset_context_for_plan(slide, updated_plan)
            validation = LayoutValidationService().validate(
                updated_plan,
                design,
                require_source=True,
                drawing_hero=updated_plan.layout_family == LayoutFamily.DRAWING_FOCUS,
                asset_context=asset_context,
            )
        if updated_plan is not None:
            self._invalidate_preview_cache(slide.presentation_id, updated_plan)
        return VisualEditResult(
            slide_id=slide.id,
            intent=VisualEditIntent.MOVE_ELEMENT,
            visual_intent=updated_intent,
            layout_plan=updated_plan,
            validation=validation,
            message="已移动元素位置。",
        )

    def apply_element_resize(
        self,
        slide_id: UUID,
        element_id: str,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        candidate_count: int = 3,
    ) -> VisualEditResult:
        """Resize one layout element to absolute page bounds."""
        slide = self._require_slide(slide_id)
        current_intent = self._load_intent(slide)
        current_plan = self._load_plan(slide)
        if current_plan is None:
            raise WorkflowError("当前页面尚无版式，无法缩放元素。")

        self._history.record_state(
            slide=slide,
            visual_intent=current_intent,
            layout_plan=current_plan,
            change_source=RevisionSource.MANUAL_EDIT,
            note=VisualEditIntent.RESIZE_ELEMENT.value,
        )

        slide_snapshot = SlideEditSnapshot(
            slide_id=slide.id,
            presentation_id=slide.presentation_id,
            visual_intent=current_intent,
            layout_plan=current_plan,
        )
        operation = AtomicOperation(
            operation_type=OperationType.RESIZE,
            target_element_id=element_id,
            params={
                "mode": "absolute",
                "x": x,
                "y": y,
                "width": width,
                "height": height,
            },
        )
        execution_context = self._build_transaction_execution_context(
            slide,
            candidate_count=candidate_count,
        )
        result = self._transaction_executor.execute_transaction(
            operations=[operation],
            slide_id=slide_id,
            slide_snapshot=slide_snapshot,
            intents_repo=self._intents,
            plans_repo=self._plans,
            presentations_repo=self._presentations,
            execution_context=execution_context,
        )
        if not result.success:
            error_msg = "缩放元素失败"
            if result.error:
                error_msg = f"{error_msg}: {result.error}"
            raise WorkflowError(error_msg)

        slide = self._require_slide(slide_id)
        updated_intent = self._load_intent(slide)
        updated_plan = self._load_plan(slide)
        validation = None
        design = self._resolve_design_system(slide, updated_intent)
        if updated_plan is not None and design is not None:
            asset_context = self._asset_context_for_plan(slide, updated_plan)
            validation = LayoutValidationService().validate(
                updated_plan,
                design,
                require_source=True,
                drawing_hero=updated_plan.layout_family == LayoutFamily.DRAWING_FOCUS,
                asset_context=asset_context,
            )
        if updated_plan is not None:
            self._invalidate_preview_cache(slide.presentation_id, updated_plan)
        return VisualEditResult(
            slide_id=slide.id,
            intent=VisualEditIntent.RESIZE_ELEMENT,
            visual_intent=updated_intent,
            layout_plan=updated_plan,
            validation=validation,
            message="已更新元素尺寸。",
        )

    def count_undo_steps(self, slide_id: UUID) -> int:
        slide = self._require_slide(slide_id)
        return self._history.count_available_undo_steps(
            slide,
            visual_intent=self._load_intent(slide),
            layout_plan=self._load_plan(slide),
        )

    def _apply_composite_operation(
        self,
        slide_id: UUID,
        parsed_intent: ParsedIntent,
        candidate_count: int = 3,
    ) -> VisualEditResult:
        """
        Apply a composite operation using transaction executor.

        Handles:
        - Constraint extraction (locks)
        - Multi-step operation sequencing
        - Atomic execution with rollback on failure
        """
        slide = self._require_slide(slide_id)
        current_intent = self._load_intent(slide)
        current_plan = self._load_plan(slide)

        # Record pre-transaction state
        self._history.record_state(
            slide=slide,
            visual_intent=current_intent,
            layout_plan=current_plan,
            change_source=RevisionSource.MANUAL_EDIT,
            note=f"before_composite_operation: {parsed_intent.intent.value}",
        )

        # Build slide snapshot for decomposition
        slide_snapshot = SlideEditSnapshot(
            slide_id=slide.id,
            presentation_id=slide.presentation_id,
            visual_intent=current_intent,
            layout_plan=current_plan,
        )

        # Decompose into atomic operations
        try:
            operations = self._decomposer.decompose(parsed_intent, slide_snapshot)
        except Exception as e:
            raise WorkflowError(f"无法分解复合操作: {str(e)}") from e

        assert_composite_operations_supported(operations)

        execution_context = self._build_transaction_execution_context(
            slide,
            candidate_count=candidate_count,
        )

        # Execute as transaction
        result = self._transaction_executor.execute_transaction(
            operations=operations,
            slide_id=slide_id,
            slide_snapshot=slide_snapshot,
            intents_repo=self._intents,
            plans_repo=self._plans,
            presentations_repo=self._presentations,
            execution_context=execution_context,
        )

        if not result.success:
            error_msg = "操作失败"
            if result.error_at_step is not None:
                error_msg += f" (第{result.error_at_step + 1}步)"
            if result.error:
                error_msg += f": {str(result.error)}"
            raise WorkflowError(error_msg)

        # Reload updated state
        slide = self._require_slide(slide_id)
        updated_intent = self._load_intent(slide)
        updated_plan = self._load_plan(slide)

        # Validate and cache invalidation
        validation = None
        design = self._resolve_design_system(slide, updated_intent)
        if updated_plan is not None and design is not None:
            validation = LayoutValidationService().validate(
                updated_plan,
                design,
                require_source=True,
                drawing_hero=updated_plan.layout_family == LayoutFamily.DRAWING_FOCUS,
            )
        if updated_plan is not None:
            self._invalidate_preview_cache(slide.presentation_id, updated_plan)

        return VisualEditResult(
            slide_id=slide.id,
            intent=parsed_intent.intent,
            visual_intent=updated_intent,
            layout_plan=updated_plan,
            validation=validation,
            restored=False,
            message=f"已执行复合操作 ({len(result.executed_operations)} 步)",
        )

    def _build_transaction_execution_context(
        self,
        slide: SlideSpec,
        *,
        candidate_count: int,
    ) -> TransactionExecutionContext:
        def replan_layout_change(
            target_slide: SlideSpec,
            intent: VisualIntent,
            current_plan: LayoutPlan,
            layout_family: LayoutFamily,
        ) -> tuple[VisualIntent, LayoutPlan]:
            if not get_layout_family_registry().get(layout_family).implemented:
                raise WorkflowError(f"版式族「{layout_family.value}」尚未实现，无法切换。")
            updated_intent = apply_layout_family_preference(intent, layout_family)
            updated_intent = self._intents.save(updated_intent)
            target_slide.visual_intent_id = updated_intent.id
            self._presentations.save_slide(target_slide)

            llm = create_llm_provider(self._settings) if self._use_llm else None
            planner = LayoutPlanningService(self._session, llm=llm)
            art, design = self._resolve_art_and_design(target_slide, updated_intent)
            candidates = planner.generate_candidates(
                slide=target_slide,
                visual_intent_id=updated_intent.id,
                art_direction_id=art.id if art else None,
                design_system_id=design.id,
                candidate_count=candidate_count,
                project_id=self._project_id_for_slide(target_slide),
                previous_layout_plan=current_plan,
            )
            best = planner.select_best(
                candidates,
                previous_layout_plan=current_plan,
                style_preference=planner.last_style_preference,
            )
            saved_plan = self._plans.save(best)
            target_slide.layout_plan_id = saved_plan.id
            self._presentations.save_slide(target_slide)
            return updated_intent, saved_plan

        def validate_layout(plan: LayoutPlan) -> None:
            design = self._resolve_design_system(slide, None)
            if design is None:
                return
            report = LayoutValidationService().validate(
                plan,
                design,
                require_source=True,
                drawing_hero=plan.layout_family == LayoutFamily.DRAWING_FOCUS,
            )
            if not report.valid:
                blocking = next(
                    (
                        issue.message
                        for issue in report.issues
                        if issue.severity
                        in {LayoutIssueSeverity.CRITICAL, LayoutIssueSeverity.ERROR}
                    ),
                    "版式不满足约束",
                )
                raise WorkflowError(f"版式校验失败: {blocking}")

        def replan_current_intent(
            target_slide: SlideSpec,
            intent: VisualIntent,
            current_plan: LayoutPlan,
        ) -> tuple[VisualIntent, LayoutPlan]:
            intent = self._intents.save(intent)
            target_slide.visual_intent_id = intent.id
            self._presentations.save_slide(target_slide)

            llm = create_llm_provider(self._settings) if self._use_llm else None
            planner = LayoutPlanningService(self._session, llm=llm)
            art, design = self._resolve_art_and_design(target_slide, intent)
            candidates = planner.generate_candidates(
                slide=target_slide,
                visual_intent_id=intent.id,
                art_direction_id=art.id if art else None,
                design_system_id=design.id,
                candidate_count=candidate_count,
                project_id=self._project_id_for_slide(target_slide),
                previous_layout_plan=current_plan,
            )
            best = planner.select_best(
                candidates,
                previous_layout_plan=current_plan,
                style_preference=planner.last_style_preference,
            )
            saved_plan = self._plans.save(best)
            target_slide.layout_plan_id = saved_plan.id
            self._presentations.save_slide(target_slide)
            return intent, saved_plan

        def resolve_asset_ref(content_ref: str, element: LayoutElement | None) -> str:
            return self._validate_asset_binding(
                slide,
                content_ref=content_ref,
                element=element,
            )

        return TransactionExecutionContext(
            replan_layout_change=replan_layout_change,
            validate_layout=validate_layout,
            replan_current_intent=replan_current_intent,
            resolve_asset_ref=resolve_asset_ref,
        )

    def _apply_element_direct_edit(
        self,
        slide: SlideSpec,
        visual_intent: VisualIntent | None,
        plan: LayoutPlan | None,
        edit_intent: VisualEditIntent,
        params: dict[str, object],
    ) -> VisualEditResult:
        if plan is None:
            raise WorkflowError("当前页面尚无版式，无法直接编辑元素。")
        element_id = str(params.get("element_id") or "")
        if not element_id:
            raise WorkflowError("请指定要编辑的元素。")

        updated_elements = []
        changed = False
        for element in plan.elements:
            if element.id != element_id:
                updated_elements.append(element)
                continue
            if edit_intent == VisualEditIntent.UPDATE_ELEMENT_TEXT:
                assert_element_editable(element, ElementEditOperation.UPDATE_TEXT)
                text = str(params.get("text") or "")
                if not text.strip():
                    raise WorkflowError("文字内容不能为空。")
                updated_elements.append(element.model_copy(update={"text_content": text}))
            elif edit_intent == VisualEditIntent.SET_ELEMENT_ASSET:
                assert_element_editable(element, ElementEditOperation.SET_ASSET)
                content_ref = str(params.get("content_ref") or params.get("asset_id") or "")
                if not content_ref.strip():
                    raise WorkflowError("请指定素材引用。")
                content_ref = self._validate_asset_binding(
                    slide,
                    content_ref=content_ref,
                    element=element,
                )
                updated_elements.append(element.model_copy(update={"content_ref": content_ref}))
            changed = True
        if not changed:
            raise WorkflowError(f"未找到元素：{element_id}")

        updated_plan = plan.model_copy(
            update={
                "elements": updated_elements,
                "version": plan.version + 1,
            }
        )
        updated_plan.touch()
        saved_plan = self._plans.save(updated_plan)
        slide.layout_plan_id = saved_plan.id
        self._presentations.save_slide(slide)
        self._invalidate_preview_cache(slide.presentation_id, saved_plan)

        design = self._resolve_design_system(slide, visual_intent)
        validation = None
        if design is not None:
            asset_context = self._asset_context_for_plan(slide, saved_plan)
            validation = LayoutValidationService().validate(
                saved_plan,
                design,
                require_source=True,
                drawing_hero=saved_plan.layout_family == LayoutFamily.DRAWING_FOCUS,
                asset_context=asset_context,
            )
        message = (
            "已更新元素文字。"
            if edit_intent == VisualEditIntent.UPDATE_ELEMENT_TEXT
            else "已更新元素素材。"
        )
        return VisualEditResult(
            slide_id=slide.id,
            intent=edit_intent,
            visual_intent=visual_intent,
            layout_plan=saved_plan,
            validation=validation,
            message=message,
        )

    def _apply_element_lock_state(
        self,
        slide: SlideSpec,
        visual_intent: VisualIntent | None,
        plan: LayoutPlan | None,
        params: dict[str, object],
        *,
        locked: bool,
        edit_intent: VisualEditIntent,
    ) -> VisualEditResult:
        if plan is None:
            action = "锁定" if locked else "解锁"
            raise WorkflowError(f"当前页面尚无版式，无法{action}元素。")

        element_id = self._resolve_lock_element_id(plan, params)
        lock_scopes_raw = params.get("lock_scopes")
        lock_scopes = (
            [str(item) for item in lock_scopes_raw]
            if isinstance(lock_scopes_raw, list)
            else []
        )

        from archium.application.visual.studio_scene_edit_service import StudioSceneEditService

        edit_result = StudioSceneEditService(
            self._session,
            settings=self._settings,
        ).set_layout_element_lock(
            slide.id,
            element_id=element_id,
            locked=locked,
            lock_scopes=lock_scopes if locked else [],
        )
        saved_plan = edit_result.layout_plan
        if saved_plan is None:
            action = "锁定" if locked else "解锁"
            raise WorkflowError(f"未找到可{action}的元素：{element_id}")

        design = self._resolve_design_system(slide, visual_intent)
        validation = None
        if design is not None:
            validation = LayoutValidationService().validate(
                saved_plan,
                design,
                require_source=True,
                drawing_hero=saved_plan.layout_family == LayoutFamily.DRAWING_FOCUS,
            )
        verb = "锁定" if locked else "解锁"
        return VisualEditResult(
            slide_id=slide.id,
            intent=edit_intent,
            visual_intent=visual_intent,
            layout_plan=saved_plan,
            validation=validation,
            message=f"已{verb}元素 `{element_id}`。",
        )

    def _resolve_lock_element_id(
        self,
        plan: LayoutPlan,
        params: dict[str, object],
    ) -> str:
        element_id = str(params.get("element_id") or plan.hero_element_id or "")
        if element_id:
            return element_id
        hero = next(
            (
                element
                for element in plan.elements
                if element.role == LayoutElementRole.HERO_VISUAL
            ),
            None,
        )
        if hero is not None:
            return hero.id
        if not plan.elements:
            raise WorkflowError("当前版式没有可锁定的元素。")
        return plan.elements[0].id

    def _apply_lock_element(
        self,
        slide: SlideSpec,
        visual_intent: VisualIntent | None,
        plan: LayoutPlan | None,
        params: dict[str, object],
    ) -> VisualEditResult:
        return self._apply_element_lock_state(
            slide,
            visual_intent,
            plan,
            params,
            locked=True,
            edit_intent=VisualEditIntent.LOCK_ELEMENT,
        )

    def _mutate_intent(
        self,
        intent: VisualIntent,
        slide: SlideSpec,
        edit_intent: VisualEditIntent,
        params: dict[str, object],
    ) -> VisualIntent:
        if edit_intent == VisualEditIntent.ENLARGE_HERO:
            return apply_visual_intent_preset(intent, "enlarge_hero")
        if edit_intent == VisualEditIntent.REDUCE_TEXT:
            return apply_visual_intent_preset(intent, "reduce_text")
        if edit_intent == VisualEditIntent.INCREASE_WHITESPACE:
            return apply_visual_intent_preset(intent, "more_whitespace")
        if edit_intent == VisualEditIntent.CHANGE_LAYOUT:
            family = params.get("layout_family")
            if isinstance(family, LayoutFamily):
                if not get_layout_family_registry().get(family).implemented:
                    raise WorkflowError(f"版式族「{family.value}」尚未实现，无法切换。")
                return apply_layout_family_preference(intent, family)
            return apply_visual_intent_preset(intent, "drawing_focus")
        if edit_intent == VisualEditIntent.SET_HERO_ASSET:
            asset_id = params.get("asset_id")
            if asset_id is None:
                asset_id = self._default_hero_asset_id(slide)
            if asset_id is None:
                raise WorkflowError("请指定主图素材，或先在页面内容中绑定素材。")
            plan = self._load_plan(slide)
            hero_element = self._resolve_hero_element(plan) if plan is not None else None
            self._validate_asset_binding(
                slide,
                content_ref=str(asset_id),
                element=hero_element,
            )
            return apply_hero_asset(intent, UUID(str(asset_id)))
        if edit_intent == VisualEditIntent.REMOVE_ASSET:
            return remove_primary_asset(intent)
        return intent

    def _assert_replan_intent_allowed(
        self,
        plan: LayoutPlan | None,
        edit_intent: VisualEditIntent,
        params: dict[str, object],
    ) -> None:
        if plan is None:
            return

        hero = self._resolve_hero_element(plan)
        if edit_intent == VisualEditIntent.SET_HERO_ASSET:
            target = self._resolve_target_element(plan, params.get("element_id")) or hero
            if target is not None:
                assert_element_editable(target, ElementEditOperation.SET_HERO)
            return

        if edit_intent == VisualEditIntent.REMOVE_ASSET:
            if hero is not None:
                assert_element_editable(hero, ElementEditOperation.REMOVE_ASSET)
            return

        if edit_intent == VisualEditIntent.ENLARGE_HERO and hero is not None:
            assert_element_editable(hero, ElementEditOperation.REPAIR_GEOMETRY)

    @staticmethod
    def _resolve_hero_element(plan: LayoutPlan) -> LayoutElement | None:
        if plan.hero_element_id is not None:
            hero = plan.element_by_id(plan.hero_element_id)
            if hero is not None:
                return hero
        heroes = plan.elements_by_role(LayoutElementRole.HERO_VISUAL)
        return heroes[0] if heroes else None

    @staticmethod
    def _resolve_target_element(
        plan: LayoutPlan,
        element_id: object,
    ) -> LayoutElement | None:
        if element_id is None:
            return None
        normalized = str(element_id).strip()
        if not normalized:
            return None
        return plan.element_by_id(normalized)

    def _replan(
        self,
        slide: SlideSpec,
        intent: VisualIntent,
        *,
        candidate_count: int,
        edit_intent: VisualEditIntent,
    ) -> VisualEditResult:
        intent = self._intents.save(intent)
        slide.visual_intent_id = intent.id
        self._presentations.save_slide(slide)

        art, design = self._resolve_art_and_design(slide, intent)
        llm = create_llm_provider(self._settings) if self._use_llm else None
        planner = LayoutPlanningService(self._session, llm=llm)
        current_plan = self._load_plan(slide)
        candidates = planner.generate_candidates(
            slide=slide,
            visual_intent_id=intent.id,
            art_direction_id=art.id if art else None,
            design_system_id=design.id,
            candidate_count=candidate_count,
            project_id=self._project_id_for_slide(slide),
            previous_layout_plan=current_plan,
        )
        saved_candidates: list[LayoutPlan] = []
        for plan, _report in candidates:
            saved_candidates.append(self._plans.save(plan))
        best = planner.select_best(
            candidates,
            previous_layout_plan=current_plan,
            style_preference=planner.last_style_preference,
        )
        best = self._plans.save(best)
        slide.layout_plan_id = best.id
        self._presentations.save_slide(slide)

        validation = LayoutValidationService().validate(
            best,
            design,
            require_source=True,
            drawing_hero=best.layout_family == LayoutFamily.DRAWING_FOCUS,
        )
        return VisualEditResult(
            slide_id=slide.id,
            intent=edit_intent,
            visual_intent=intent,
            layout_plan=best,
            validation=validation,
            message="已应用修改并重新生成版式。",
        )

    def _require_slide(self, slide_id: UUID) -> SlideSpec:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError(f"页面 {slide_id} 不存在")
        return slide

    def _load_intent(self, slide: SlideSpec) -> VisualIntent:
        intent = None
        if slide.visual_intent_id is not None:
            intent = self._intents.get(slide.visual_intent_id)
        if intent is None:
            intent = self._intents.get_by_slide(slide.id)
        if intent is None:
            llm = create_llm_provider(self._settings) if self._use_llm else None
            intent = VisualIntentService(self._session, llm=llm).generate_for_slide(
                slide,
                use_llm=self._use_llm,
            )
            slide.visual_intent_id = intent.id
            self._presentations.save_slide(slide)
        return intent

    def _load_plan(self, slide: SlideSpec) -> LayoutPlan | None:
        if slide.layout_plan_id is None:
            listed = self._plans.list_by_slide(slide.id)
            return listed[0] if listed else None
        return self._plans.get(slide.layout_plan_id)

    def _resolve_art_and_design(
        self,
        slide: SlideSpec,
        intent: VisualIntent,
    ) -> tuple[ArtDirection | None, DesignSystem]:
        presentation = self._presentations.get_presentation(slide.presentation_id)
        art = None
        design = None
        if intent.art_direction_id is not None:
            art = ArtDirectionRepository(self._session).get(intent.art_direction_id)
            if art is not None and art.design_system_id is not None:
                design = self._design_repo.get(art.design_system_id)
        if design is None and presentation is not None:
            arts = ArtDirectionRepository(self._session).list_by_project(presentation.project_id)
            for item in arts:
                if item.presentation_id == slide.presentation_id and item.design_system_id:
                    design = self._design_repo.get(item.design_system_id)
                    art = item
                    break
            if design is None and arts and arts[0].design_system_id:
                design = self._design_repo.get(arts[0].design_system_id)
                art = arts[0]
        if design is None:
            from archium.domain.visual.defaults import default_presentation_design_system

            design = self._design_repo.save(default_presentation_design_system())
        return art, design

    def _resolve_design_system(
        self,
        slide: SlideSpec,
        intent: VisualIntent | None,
    ) -> DesignSystem:
        _, design = self._resolve_art_and_design(slide, intent or self._load_intent(slide))
        return design

    @staticmethod
    def _default_hero_asset_id(slide: SlideSpec) -> UUID | None:
        for requirement in slide.visual_requirements:
            asset_id = requirement.primary_asset_id
            if asset_id is not None:
                return asset_id
        return None

    def _project_id_for_slide(self, slide: SlideSpec) -> UUID:
        presentation = self._presentations.get_presentation(slide.presentation_id)
        if presentation is None:
            raise WorkflowError("无法解析当前页面所属项目。")
        return presentation.project_id

    def _validate_asset_binding(
        self,
        slide: SlideSpec,
        *,
        content_ref: str,
        element: LayoutElement | None,
    ) -> str:
        resolver = AssetReferenceResolver(self._session, settings=self._settings)
        resolved = resolver.resolve(
            project_id=self._project_id_for_slide(slide),
            content_ref=content_ref,
            element=element,
        )
        return resolved.ref

    def _asset_context_for_plan(
        self,
        slide: SlideSpec,
        plan: LayoutPlan,
    ) -> AssetReferenceContext:
        return build_asset_reference_context(
            self._session,
            project_id=self._project_id_for_slide(slide),
            content_refs=content_refs_from_plan(plan),
            settings=self._settings,
        )

    def _invalidate_preview_cache(self, presentation_id: UUID, plan: LayoutPlan | None) -> None:
        if plan is None:
            return
        cache_path = (
            self._settings.output_path / "studio-previews" / str(presentation_id) / f"{plan.id}.png"
        )
        if cache_path.is_file():
            cache_path.unlink()
        try:
            from archium.application.visual.studio_scene_service import StudioSceneService

            StudioSceneService(self._session, settings=self._settings).refresh_after_layout_edit(
                presentation_id=presentation_id,
                plan=plan,
            )
        except Exception:
            # Scene refresh must not block layout edits; Studio will fall back to wireframe.
            return

"""Transaction executor for atomic visual editing operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.application.visual.element_geometry import (
    compute_element_placement,
    reduce_text_content,
)
from archium.application.visual.transaction_immutability import (
    bumped_layout_plan,
    restored_from_snapshot,
)
from archium.application.visual.transaction_repository_protocols import (
    LayoutPlanRepositoryProtocol,
    PresentationRepositoryProtocol,
    VisualIntentRepositoryProtocol,
)
from archium.application.visual.visual_history_service import VisualHistoryService
from archium.application.visual.visual_intent_presets import (
    apply_hero_asset,
    apply_visual_intent_preset,
    remove_primary_asset,
)
from archium.domain.enums import RevisionSource
from archium.domain.slide import SlideSpec
from archium.domain.visual.atomic_operation import AtomicOperation, OperationType
from archium.domain.visual.element_lock import ElementEditOperation, assert_element_editable
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.slide_edit_snapshot import SlideEditSnapshot
from archium.domain.visual.visual_intent import VisualIntent
from archium.exceptions import WorkflowError


@dataclass(frozen=True)
class TransactionExecutionContext:
    """Hooks required for safe composite operation execution."""

    replan_layout_change: Callable[
        [SlideSpec, VisualIntent, LayoutPlan, LayoutFamily],
        tuple[VisualIntent, LayoutPlan],
    ]
    validate_layout: Callable[[LayoutPlan], None]
    replan_current_intent: Callable[
        [SlideSpec, VisualIntent, LayoutPlan],
        tuple[VisualIntent, LayoutPlan],
    ] | None = None
    resolve_asset_ref: Callable[[str, LayoutElement | None], str] | None = None


@dataclass
class Checkpoint:
    """A savepoint in a transaction that can be restored."""

    checkpoint_id: UUID
    slide_id: UUID
    visual_intent_snapshot: dict[str, Any] | None
    layout_plan_snapshot: dict[str, Any] | None
    operation_index: int


@dataclass(frozen=True)
class _ExecutedStepState:
    """Post-operation state captured for per-step revision history."""

    operation: AtomicOperation
    visual_intent: VisualIntent | None
    layout_plan: LayoutPlan | None


@dataclass
class TransactionResult:
    """Result of a transaction execution."""

    success: bool
    executed_operations: list[AtomicOperation]
    revision_chain_id: UUID | None
    error: Exception | None = None
    error_at_step: int | None = None


class TransactionExecutor:
    """
    Execute sequences of atomic operations with transaction support.

    Features:
    - Sequential execution with checkpointing
    - Automatic rollback on failure
    - Revision chain management
    - Constraint validation
    """

    def __init__(
        self,
        session: Session,
        history_service: VisualHistoryService,
    ) -> None:
        self._session = session
        self._history = history_service

    def execute_transaction(
        self,
        operations: list[AtomicOperation],
        slide_id: UUID,
        slide_snapshot: SlideEditSnapshot,
        *,
        intents_repo: VisualIntentRepositoryProtocol,
        plans_repo: LayoutPlanRepositoryProtocol,
        presentations_repo: PresentationRepositoryProtocol,
        execution_context: TransactionExecutionContext | None = None,
    ) -> TransactionResult:
        """
        Execute a sequence of operations as a transaction.

        Args:
            operations: Ordered list of atomic operations
            slide_id: Target slide ID
            slide_snapshot: Current slide state
            intents_repo: VisualIntentRepository for state access
            plans_repo: LayoutPlanRepository for state access
            presentations_repo: PresentationRepository for state access
            execution_context: Required hooks for layout replanning and validation

        Returns:
            TransactionResult with success status and error details

        Notes:
            - All operations execute within a database transaction
            - Each operation creates a checkpoint before execution
            - On failure, all operations are rolled back
            - Revision history is recorded before commit so data and revisions
              share the same atomic boundary
        """
        revision_chain_id = uuid4()
        checkpoints: list[Checkpoint] = []
        executed: list[AtomicOperation] = []
        step_states: list[_ExecutedStepState] = []
        slide: SlideSpec | None = None

        try:
            slide = presentations_repo.get_slide(slide_id)
            if not slide:
                raise WorkflowError(f"Slide {slide_id} not found")

            visual_intent = (
                intents_repo.get(slide.visual_intent_id)
                if slide.visual_intent_id
                else None
            )
            layout_plan = (
                plans_repo.get(slide.layout_plan_id)
                if slide.layout_plan_id
                else None
            )

            for i, operation in enumerate(operations):
                checkpoint = self._create_checkpoint(
                    slide_id=slide_id,
                    visual_intent=visual_intent,
                    layout_plan=layout_plan,
                    operation_index=i,
                )
                checkpoints.append(checkpoint)

                visual_intent, layout_plan = self._execute_operation(
                    operation=operation,
                    slide=slide,
                    visual_intent=visual_intent,
                    layout_plan=layout_plan,
                    intents_repo=intents_repo,
                    plans_repo=plans_repo,
                    execution_context=execution_context,
                )

                if layout_plan is not None and execution_context is not None:
                    execution_context.validate_layout(layout_plan)

                executed.append(operation)
                step_states.append(
                    _ExecutedStepState(
                        operation=operation,
                        visual_intent=(
                            visual_intent.model_copy(deep=True)
                            if visual_intent is not None
                            else None
                        ),
                        layout_plan=(
                            layout_plan.model_copy(deep=True)
                            if layout_plan is not None
                            else None
                        ),
                    )
                )

            if step_states:
                final_step = step_states[-1]
                self._history.record_state(
                    slide=slide,
                    visual_intent=final_step.visual_intent,
                    layout_plan=final_step.layout_plan,
                    change_source=RevisionSource.MANUAL_EDIT,
                    note=(
                        f"Transaction {revision_chain_id} complete "
                        f"({len(step_states)} step(s))"
                    ),
                )

            self._session.flush()
            self._session.commit()

            return TransactionResult(
                success=True,
                executed_operations=executed,
                revision_chain_id=revision_chain_id,
                error=None,
            )

        except Exception as e:
            self._session.rollback()

            if slide is not None:
                self._restore_from_checkpoints(
                    checkpoints=checkpoints,
                    intents_repo=intents_repo,
                    plans_repo=plans_repo,
                )
                try:
                    self._session.commit()
                except Exception:
                    self._session.rollback()

            return TransactionResult(
                success=False,
                executed_operations=executed,
                revision_chain_id=None,
                error=e,
                error_at_step=len(executed),
            )

    def _create_checkpoint(
        self,
        slide_id: UUID,
        visual_intent: VisualIntent | None,
        layout_plan: LayoutPlan | None,
        operation_index: int,
    ) -> Checkpoint:
        """Create a checkpoint of the current state."""
        return Checkpoint(
            checkpoint_id=uuid4(),
            slide_id=slide_id,
            visual_intent_snapshot=(
                self._snapshot_visual_intent(visual_intent)
                if visual_intent
                else None
            ),
            layout_plan_snapshot=(
                self._snapshot_layout_plan(layout_plan)
                if layout_plan
                else None
            ),
            operation_index=operation_index,
        )

    def _execute_operation(
        self,
        operation: AtomicOperation,
        slide: SlideSpec,
        visual_intent: VisualIntent | None,
        layout_plan: LayoutPlan | None,
        intents_repo: VisualIntentRepositoryProtocol,
        plans_repo: LayoutPlanRepositoryProtocol,
        execution_context: TransactionExecutionContext | None,
    ) -> tuple[VisualIntent | None, LayoutPlan | None]:
        """Execute a single atomic operation."""
        op_type = operation.operation_type

        if op_type == OperationType.LOCK:
            layout_plan = self._apply_lock_state(
                layout_plan,
                operation,
                locked=True,
                plans_repo=plans_repo,
            )
            return visual_intent, layout_plan

        if op_type == OperationType.UNLOCK:
            layout_plan = self._apply_lock_state(
                layout_plan,
                operation,
                locked=False,
                plans_repo=plans_repo,
            )
            return visual_intent, layout_plan

        if op_type == OperationType.MOVE:
            layout_plan = self._move_element(layout_plan, operation)
            plans_repo.save(layout_plan)
            return visual_intent, layout_plan

        if op_type == OperationType.SWAP:
            layout_plan = self._swap_elements(layout_plan, operation)
            plans_repo.save(layout_plan)
            return visual_intent, layout_plan

        if op_type == OperationType.REDUCE_TEXT:
            visual_intent, layout_plan = self._reduce_text(
                visual_intent,
                layout_plan,
                operation,
                intents_repo=intents_repo,
                plans_repo=plans_repo,
            )
            return visual_intent, layout_plan

        if op_type == OperationType.UPDATE_ELEMENT_TEXT:
            layout_plan = self._update_element_text(layout_plan, operation)
            plans_repo.save(layout_plan)
            return visual_intent, layout_plan

        if op_type == OperationType.SET_ELEMENT_ASSET:
            layout_plan = self._set_element_asset(
                layout_plan,
                operation,
                execution_context=execution_context,
            )
            plans_repo.save(layout_plan)
            return visual_intent, layout_plan

        if op_type in {OperationType.SET_HERO_ASSET, OperationType.REMOVE_ASSET}:
            visual_intent, layout_plan = self._apply_intent_asset_change(
                slide,
                visual_intent,
                layout_plan,
                operation,
                execution_context=execution_context,
                intents_repo=intents_repo,
                plans_repo=plans_repo,
            )
            return visual_intent, layout_plan

        if operation.modifies_layout:
            if layout_plan is None:
                raise WorkflowError(f"Cannot execute {op_type}: no layout plan")

            if op_type == OperationType.CHANGE_LAYOUT:
                layout_family = operation.params.get("layout_family")
                if not isinstance(layout_family, LayoutFamily):
                    raise WorkflowError("change_layout requires layout_family")
                if visual_intent is None:
                    raise WorkflowError("change_layout requires visual intent")
                if execution_context is None:
                    raise WorkflowError("change_layout requires layout replanning context")
                visual_intent, layout_plan = execution_context.replan_layout_change(
                    slide,
                    visual_intent,
                    layout_plan,
                    layout_family,
                )
                intents_repo.save(visual_intent)
                plans_repo.save(layout_plan)

            elif op_type == OperationType.ENLARGE_HERO:
                layout_plan = self._enlarge_hero(layout_plan, operation)
                plans_repo.save(layout_plan)

            elif op_type == OperationType.INCREASE_WHITESPACE:
                layout_plan = self._increase_whitespace(layout_plan)
                plans_repo.save(layout_plan)

            elif op_type == OperationType.RESIZE:
                layout_plan = self._resize_element(layout_plan, operation)
                plans_repo.save(layout_plan)

            else:
                raise WorkflowError(f"Unknown layout operation: {op_type}")

            return visual_intent, layout_plan

        raise WorkflowError(f"Unknown operation type: {op_type}")

    def _apply_lock_state(
        self,
        layout_plan: LayoutPlan | None,
        operation: AtomicOperation,
        *,
        locked: bool,
        plans_repo: LayoutPlanRepositoryProtocol,
    ) -> LayoutPlan:
        if layout_plan is None:
            action = "lock" if locked else "unlock"
            raise WorkflowError(f"Cannot {action} element: no layout plan")
        element_id = operation.target_element_id
        if not element_id:
            raise WorkflowError("Lock operation requires target_element_id")

        target_id = str(element_id)
        updated_elements: list[LayoutElement] = []
        changed = False
        for element in layout_plan.elements:
            if element.id == target_id:
                updated_elements.append(element.model_copy(update={"locked": locked}))
                changed = True
            else:
                updated_elements.append(element)

        if not changed:
            action = "锁定" if locked else "解锁"
            raise WorkflowError(f"未找到可{action}的元素：{target_id}")

        return plans_repo.save(bumped_layout_plan(layout_plan, elements=updated_elements))

    @staticmethod
    def _assert_no_element_overlap(
        layout_plan: LayoutPlan,
        *,
        target_id: str,
        x: float,
        y: float,
        width: float,
        height: float,
        tolerance: float = 0.05,
    ) -> None:
        from archium.infrastructure.layout.geometry import Rect

        moved = Rect(x, y, width, height)
        for other in layout_plan.elements:
            if other.id == target_id:
                continue
            other_rect = Rect(other.x, other.y, other.width, other.height)
            if moved.overlaps(other_rect, tolerance=tolerance):
                raise WorkflowError(f"移动后会与元素 `{other.id}` 重叠，无法执行")

    def _move_element(
        self,
        layout_plan: LayoutPlan | None,
        operation: AtomicOperation,
    ) -> LayoutPlan:
        if layout_plan is None:
            raise WorkflowError("Cannot move element: no layout plan")
        element_id = operation.target_element_id
        if not element_id:
            raise WorkflowError("Move operation requires target_element_id")

        target_id = str(element_id)
        position = str(operation.params.get("position") or "right")
        updated_elements: list[LayoutElement] = []
        changed = False
        for element in layout_plan.elements:
            if element.id != target_id:
                updated_elements.append(element)
                continue
            assert_element_editable(element, ElementEditOperation.REPAIR_GEOMETRY)
            x, y, width, height = compute_element_placement(
                element,
                layout_plan,
                position,
                absolute_x=operation.params.get("x"),
                absolute_y=operation.params.get("y"),
            )
            self._assert_no_element_overlap(
                layout_plan,
                target_id=target_id,
                x=x,
                y=y,
                width=width,
                height=height,
            )
            updated_elements.append(
                element.model_copy(update={"x": x, "y": y, "width": width, "height": height})
            )
            changed = True

        if not changed:
            raise WorkflowError(f"未找到可移动的元素：{target_id}")

        return bumped_layout_plan(layout_plan, elements=updated_elements)

    def _swap_elements(
        self,
        layout_plan: LayoutPlan | None,
        operation: AtomicOperation,
    ) -> LayoutPlan:
        if layout_plan is None:
            raise WorkflowError("Cannot swap elements: no layout plan")
        first_id = operation.target_element_id
        second_id = operation.params.get("second_element_id")
        if not first_id or not second_id:
            raise WorkflowError("Swap operation requires two element ids")

        first = layout_plan.element_by_id(str(first_id))
        second = layout_plan.element_by_id(str(second_id))
        if first is None or second is None:
            raise WorkflowError("无法解析 swap 目标元素")

        assert_element_editable(first, ElementEditOperation.REPAIR_GEOMETRY)
        assert_element_editable(second, ElementEditOperation.REPAIR_GEOMETRY)

        updated_elements: list[LayoutElement] = []
        for element in layout_plan.elements:
            if element.id == first.id:
                updated_elements.append(
                    element.model_copy(
                        update={
                            "x": second.x,
                            "y": second.y,
                            "width": second.width,
                            "height": second.height,
                        }
                    )
                )
            elif element.id == second.id:
                updated_elements.append(
                    element.model_copy(
                        update={
                            "x": first.x,
                            "y": first.y,
                            "width": first.width,
                            "height": first.height,
                        }
                    )
                )
            else:
                updated_elements.append(element)

        return bumped_layout_plan(layout_plan, elements=updated_elements)

    def _resize_element(
        self,
        layout_plan: LayoutPlan,
        operation: AtomicOperation,
    ) -> LayoutPlan:
        element_id = operation.target_element_id
        if not element_id:
            raise WorkflowError("Resize operation requires target_element_id")
        scale_factor = float(operation.params.get("scale_factor", 1.0))
        if scale_factor <= 0:
            raise WorkflowError("Resize scale_factor must be positive")

        target_id = str(element_id)
        updated_elements: list[LayoutElement] = []
        changed = False
        for element in layout_plan.elements:
            if element.id != target_id:
                updated_elements.append(element)
                continue
            assert_element_editable(element, ElementEditOperation.REPAIR_GEOMETRY)
            new_width = element.width * scale_factor
            new_height = element.height * scale_factor
            center_x = element.x + element.width / 2
            center_y = element.y + element.height / 2
            new_x = center_x - new_width / 2
            new_y = center_y - new_height / 2
            if (
                new_x < 0
                or new_y < 0
                or new_x + new_width > layout_plan.page_width
                or new_y + new_height > layout_plan.page_height
            ):
                raise WorkflowError("缩放后元素会超出页面边界，无法执行")
            updated_elements.append(
                element.model_copy(
                    update={
                        "x": new_x,
                        "y": new_y,
                        "width": new_width,
                        "height": new_height,
                    }
                )
            )
            changed = True

        if not changed:
            raise WorkflowError(f"未找到可缩放的元素：{target_id}")

        return bumped_layout_plan(layout_plan, elements=updated_elements)

    def _reduce_text(
        self,
        visual_intent: VisualIntent | None,
        layout_plan: LayoutPlan | None,
        operation: AtomicOperation,
        *,
        intents_repo: VisualIntentRepositoryProtocol,
        plans_repo: LayoutPlanRepositoryProtocol,
    ) -> tuple[VisualIntent | None, LayoutPlan | None]:
        if layout_plan is None:
            raise WorkflowError("Cannot reduce text: no layout plan")

        target_id = str(operation.target_element_id) if operation.target_element_id else None
        reduce_lines = operation.params.get("reduce_lines")
        updated_elements: list[LayoutElement] = []
        changed = False

        for element in layout_plan.elements:
            if target_id is not None and element.id != target_id:
                updated_elements.append(element)
                continue
            if element.content_type != LayoutContentType.TEXT or not element.text_content:
                updated_elements.append(element)
                continue
            if target_id is None and changed:
                updated_elements.append(element)
                continue

            assert_element_editable(element, ElementEditOperation.UPDATE_TEXT)
            new_text = reduce_text_content(
                element.text_content,
                reduce_lines=int(reduce_lines) if reduce_lines is not None else None,
            )
            updated_elements.append(element.model_copy(update={"text_content": new_text}))
            changed = True

        if not changed:
            raise WorkflowError("未找到可缩减文字的元素")

        saved_plan = plans_repo.save(bumped_layout_plan(layout_plan, elements=updated_elements))

        if visual_intent is not None:
            visual_intent = apply_visual_intent_preset(visual_intent, "reduce_text")
            visual_intent = intents_repo.save(visual_intent)

        return visual_intent, saved_plan

    def _update_element_text(
        self,
        layout_plan: LayoutPlan | None,
        operation: AtomicOperation,
    ) -> LayoutPlan:
        if layout_plan is None:
            raise WorkflowError("Cannot update text: no layout plan")
        element_id = operation.target_element_id
        if not element_id:
            raise WorkflowError("Update text requires target_element_id")
        text = str(operation.params.get("text") or "").strip()
        if not text:
            raise WorkflowError("文字内容不能为空")

        target_id = str(element_id)
        updated_elements: list[LayoutElement] = []
        changed = False
        for element in layout_plan.elements:
            if element.id != target_id:
                updated_elements.append(element)
                continue
            assert_element_editable(element, ElementEditOperation.UPDATE_TEXT)
            updated_elements.append(element.model_copy(update={"text_content": text}))
            changed = True

        if not changed:
            raise WorkflowError(f"未找到可更新文字的元素：{target_id}")

        return bumped_layout_plan(layout_plan, elements=updated_elements)

    def _set_element_asset(
        self,
        layout_plan: LayoutPlan | None,
        operation: AtomicOperation,
        *,
        execution_context: TransactionExecutionContext | None,
    ) -> LayoutPlan:
        if layout_plan is None:
            raise WorkflowError("Cannot set element asset: no layout plan")
        if execution_context is None or execution_context.resolve_asset_ref is None:
            raise WorkflowError("set_element_asset requires asset resolution context")

        element_id = operation.target_element_id
        if not element_id:
            raise WorkflowError("Set element asset requires target_element_id")
        content_ref = str(
            operation.params.get("content_ref") or operation.params.get("asset_id") or ""
        ).strip()
        if not content_ref:
            raise WorkflowError("请指定素材引用")

        target_id = str(element_id)
        updated_elements: list[LayoutElement] = []
        changed = False
        for element in layout_plan.elements:
            if element.id != target_id:
                updated_elements.append(element)
                continue
            assert_element_editable(element, ElementEditOperation.SET_ASSET)
            resolved_ref = execution_context.resolve_asset_ref(content_ref, element)
            updated_elements.append(element.model_copy(update={"content_ref": resolved_ref}))
            changed = True

        if not changed:
            raise WorkflowError(f"未找到可替换素材的元素：{target_id}")

        return bumped_layout_plan(layout_plan, elements=updated_elements)

    def _apply_intent_asset_change(
        self,
        slide: SlideSpec,
        visual_intent: VisualIntent | None,
        layout_plan: LayoutPlan | None,
        operation: AtomicOperation,
        *,
        execution_context: TransactionExecutionContext | None,
        intents_repo: VisualIntentRepositoryProtocol,
        plans_repo: LayoutPlanRepositoryProtocol,
    ) -> tuple[VisualIntent | None, LayoutPlan | None]:
        if visual_intent is None:
            raise WorkflowError("Asset operations require visual intent")
        if layout_plan is None:
            raise WorkflowError("Asset operations require layout plan")
        if execution_context is None or execution_context.replan_current_intent is None:
            raise WorkflowError("Asset operations require layout replanning context")

        hero = self._resolve_hero_element(layout_plan)
        if operation.operation_type == OperationType.SET_HERO_ASSET:
            if hero is not None:
                assert_element_editable(hero, ElementEditOperation.SET_HERO)
            asset_id = operation.params.get("asset_id")
            if asset_id is None:
                raise WorkflowError("请指定主图素材")
            visual_intent = apply_hero_asset(visual_intent, UUID(str(asset_id)))
        elif operation.operation_type == OperationType.REMOVE_ASSET:
            if hero is not None:
                assert_element_editable(hero, ElementEditOperation.REMOVE_ASSET)
            visual_intent = remove_primary_asset(visual_intent)
        else:
            raise WorkflowError(f"Unknown asset operation: {operation.operation_type}")

        visual_intent = intents_repo.save(visual_intent)
        return execution_context.replan_current_intent(slide, visual_intent, layout_plan)

    def _enlarge_hero(
        self,
        layout_plan: LayoutPlan,
        operation: AtomicOperation,
    ) -> LayoutPlan:
        scale_factor = float(operation.params.get("scale_factor", 1.3))
        if scale_factor <= 1.0:
            raise WorkflowError("enlarge_hero requires scale_factor > 1.0")

        hero = self._resolve_hero_element(layout_plan)
        if hero is None:
            raise WorkflowError("当前页面没有可放大的主图元素")

        assert_element_editable(hero, ElementEditOperation.REPAIR_GEOMETRY)

        old_width = hero.width
        old_height = hero.height
        new_width = old_width * scale_factor
        new_height = old_height * scale_factor
        center_x = hero.x + old_width / 2
        center_y = hero.y + old_height / 2
        new_x = center_x - new_width / 2
        new_y = center_y - new_height / 2

        if (
            new_x < 0
            or new_y < 0
            or new_x + new_width > layout_plan.page_width
            or new_y + new_height > layout_plan.page_height
        ):
            raise WorkflowError("放大主图后会超出页面边界，无法执行")

        updated_elements = []
        for element in layout_plan.elements:
            if element.id != hero.id:
                updated_elements.append(element)
                continue
            updated_elements.append(
                element.model_copy(
                    update={
                        "x": new_x,
                        "y": new_y,
                        "width": new_width,
                        "height": new_height,
                    }
                )
            )

        return bumped_layout_plan(layout_plan, elements=updated_elements)

    def _increase_whitespace(self, layout_plan: LayoutPlan) -> LayoutPlan:
        updated_elements: list[LayoutElement] = []
        for element in layout_plan.elements:
            if element.locked:
                updated_elements.append(element)
                continue
            assert_element_editable(element, ElementEditOperation.REPAIR_GEOMETRY)
            center_x = element.x + element.width / 2
            center_y = element.y + element.height / 2
            new_width = element.width * 0.9
            new_height = element.height * 0.9
            updated_elements.append(
                element.model_copy(
                    update={
                        "x": center_x - new_width / 2,
                        "y": center_y - new_height / 2,
                        "width": new_width,
                        "height": new_height,
                    }
                )
            )

        return bumped_layout_plan(layout_plan, elements=updated_elements)

    @staticmethod
    def _resolve_hero_element(layout_plan: LayoutPlan) -> LayoutElement | None:
        if layout_plan.hero_element_id is not None:
            hero = layout_plan.element_by_id(layout_plan.hero_element_id)
            if hero is not None:
                return hero

        for role in (LayoutElementRole.HERO_VISUAL,):
            heroes = layout_plan.elements_by_role(role)
            if heroes:
                return heroes[0]
        return None

    def _restore_from_checkpoints(
        self,
        checkpoints: list[Checkpoint],
        intents_repo: VisualIntentRepositoryProtocol,
        plans_repo: LayoutPlanRepositoryProtocol,
    ) -> None:
        """Restore state from checkpoints (application-level rollback)."""
        if not checkpoints:
            return

        first_checkpoint = checkpoints[0]

        if first_checkpoint.visual_intent_snapshot:
            visual_intent = self._restore_visual_intent(
                first_checkpoint.visual_intent_snapshot,
                intents_repo,
            )
            if visual_intent:
                intents_repo.save(visual_intent)

        if first_checkpoint.layout_plan_snapshot:
            layout_plan = self._restore_layout_plan(
                first_checkpoint.layout_plan_snapshot,
                plans_repo,
            )
            if layout_plan:
                plans_repo.save(layout_plan)

    def _snapshot_visual_intent(self, intent: VisualIntent) -> dict[str, Any]:
        """Create a snapshot of visual intent state."""
        return intent.model_dump(mode="json")

    def _snapshot_layout_plan(self, plan: LayoutPlan) -> dict[str, Any]:
        """Create a snapshot of layout plan state."""
        return plan.model_dump(mode="json")

    def _restore_visual_intent(
        self,
        snapshot: dict[str, Any],
        intents_repo: VisualIntentRepositoryProtocol,
    ) -> VisualIntent | None:
        """Restore visual intent from snapshot."""
        intent_id = UUID(snapshot["id"])
        current = intents_repo.get(intent_id)
        if current is None:
            return None
        restored = VisualIntent.model_validate(snapshot)
        return restored_from_snapshot(restored)

    def _restore_layout_plan(
        self,
        snapshot: dict[str, Any],
        plans_repo: LayoutPlanRepositoryProtocol,
    ) -> LayoutPlan | None:
        """Restore layout plan from snapshot."""
        plan_id = UUID(snapshot["id"])
        current = plans_repo.get(plan_id)
        if current is None:
            return None
        restored = LayoutPlan.model_validate(snapshot)
        return restored_from_snapshot(restored)

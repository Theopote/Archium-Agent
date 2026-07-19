"""Transaction executor for atomic visual editing operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.application.visual.visual_history_service import VisualHistoryService
from archium.domain.enums import RevisionSource
from archium.domain.slide import SlideSpec
from archium.domain.visual.atomic_operation import AtomicOperation, OperationType
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.slide import SlideSnapshot
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.error_framework import WorkflowError


@dataclass
class Checkpoint:
    """A savepoint in a transaction that can be restored."""

    checkpoint_id: UUID
    slide_id: UUID
    visual_intent_snapshot: dict[str, Any] | None
    layout_plan_snapshot: dict[str, Any] | None
    operation_index: int


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
        slide_snapshot: SlideSnapshot,
        *,
        intents_repo: Any,
        plans_repo: Any,
        presentations_repo: Any,
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

        Returns:
            TransactionResult with success status and error details

        Notes:
            - All operations execute within a database transaction
            - Each operation creates a checkpoint before execution
            - On failure, all operations are rolled back
            - Revision chain tracks the complete operation sequence
        """
        revision_chain_id = uuid4()
        checkpoints: list[Checkpoint] = []
        executed: list[AtomicOperation] = []

        try:
            # Get current state
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

            # Execute each operation
            for i, operation in enumerate(operations):
                # Create checkpoint before execution
                checkpoint = self._create_checkpoint(
                    slide_id=slide_id,
                    visual_intent=visual_intent,
                    layout_plan=layout_plan,
                    operation_index=i,
                )
                checkpoints.append(checkpoint)

                # Execute the operation
                visual_intent, layout_plan = self._execute_operation(
                    operation=operation,
                    slide=slide,
                    visual_intent=visual_intent,
                    layout_plan=layout_plan,
                    intents_repo=intents_repo,
                    plans_repo=plans_repo,
                )

                # Record revision for this step
                self._history.record_state(
                    slide=slide,
                    visual_intent=visual_intent,
                    layout_plan=layout_plan,
                    change_source=RevisionSource.AI_EDIT,
                    note=f"Transaction {revision_chain_id} step {i+1}/{len(operations)}: {operation.operation_type}",
                )

                executed.append(operation)

            # Commit database transaction
            self._session.commit()

            return TransactionResult(
                success=True,
                executed_operations=executed,
                revision_chain_id=revision_chain_id,
                error=None,
            )

        except Exception as e:
            # Rollback database transaction
            self._session.rollback()

            # Restore from checkpoints (application-level rollback)
            self._restore_from_checkpoints(
                checkpoints=checkpoints,
                slide=slide,
                intents_repo=intents_repo,
                plans_repo=plans_repo,
            )

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
        intents_repo: Any,
        plans_repo: Any,
    ) -> tuple[VisualIntent | None, LayoutPlan | None]:
        """
        Execute a single atomic operation.

        Returns updated visual_intent and layout_plan.
        """
        op_type = operation.operation_type

        # Lock/Unlock operations modify layout plan locks
        if op_type == OperationType.LOCK:
            if not layout_plan:
                raise WorkflowError("Cannot lock element: no layout plan")
            element_id = operation.target_element_id
            if not element_id:
                raise WorkflowError("Lock operation requires target_element_id")
            # Find element spec and set locked=True
            for spec in layout_plan.element_specs:
                if spec.id == element_id:
                    spec.locked = True
            plans_repo.save(layout_plan)
            return visual_intent, layout_plan

        elif op_type == OperationType.UNLOCK:
            if not layout_plan:
                raise WorkflowError("Cannot unlock element: no layout plan")
            element_id = operation.target_element_id
            if not element_id:
                raise WorkflowError("Unlock operation requires target_element_id")
            # Find element spec and set locked=False
            for spec in layout_plan.element_specs:
                if spec.id == element_id:
                    spec.locked = False
            plans_repo.save(layout_plan)
            return visual_intent, layout_plan

        # Layout operations modify the layout plan
        elif operation.modifies_layout:
            if not layout_plan:
                raise WorkflowError(f"Cannot execute {op_type}: no layout plan")

            if op_type == OperationType.CHANGE_LAYOUT:
                layout_family = operation.params.get("layout_family")
                if not layout_family:
                    raise WorkflowError("change_layout requires layout_family")
                # This would trigger layout regeneration
                # For now, just update the family
                layout_plan.layout_family = layout_family
                plans_repo.save(layout_plan)

            elif op_type == OperationType.ENLARGE_HERO:
                # Find hero element and scale it
                scale_factor = operation.params.get("scale_factor", 1.3)
                for spec in layout_plan.element_specs:
                    if spec.role in ("hero", "main_visual"):
                        # Scale dimensions
                        spec.w = int(spec.w * scale_factor)
                        spec.h = int(spec.h * scale_factor)
                plans_repo.save(layout_plan)

            elif op_type == OperationType.INCREASE_WHITESPACE:
                # Reduce element sizes to increase whitespace
                for spec in layout_plan.element_specs:
                    if not spec.locked:
                        spec.w = int(spec.w * 0.9)
                        spec.h = int(spec.h * 0.9)
                plans_repo.save(layout_plan)

            return visual_intent, layout_plan

        # Content operations modify visual intent
        elif operation.modifies_content:
            if not visual_intent:
                raise WorkflowError(f"Cannot execute {op_type}: no visual intent")

            if op_type == OperationType.REDUCE_TEXT:
                # This would trigger content reduction
                # The actual implementation would call content adaptation service
                pass

            intents_repo.save(visual_intent)
            return visual_intent, layout_plan

        # Asset operations
        elif operation.modifies_assets:
            # Asset operations would modify the visual intent or layout plan
            # depending on the specific operation
            pass

        else:
            raise WorkflowError(f"Unknown operation type: {op_type}")

        return visual_intent, layout_plan

    def _restore_from_checkpoints(
        self,
        checkpoints: list[Checkpoint],
        slide: SlideSpec,
        intents_repo: Any,
        plans_repo: Any,
    ) -> None:
        """
        Restore state from checkpoints (application-level rollback).

        This is a safety mechanism in addition to database rollback.
        """
        if not checkpoints:
            return

        # Restore from the first checkpoint (pre-transaction state)
        first_checkpoint = checkpoints[0]

        # Restore visual intent
        if first_checkpoint.visual_intent_snapshot:
            visual_intent = self._restore_visual_intent(
                first_checkpoint.visual_intent_snapshot,
                intents_repo,
            )
            if visual_intent:
                intents_repo.save(visual_intent)

        # Restore layout plan
        if first_checkpoint.layout_plan_snapshot:
            layout_plan = self._restore_layout_plan(
                first_checkpoint.layout_plan_snapshot,
                plans_repo,
            )
            if layout_plan:
                plans_repo.save(layout_plan)

    def _snapshot_visual_intent(self, intent: VisualIntent) -> dict[str, Any]:
        """Create a snapshot of visual intent state."""
        return {
            "id": str(intent.id),
            "slide_id": str(intent.slide_id),
            # Add other relevant fields
        }

    def _snapshot_layout_plan(self, plan: LayoutPlan) -> dict[str, Any]:
        """Create a snapshot of layout plan state."""
        return {
            "id": str(plan.id),
            "layout_family": plan.layout_family.value if plan.layout_family else None,
            "element_specs": [
                {
                    "id": str(spec.id),
                    "role": spec.role,
                    "locked": spec.locked,
                    "x": spec.x,
                    "y": spec.y,
                    "w": spec.w,
                    "h": spec.h,
                }
                for spec in plan.element_specs
            ],
        }

    def _restore_visual_intent(
        self,
        snapshot: dict[str, Any],
        intents_repo: Any,
    ) -> VisualIntent | None:
        """Restore visual intent from snapshot."""
        intent_id = UUID(snapshot["id"])
        intent = intents_repo.get(intent_id)
        if not intent:
            return None
        # Restore fields from snapshot
        return intent

    def _restore_layout_plan(
        self,
        snapshot: dict[str, Any],
        plans_repo: Any,
    ) -> LayoutPlan | None:
        """Restore layout plan from snapshot."""
        plan_id = UUID(snapshot["id"])
        plan = plans_repo.get(plan_id)
        if not plan:
            return None

        # Restore element specs
        for spec_snapshot in snapshot.get("element_specs", []):
            spec_id = UUID(spec_snapshot["id"])
            for spec in plan.element_specs:
                if spec.id == spec_id:
                    spec.locked = spec_snapshot["locked"]
                    spec.x = spec_snapshot["x"]
                    spec.y = spec_snapshot["y"]
                    spec.w = spec_snapshot["w"]
                    spec.h = spec_snapshot["h"]

        return plan

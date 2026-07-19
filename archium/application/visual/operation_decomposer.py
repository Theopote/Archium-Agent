"""Decompose parsed intents into atomic operations for transactional execution."""

from __future__ import annotations

import re
from uuid import UUID

from archium.domain.visual.atomic_operation import (
    AtomicOperation,
    ChangeLayoutOperation,
    EnlargeHeroOperation,
    IncreaseWhitespaceOperation,
    LockOperation,
    MoveOperation,
    ReduceTextOperation,
    ResizeOperation,
    SwapOperation,
    UnlockOperation,
    intent_to_operation_type,
    OperationType,
)
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.nlp_parser import ModifierType, ParsedIntent
from archium.domain.visual.slide import SlideSnapshot
from archium.exceptions import WorkflowError


class OperationDecomposer:
    """
    Decompose complex parsed intents into sequences of atomic operations.

    Handles:
    - Constraint extraction (lock/preserve operations)
    - Multi-step operation sequencing
    - Semantic operation expansion
    - Relative adjustment translation
    """

    def decompose(
        self,
        parsed_intent: ParsedIntent,
        slide_snapshot: SlideSnapshot,
    ) -> list[AtomicOperation]:
        """
        Decompose a parsed intent into atomic operations.

        Operations are ordered:
        1. Lock operations (from constraints)
        2. Main operation
        3. Additional operations (from multi-step)

        Args:
            parsed_intent: The parsed natural language intent
            slide_snapshot: Current slide state for element resolution

        Returns:
            List of atomic operations in execution order

        Raises:
            WorkflowError: If intent cannot be decomposed
        """
        operations: list[AtomicOperation] = []

        # Step 1: Extract lock operations from constraints
        lock_ops = self._extract_lock_operations(
            parsed_intent.modifiers,
            slide_snapshot,
        )
        operations.extend(lock_ops)

        # Step 2: Create main operation
        main_op = self._create_main_operation(
            parsed_intent.intent,
            parsed_intent.params,
            slide_snapshot,
        )
        if main_op:
            operations.append(main_op)

        # Step 3: Extract multi-step operations
        multi_step_ops = self._extract_multi_step_operations(
            parsed_intent.params,
            slide_snapshot,
        )
        if main_op is not None and main_op.operation_type == OperationType.MOVE:
            multi_step_ops = [
                op
                for op in multi_step_ops
                if not (
                    op.operation_type == OperationType.MOVE
                    and op.target_element_id == main_op.target_element_id
                )
            ]
        operations.extend(multi_step_ops)

        if not operations:
            raise WorkflowError(
                f"Cannot decompose intent {parsed_intent.intent}: no valid operations"
            )

        return operations

    def _extract_lock_operations(
        self,
        modifiers: list,
        slide_snapshot: SlideSnapshot,
    ) -> list[AtomicOperation]:
        """Extract lock operations from constraint modifiers."""
        lock_ops: list[AtomicOperation] = []

        for modifier in modifiers:
            if modifier.type != ModifierType.CONSTRAINT:
                continue

            # Check if this is a "preserve" or "keep unchanged" constraint
            if modifier.value in ("preserve", "dont_touch"):
                element_id = self._resolve_element_name(
                    modifier.target,
                    slide_snapshot,
                )
                if element_id:
                    lock_ops.append(LockOperation(element_id))

        return lock_ops

    def _create_main_operation(
        self,
        intent: VisualEditIntent,
        params: dict,
        slide_snapshot: SlideSnapshot,
    ) -> AtomicOperation | None:
        """Create the main operation from the intent."""
        # Special handling for restore (not a regular operation)
        if intent == VisualEditIntent.RESTORE_PREVIOUS:
            return None

        # Map intent to operation type
        try:
            op_type = intent_to_operation_type(intent)
        except ValueError:
            raise WorkflowError(f"Cannot map intent {intent} to operation")

        # Build operation based on type
        if op_type == OperationType.CHANGE_LAYOUT:
            layout_family = params.get("layout_family")
            if isinstance(layout_family, LayoutFamily):
                return ChangeLayoutOperation(layout_family)
            target = params.get("target")
            position = params.get("position", "right")
            if target:
                element_id = self._resolve_element_name(target, slide_snapshot)
                if element_id:
                    return MoveOperation(element_id, str(position), preserve_size=True)
            if params.get("multi_step_operations"):
                return None
            raise WorkflowError(
                "change_layout requires layout_family or a movable target with position"
            )

        elif op_type == OperationType.ENLARGE_HERO:
            # Apply relative adjustment if present
            scale_factor = 1.3
            if "adjustment_strength" in params:
                # Scale the adjustment: 0.3 strength -> 1.09x, 0.8 strength -> 1.24x
                strength = params["adjustment_strength"]
                scale_factor = 1.0 + (0.3 * strength)
            return EnlargeHeroOperation(scale_factor)

        elif op_type == OperationType.REDUCE_TEXT:
            element_id = params.get("element_id")
            if element_id:
                element_id = self._resolve_element_name(element_id, slide_snapshot)
            reduce_lines = params.get("reduce_lines")
            return ReduceTextOperation(element_id, reduce_lines)

        elif op_type == OperationType.INCREASE_WHITESPACE:
            return IncreaseWhitespaceOperation()

        elif op_type == OperationType.LOCK:
            element_id = params.get("element_id")
            if not element_id:
                raise WorkflowError("lock operation requires element_id")
            element_id = self._resolve_element_name(element_id, slide_snapshot)
            if not element_id:
                raise WorkflowError(f"Cannot resolve element: {params.get('element_id')}")
            return LockOperation(element_id)

        elif op_type == OperationType.UNLOCK:
            element_id = params.get("element_id")
            if not element_id:
                raise WorkflowError("unlock operation requires element_id")
            element_id = self._resolve_element_name(element_id, slide_snapshot)
            if not element_id:
                raise WorkflowError(f"Cannot resolve element: {params.get('element_id')}")
            return UnlockOperation(element_id)

        else:
            # Generic operation - wrap params directly
            return AtomicOperation(
                operation_type=op_type,
                target_element_id=params.get("element_id"),
                params=params,
            )

    def _extract_multi_step_operations(
        self,
        params: dict,
        slide_snapshot: SlideSnapshot,
    ) -> list[AtomicOperation]:
        """Extract additional operations from multi_step_operations parameter."""
        multi_step_ops: list[AtomicOperation] = []

        if "multi_step_operations" not in params:
            return multi_step_ops

        for step in params["multi_step_operations"]:
            if not isinstance(step, dict):
                continue

            operation_name = step.get("operation")
            targets = step.get("targets", [])

            if operation_name == "move_to" and len(targets) >= 2:
                # Move element to position
                element_name = targets[0]
                position = targets[1] if len(targets) > 1 else "right"
                element_id = self._resolve_element_name(element_name, slide_snapshot)
                if element_id:
                    multi_step_ops.append(
                        MoveOperation(element_id, position, preserve_size=True)
                    )

            elif operation_name == "swap" and len(targets) >= 2:
                layout_plan = slide_snapshot.layout_plan
                if layout_plan is None:
                    raise WorkflowError("swap requires an existing layout plan")
                elem1_id = self._resolve_element_name(targets[0], slide_snapshot)
                elem2_id = self._resolve_element_name(targets[1], slide_snapshot)
                if elem1_id is None or elem2_id is None:
                    raise WorkflowError("无法解析 swap 目标元素")
                first = layout_plan.element_by_id(elem1_id)
                second = layout_plan.element_by_id(elem2_id)
                if first is None or second is None:
                    raise WorkflowError("无法解析 swap 目标元素")
                multi_step_ops.append(SwapOperation(elem1_id, elem2_id))

        # Also check for inline "reduce_lines" operations
        if "reduce_lines" in params and params["reduce_lines"]:
            # This is an additional reduction operation
            element_id = params.get("reduce_text_element")
            if element_id:
                element_id = self._resolve_element_name(element_id, slide_snapshot)
            multi_step_ops.append(
                ReduceTextOperation(element_id, params["reduce_lines"])
            )

        return multi_step_ops

    def _resolve_element_name(
        self,
        name: str | UUID | None,
        slide_snapshot: SlideSnapshot,
    ) -> str | None:
        """
        Resolve element name to a layout element id string.

        Args:
            name: Element name (Chinese or English), UUID, or element id
            slide_snapshot: Current slide state

        Returns:
            Element id if found, None otherwise
        """
        if name is None:
            return None

        if isinstance(name, UUID):
            return str(name)

        normalized = name.strip().lower()

        name_mappings = {
            "图纸": "drawing",
            "主图": "hero",
            "说明": "caption",
            "标题": "title",
            "正文": "body",
            "文字": "text",
            "证据": "evidence",
            "数据": "data",
            "图表": "chart",
        }

        role = name_mappings.get(normalized, normalized)

        layout_plan = slide_snapshot.layout_plan
        if not layout_plan:
            return None

        for element in layout_plan.elements:
            if element.id.lower() == normalized:
                return element.id

        if role in {"drawing", "hero", "hero_visual", "main_visual"}:
            for candidate_role in (
                LayoutElementRole.HERO_VISUAL,
                LayoutElementRole.SUPPORTING_VISUAL,
            ):
                for element in layout_plan.elements:
                    if element.role == candidate_role:
                        return element.id

        for element in layout_plan.elements:
            if element.role and element.role.value.lower() == role:
                return element.id
            if role == "text" and element.content_type == LayoutContentType.TEXT:
                return element.id

        return None

"""Parse and validate deliverable planning drafts."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import DeliverableType
from archium.domain.workstream import Workstream
from archium.infrastructure.llm.deliverable_schemas import DeliverablePlanDraft


@dataclass
class DeliverableParseResult:
    plan: DeliverablePlan
    warnings: list[str] = field(default_factory=list)


def parse_deliverable_plan_draft(
    draft: DeliverablePlanDraft,
    *,
    project_id: UUID,
    mission_id: UUID,
    workstreams: list[Workstream],
    previous: DeliverablePlan | None = None,
) -> DeliverableParseResult:
    warnings: list[str] = []
    deliverables: list[PlannedDeliverable] = []
    seen_ids: set[str] = set()

    for item in draft.deliverables:
        deliverable_id = item.id.strip() or f"del-{uuid4().hex[:8]}"
        if deliverable_id in seen_ids:
            deliverable_id = f"{deliverable_id}-{uuid4().hex[:4]}"
            warnings.append(f"成果 id 重复，已重命名为 {deliverable_id}")
        seen_ids.add(deliverable_id)

        source_ids: list[UUID] = []
        for index in item.source_workstream_indices:
            if 0 <= index < len(workstreams):
                source_ids.append(workstreams[index].id)
            else:
                warnings.append(
                    f"成果「{item.title}」工作路径下标 {index} 无效，已忽略"
                )

        recommendation = (item.recommendation or "optional").strip().lower()
        required = recommendation == "required"
        selected = recommendation in {"required", "optional"}
        notes = item.notes or ""
        if item.decision_served:
            decision_note = f"服务决策：{item.decision_served}"
            notes = f"{notes}\n{decision_note}".strip() if notes else decision_note
        if recommendation == "not_recommended":
            selected = False
            required = False
            if "不建议" not in notes:
                notes = (notes + "\n【不建议本轮产出】").strip()

        deliverables.append(
            PlannedDeliverable(
                id=deliverable_id,
                title=item.title,
                deliverable_type=_parse_enum(
                    item.deliverable_type, DeliverableType, DeliverableType.OTHER
                ),
                purpose=item.purpose,
                audience=item.audience,
                content_scope=list(item.content_scope),
                source_workstream_ids=source_ids,
                required=required,
                selected=selected,
                format=item.format or "markdown",
                expected_length=item.expected_length,
                notes=notes or None,
            )
        )

    plan = DeliverablePlan(
        project_id=project_id,
        mission_id=mission_id,
        deliverables=deliverables,
        version=(previous.version + 1) if previous is not None else 1,
    )
    if previous is not None:
        plan.lineage_id = previous.lineage_id
        plan.logical_key = previous.logical_key

    return DeliverableParseResult(plan=plan, warnings=warnings)


def validate_deliverable_plan_draft(draft: DeliverablePlanDraft) -> list[str]:
    errors: list[str] = []
    if not draft.deliverables:
        errors.append("成果规划不能为空")
    for item in draft.deliverables:
        if not item.title.strip():
            errors.append("成果标题不能为空")
        if not item.purpose.strip():
            errors.append(f"成果「{item.title}」缺少用途说明")
        recommendation = (item.recommendation or "").strip().lower()
        if recommendation not in {"required", "optional", "not_recommended", ""}:
            errors.append(f"成果「{item.title}」recommendation 无效：{item.recommendation}")
    return errors


def _parse_enum(value: str, enum_cls, fallback):
    try:
        return enum_cls(value)
    except ValueError:
        return fallback

"""Non-presentation artifact executors (Question List, Work Plan, …).

Router selects the executor; executors read the full mission bundle and write
Markdown + JSON artifacts. DOCX is reserved for a later sprint.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import (
    AssumptionStatus,
    KnowledgeGapStatus,
    QuestionStatus,
    VerificationStatus,
)
from archium.domain.fact import ProjectFact
from archium.domain.knowledge_gap import Assumption, ClarifyingQuestion, KnowledgeGap
from archium.domain.project_mission import ProjectMission
from archium.domain.workstream import Workstream


@dataclass
class ArtifactOutput:
    """Generated artifact payload (in-memory + optional on-disk paths)."""

    kind: str
    title: str
    payload: dict[str, Any]
    markdown: str
    json_path: Path | None = None
    markdown_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "payload": self.payload,
            "markdown": self.markdown,
            "json_path": str(self.json_path) if self.json_path else None,
            "markdown_path": str(self.markdown_path) if self.markdown_path else None,
        }


def artifact_output_dir(
    output_root: Path,
    *,
    mission_id: UUID,
    kind: str,
) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = output_root / "artifacts" / str(mission_id) / f"{kind}_{stamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_artifact_files(
    output: ArtifactOutput,
    directory: Path,
    *,
    basename: str,
) -> ArtifactOutput:
    json_path = directory / f"{basename}.json"
    md_path = directory / f"{basename}.md"
    json_path.write_text(
        json.dumps(output.payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(output.markdown, encoding="utf-8")
    output.json_path = json_path
    output.markdown_path = md_path
    return output


@dataclass(frozen=True)
class QuestionListItem:
    source: str
    text: str
    blocking: bool = False
    priority: str = "medium"
    status: str = "open"
    source_id: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class QuestionListExecutor:
    """Build a question list from mission bundle context (not deliverable.content_scope).

    Future: DOCX export via the same payload.
    """

    def execute(
        self,
        mission: ProjectMission,
        *,
        gaps: list[KnowledgeGap] | None = None,
        questions: list[ClarifyingQuestion] | None = None,
        assumptions: list[Assumption] | None = None,
        facts: list[ProjectFact] | None = None,
        deliverable: PlannedDeliverable | None = None,
        output_dir: Path | None = None,
    ) -> ArtifactOutput:
        items = self._collect_items(
            mission,
            gaps=gaps or [],
            questions=questions or [],
            assumptions=assumptions or [],
            facts=facts or [],
        )
        title = (
            deliverable.title
            if deliverable is not None
            else f"{mission.title} — 提问清单"
        )
        payload = {
            "kind": "question_list",
            "mission_id": str(mission.id),
            "title": title,
            "generated_at": datetime.now(UTC).isoformat(),
            "item_count": len(items),
            "items": [item.to_dict() for item in items],
            # Reserved for later DOCX export.
            "formats": ["json", "markdown", "docx_pending"],
        }
        markdown = self._to_markdown(title, mission, items)
        output = ArtifactOutput(
            kind="question_list",
            title=title,
            payload=payload,
            markdown=markdown,
        )
        if output_dir is not None:
            write_artifact_files(output, output_dir, basename="question_list")
        return output

    def _collect_items(
        self,
        mission: ProjectMission,
        *,
        gaps: list[KnowledgeGap],
        questions: list[ClarifyingQuestion],
        assumptions: list[Assumption],
        facts: list[ProjectFact],
    ) -> list[QuestionListItem]:
        items: list[QuestionListItem] = []
        seen: set[str] = set()

        def _add(item: QuestionListItem) -> None:
            key = f"{item.source}:{item.text.strip()}"
            if not item.text.strip() or key in seen:
                return
            seen.add(key)
            items.append(item)

        for gap in gaps:
            if gap.status != KnowledgeGapStatus.OPEN:
                continue
            _add(
                QuestionListItem(
                    source="knowledge_gap",
                    text=gap.question,
                    blocking=gap.blocking,
                    priority=gap.priority.value,
                    status=gap.status.value,
                    source_id=str(gap.id),
                    notes=gap.why_it_matters or "",
                )
            )

        for question in questions:
            if question.status != QuestionStatus.OPEN:
                continue
            _add(
                QuestionListItem(
                    source="clarifying_question",
                    text=question.question,
                    blocking=question.blocking,
                    priority=question.priority.value,
                    status=question.status.value,
                    source_id=str(question.id),
                    notes=question.why_asked or "",
                )
            )

        for assumption in assumptions:
            if not assumption.requires_confirmation:
                continue
            if assumption.status in {
                AssumptionStatus.CONFIRMED,
                AssumptionStatus.ACCEPTED,
                AssumptionStatus.REJECTED,
            }:
                continue
            _add(
                QuestionListItem(
                    source="assumption",
                    text=f"请确认假设：{assumption.statement}",
                    blocking=False,
                    priority="medium",
                    status=assumption.status.value,
                    source_id=str(assumption.id),
                    notes=assumption.reason or "",
                )
            )

        for fact in facts:
            if fact.verification_status != VerificationStatus.CONFLICTED:
                continue
            label = fact.label or fact.key
            _add(
                QuestionListItem(
                    source="fact_conflict",
                    text=f"请裁决事实冲突：{label} = {fact.value}",
                    blocking=True,
                    priority="high",
                    status=fact.verification_status.value,
                    source_id=str(fact.id),
                    notes=fact.conflict_group or "",
                )
            )

        for decision in mission.decisions_required:
            text = decision.strip()
            if not text:
                continue
            if not text.endswith(("?", "？")):
                text = f"待决策：{text}"
            _add(
                QuestionListItem(
                    source="required_decision",
                    text=text,
                    blocking=True,
                    priority="high",
                    status="open",
                )
            )

        # Blocking items first, then by source stability.
        source_order = {
            "fact_conflict": 0,
            "knowledge_gap": 1,
            "clarifying_question": 2,
            "required_decision": 3,
            "assumption": 4,
        }
        items.sort(
            key=lambda item: (
                0 if item.blocking else 1,
                source_order.get(item.source, 9),
                item.text,
            )
        )
        return items

    def _to_markdown(
        self,
        title: str,
        mission: ProjectMission,
        items: list[QuestionListItem],
    ) -> str:
        lines = [
            f"# {title}",
            "",
            f"任务：{mission.task_statement}",
            "",
            f"共 {len(items)} 项。",
            "",
        ]
        blocking = [item for item in items if item.blocking]
        other = [item for item in items if not item.blocking]
        if blocking:
            lines.append("## 阻塞项")
            lines.append("")
            for idx, item in enumerate(blocking, start=1):
                lines.append(f"{idx}. **[{item.source}]** {item.text}")
                if item.notes:
                    lines.append(f"   - 说明：{item.notes}")
            lines.append("")
        if other:
            lines.append("## 其他待澄清")
            lines.append("")
            for idx, item in enumerate(other, start=1):
                lines.append(f"{idx}. **[{item.source}]** {item.text}")
                if item.notes:
                    lines.append(f"   - 说明：{item.notes}")
            lines.append("")
        if not items:
            lines.append("_当前无待澄清项。_")
            lines.append("")
        return "\n".join(lines)


@dataclass
class WorkPlanSection:
    workstream_id: str
    title: str
    workstream_type: str
    objective: str
    inputs: list[str] = field(default_factory=list)
    activities: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    priority: str = "medium"
    selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkPlanExecutor:
    """Generate a structured project work outline from Mission + Workstreams + DeliverablePlan."""

    def execute(
        self,
        mission: ProjectMission,
        *,
        workstreams: list[Workstream],
        deliverable_plan: DeliverablePlan | None = None,
        deliverable: PlannedDeliverable | None = None,
        output_dir: Path | None = None,
        selected_only: bool = True,
    ) -> ArtifactOutput:
        selected_ws = [
            ws
            for ws in workstreams
            if (ws.selected if selected_only else True)
        ]
        if not selected_ws and workstreams:
            # Fall back to recommended / all when nothing explicitly selected.
            selected_ws = [ws for ws in workstreams if ws.recommended] or list(workstreams)

        id_to_title = {str(ws.id): ws.title for ws in workstreams}
        sections = [
            WorkPlanSection(
                workstream_id=str(ws.id),
                title=ws.title,
                workstream_type=ws.workstream_type.value,
                objective=ws.objective,
                inputs=list(ws.inputs_required),
                activities=list(ws.activities),
                outputs=list(ws.outputs),
                dependencies=[
                    id_to_title.get(str(dep), str(dep)) for dep in ws.dependencies
                ],
                priority=ws.priority.value,
                selected=ws.selected,
            )
            for ws in selected_ws
        ]

        deliverables = []
        if deliverable_plan is not None:
            for item in deliverable_plan.selected_deliverables():
                deliverables.append(
                    {
                        "id": item.id,
                        "title": item.title,
                        "type": item.deliverable_type.value,
                        "purpose": item.purpose,
                        "content_scope": list(item.content_scope),
                    }
                )

        title = (
            deliverable.title
            if deliverable is not None
            else f"{mission.title} — 工作大纲"
        )
        payload = {
            "kind": "work_plan",
            "mission_id": str(mission.id),
            "title": title,
            "generated_at": datetime.now(UTC).isoformat(),
            "mission": {
                "title": mission.title,
                "task_statement": mission.task_statement,
                "in_scope": list(mission.in_scope),
                "out_of_scope": list(mission.out_of_scope),
                "decisions_required": list(mission.decisions_required),
            },
            "workstreams": [section.to_dict() for section in sections],
            "deliverables": deliverables,
            "formats": ["json", "markdown"],
        }
        markdown = self._to_markdown(title, mission, sections, deliverables)
        output = ArtifactOutput(
            kind="work_plan",
            title=title,
            payload=payload,
            markdown=markdown,
        )
        if output_dir is not None:
            write_artifact_files(output, output_dir, basename="work_plan")
        return output

    def _to_markdown(
        self,
        title: str,
        mission: ProjectMission,
        sections: list[WorkPlanSection],
        deliverables: list[dict[str, Any]],
    ) -> str:
        lines = [
            f"# {title}",
            "",
            f"**任务陈述**：{mission.task_statement}",
            "",
        ]
        if mission.in_scope:
            lines.append("**范围内**：" + "、".join(mission.in_scope))
            lines.append("")
        if mission.out_of_scope:
            lines.append("**范围外**：" + "、".join(mission.out_of_scope))
            lines.append("")

        lines.append("## 工作路径")
        lines.append("")
        if not sections:
            lines.append("_暂无工作路径。_")
            lines.append("")
        for idx, section in enumerate(sections, start=1):
            lines.append(f"### {idx}. {section.title}")
            lines.append("")
            lines.append(f"- 类型：`{section.workstream_type}`")
            lines.append(f"- 优先级：{section.priority}")
            lines.append(f"- 目标：{section.objective}")
            if section.dependencies:
                lines.append("- 依赖：" + "、".join(section.dependencies))
            if section.inputs:
                lines.append("- 输入：" + "、".join(section.inputs))
            if section.activities:
                lines.append("- 活动：")
                for activity in section.activities:
                    lines.append(f"  - {activity}")
            if section.outputs:
                lines.append("- 产出：" + "、".join(section.outputs))
            lines.append("")

        if deliverables:
            lines.append("## 计划成果")
            lines.append("")
            for item in deliverables:
                lines.append(
                    f"- **{item['title']}**（{item['type']}）：{item.get('purpose') or ''}"
                )
            lines.append("")

        if mission.decisions_required:
            lines.append("## 待决策")
            lines.append("")
            for decision in mission.decisions_required:
                lines.append(f"- {decision}")
            lines.append("")

        return "\n".join(lines)

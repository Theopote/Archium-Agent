"""Non-presentation artifact executors (Question List, Work Plan, Report, …).

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


def _mission_context_payload(mission: ProjectMission) -> dict[str, Any]:
    return {
        "title": mission.title,
        "task_statement": mission.task_statement,
        "project_context": mission.project_context,
        "current_situation": mission.current_situation,
        "primary_problems": list(mission.primary_problems),
        "desired_changes": list(mission.desired_changes),
        "in_scope": list(mission.in_scope),
        "out_of_scope": list(mission.out_of_scope),
        "decisions_required": list(mission.decisions_required),
        "key_unknowns": list(mission.key_unknowns),
        "research_questions": list(mission.research_questions),
        "decision_context": mission.decision_context,
        "stakeholders": [
            {
                "name": item.name,
                "role": item.role,
                "concerns": list(item.concerns),
            }
            for item in mission.stakeholders
        ],
    }


def _append_mission_context_markdown(lines: list[str], mission: ProjectMission) -> None:
    lines.append(f"**任务陈述**：{mission.task_statement}")
    lines.append("")
    if mission.project_context.strip():
        lines.append(f"**项目背景**：{mission.project_context.strip()}")
        lines.append("")
    if mission.current_situation.strip():
        lines.append(f"**现状**：{mission.current_situation.strip()}")
        lines.append("")
    if mission.primary_problems:
        lines.append("**主要问题**：")
        for item in mission.primary_problems:
            lines.append(f"- {item}")
        lines.append("")
    if mission.desired_changes:
        lines.append("**期望变化**：")
        for item in mission.desired_changes:
            lines.append(f"- {item}")
        lines.append("")
    if mission.in_scope:
        lines.append("**范围内**：" + "、".join(mission.in_scope))
        lines.append("")
    if mission.out_of_scope:
        lines.append("**范围外**：" + "、".join(mission.out_of_scope))
        lines.append("")
    if mission.stakeholders:
        lines.append("## 利益相关方")
        lines.append("")
        for stakeholder in mission.stakeholders:
            concerns = "；".join(stakeholder.concerns) if stakeholder.concerns else "—"
            lines.append(f"- **{stakeholder.name}**（{stakeholder.role}）：{concerns}")
        lines.append("")
    if mission.decisions_required:
        lines.append("## 待决策")
        lines.append("")
        for decision in mission.decisions_required:
            lines.append(f"- {decision}")
        lines.append("")
    if mission.key_unknowns:
        lines.append("## 关键未知")
        lines.append("")
        for unknown in mission.key_unknowns:
            lines.append(f"- {unknown}")
        lines.append("")
    if mission.research_questions:
        lines.append("## 研究问题")
        lines.append("")
        for question in mission.research_questions:
            lines.append(f"- {question}")
        lines.append("")


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


class ReportExecutor:
    """Generate a structured report outline from Mission + deliverable scope."""

    def execute(
        self,
        mission: ProjectMission,
        *,
        deliverable: PlannedDeliverable | None = None,
        content_scope: list[str] | None = None,
        purpose: str = "",
        audience: str = "",
        expected_length: str = "",
        notes: str = "",
        output_dir: Path | None = None,
    ) -> ArtifactOutput:
        scope = list(content_scope or [])
        if deliverable is not None and not scope:
            scope = list(deliverable.content_scope)
        title = deliverable.title if deliverable is not None else f"{mission.title} — 报告"
        purpose = purpose or (deliverable.purpose if deliverable else "") or ""
        audience = audience or (deliverable.audience if deliverable else "") or ""
        expected_length = expected_length or (
            (deliverable.expected_length or "") if deliverable else ""
        )
        notes = notes or ((deliverable.notes or "") if deliverable else "")

        sections = scope or [
            "任务理解与背景",
            "关键问题与约束",
            "分析要点",
            "建议与下一步",
        ]
        payload = {
            "kind": "report",
            "mission_id": str(mission.id),
            "title": title,
            "generated_at": datetime.now(UTC).isoformat(),
            "purpose": purpose,
            "audience": audience,
            "expected_length": expected_length,
            "notes": notes,
            "sections": sections,
            "mission": _mission_context_payload(mission),
            "formats": ["json", "markdown"],
        }
        lines = [f"# {title}", ""]
        if purpose:
            lines.append(f"**目的**：{purpose}")
            lines.append("")
        if audience:
            lines.append(f"**受众**：{audience}")
            lines.append("")
        if expected_length:
            lines.append(f"**预期篇幅**：{expected_length}")
            lines.append("")
        _append_mission_context_markdown(lines, mission)
        lines.append("## 报告结构")
        lines.append("")
        for idx, section in enumerate(sections, start=1):
            lines.append(f"### {idx}. {section}")
            lines.append("")
            lines.append("_待基于 Mission 与后续研究填充。_")
            lines.append("")
        if notes:
            lines.append("## 备注")
            lines.append("")
            lines.append(notes)
            lines.append("")
        output = ArtifactOutput(
            kind="report",
            title=title,
            payload=payload,
            markdown="\n".join(lines),
        )
        if output_dir is not None:
            write_artifact_files(output, output_dir, basename="report")
        return output


class MemoExecutor:
    """Generate a short planning memo from Mission context."""

    def execute(
        self,
        mission: ProjectMission,
        *,
        deliverable: PlannedDeliverable | None = None,
        content_scope: list[str] | None = None,
        purpose: str = "",
        audience: str = "",
        notes: str = "",
        output_dir: Path | None = None,
    ) -> ArtifactOutput:
        scope = list(content_scope or [])
        if deliverable is not None and not scope:
            scope = list(deliverable.content_scope)
        title = deliverable.title if deliverable is not None else f"{mission.title} — 备忘录"
        purpose = purpose or (deliverable.purpose if deliverable else "") or ""
        audience = audience or (deliverable.audience if deliverable else "") or ""
        notes = notes or ((deliverable.notes or "") if deliverable else "")

        bullets = scope or list(mission.primary_problems[:5]) or list(mission.decisions_required[:5])
        payload = {
            "kind": "memo",
            "mission_id": str(mission.id),
            "title": title,
            "generated_at": datetime.now(UTC).isoformat(),
            "purpose": purpose,
            "audience": audience,
            "notes": notes,
            "highlights": bullets,
            "mission": _mission_context_payload(mission),
            "formats": ["json", "markdown"],
        }
        lines = [f"# {title}", ""]
        if purpose:
            lines.append(f"**目的**：{purpose}")
            lines.append("")
        if audience:
            lines.append(f"**受众**：{audience}")
            lines.append("")
        lines.append(f"**一句话任务**：{mission.task_statement}")
        lines.append("")
        if bullets:
            lines.append("## 要点")
            lines.append("")
            for item in bullets:
                lines.append(f"- {item}")
            lines.append("")
        if mission.decisions_required:
            lines.append("## 需决策")
            lines.append("")
            for item in mission.decisions_required:
                lines.append(f"- {item}")
            lines.append("")
        if mission.key_unknowns:
            lines.append("## 待澄清")
            lines.append("")
            for item in mission.key_unknowns:
                lines.append(f"- {item}")
            lines.append("")
        if notes:
            lines.append("## 备注")
            lines.append("")
            lines.append(notes)
            lines.append("")
        output = ArtifactOutput(
            kind="memo",
            title=title,
            payload=payload,
            markdown="\n".join(lines),
        )
        if output_dir is not None:
            write_artifact_files(output, output_dir, basename="memo")
        return output


class ChecklistExecutor:
    """Generate a checklist from deliverable content_scope and mission decisions."""

    def execute(
        self,
        mission: ProjectMission,
        *,
        deliverable: PlannedDeliverable | None = None,
        items: list[str] | None = None,
        purpose: str = "",
        audience: str = "",
        notes: str = "",
        output_dir: Path | None = None,
    ) -> ArtifactOutput:
        checklist_items = list(items or [])
        if deliverable is not None and not checklist_items:
            checklist_items = list(deliverable.content_scope)
        if not checklist_items:
            checklist_items = list(mission.decisions_required) or list(mission.key_unknowns)
        title = deliverable.title if deliverable is not None else f"{mission.title} — 清单"
        purpose = purpose or (deliverable.purpose if deliverable else "") or ""
        audience = audience or (deliverable.audience if deliverable else "") or ""
        notes = notes or ((deliverable.notes or "") if deliverable else "")

        payload = {
            "kind": "checklist",
            "mission_id": str(mission.id),
            "title": title,
            "generated_at": datetime.now(UTC).isoformat(),
            "purpose": purpose,
            "audience": audience,
            "notes": notes,
            "item_count": len(checklist_items),
            "items": [{"text": text, "checked": False} for text in checklist_items],
            "mission": {
                "title": mission.title,
                "task_statement": mission.task_statement,
            },
            "formats": ["json", "markdown"],
        }
        lines = [f"# {title}", ""]
        if purpose:
            lines.append(f"**目的**：{purpose}")
            lines.append("")
        if audience:
            lines.append(f"**受众**：{audience}")
            lines.append("")
        lines.append(f"任务：{mission.task_statement}")
        lines.append("")
        lines.append(f"共 {len(checklist_items)} 项。")
        lines.append("")
        if checklist_items:
            for item in checklist_items:
                lines.append(f"- [ ] {item}")
            lines.append("")
        else:
            lines.append("_当前无清单项。_")
            lines.append("")
        if notes:
            lines.append("## 备注")
            lines.append("")
            lines.append(notes)
            lines.append("")
        output = ArtifactOutput(
            kind="checklist",
            title=title,
            payload=payload,
            markdown="\n".join(lines),
        )
        if output_dir is not None:
            write_artifact_files(output, output_dir, basename="checklist")
        return output


class CaseStudyExecutor:
    """Generate a case-study brief skeleton from Mission + research questions."""

    def execute(
        self,
        mission: ProjectMission,
        *,
        deliverable: PlannedDeliverable | None = None,
        content_scope: list[str] | None = None,
        purpose: str = "",
        audience: str = "",
        expected_length: str = "",
        notes: str = "",
        output_dir: Path | None = None,
    ) -> ArtifactOutput:
        scope = list(content_scope or [])
        if deliverable is not None and not scope:
            scope = list(deliverable.content_scope)
        title = (
            deliverable.title if deliverable is not None else f"{mission.title} — 案例研究"
        )
        purpose = purpose or (deliverable.purpose if deliverable else "") or ""
        audience = audience or (deliverable.audience if deliverable else "") or ""
        expected_length = expected_length or (
            (deliverable.expected_length or "") if deliverable else ""
        )
        notes = notes or ((deliverable.notes or "") if deliverable else "")

        lenses = scope or [
            "项目背景与问题",
            "策略与空间组织",
            "可借鉴要点",
            "对本任务的启示",
        ]
        research = list(mission.research_questions)
        if mission.design_intent is not None:
            research = list(dict.fromkeys([*research, *mission.design_intent.research_needed]))

        payload = {
            "kind": "case_study",
            "mission_id": str(mission.id),
            "title": title,
            "generated_at": datetime.now(UTC).isoformat(),
            "purpose": purpose,
            "audience": audience,
            "expected_length": expected_length,
            "notes": notes,
            "lenses": lenses,
            "research_questions": research,
            "mission": _mission_context_payload(mission),
            "formats": ["json", "markdown"],
        }
        lines = [f"# {title}", ""]
        if purpose:
            lines.append(f"**目的**：{purpose}")
            lines.append("")
        if audience:
            lines.append(f"**受众**：{audience}")
            lines.append("")
        lines.append(f"**对照任务**：{mission.task_statement}")
        lines.append("")
        if research:
            lines.append("## 研究问题")
            lines.append("")
            for item in research:
                lines.append(f"- {item}")
            lines.append("")
        lines.append("## 分析框架")
        lines.append("")
        for idx, lens in enumerate(lenses, start=1):
            lines.append(f"### {idx}. {lens}")
            lines.append("")
            lines.append("_待填入案例事实与可借鉴结论；不得编造未检索到的项目指标。_")
            lines.append("")
        if notes:
            lines.append("## 备注")
            lines.append("")
            lines.append(notes)
            lines.append("")
        output = ArtifactOutput(
            kind="case_study",
            title=title,
            payload=payload,
            markdown="\n".join(lines),
        )
        if output_dir is not None:
            write_artifact_files(output, output_dir, basename="case_study")
        return output

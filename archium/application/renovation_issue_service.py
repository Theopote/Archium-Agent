"""Renovation scenario detection, validation, and prompt formatting."""

from __future__ import annotations

import json
from uuid import UUID

from archium.application.outline_templates import detect_scenario_template
from archium.application.presentation_models import PresentationRequest
from archium.domain.enums import InformationOrigin, ProjectType
from archium.domain.presentation import PresentationBrief
from archium.domain.project import Project
from archium.domain.renovation_issue import (
    RenovationEvidence,
    RenovationIssue,
    RenovationIssueMap,
    RenovationStrategy,
)
from archium.infrastructure.llm.presentation_schemas import RenovationIssueMapDraft


def is_renovation_scenario(
    *,
    brief: PresentationBrief | None = None,
    request: PresentationRequest | None = None,
    project: Project | None = None,
) -> bool:
    """Return True when the task matches renovation / retrofit reporting."""
    if project is not None and project.project_type == ProjectType.URBAN_RENEWAL:
        if brief is not None or request is not None:
            pass
        else:
            return False

    required = list(brief.required_sections) if brief is not None else []
    purpose = (brief.purpose if brief else "") or (request.purpose if request else "")
    audience = (brief.audience if brief else "") or (request.audience if request else "")
    if request is not None:
        required = required or list(request.required_sections)
    return detect_scenario_template(
        required_sections=required,
        purpose=purpose,
        audience=audience,
    ) == "renovation"


def issue_map_fallback_from_brief(
    brief: PresentationBrief,
    *,
    project_id: UUID,
    version: int = 1,
) -> RenovationIssueMap:
    """Minimal issue map scaffold when LLM is unavailable."""
    evidence_id = "ev1"
    issue_id = "issue1"
    return RenovationIssueMap(
        project_id=project_id,
        building_summary=brief.core_message or brief.purpose,
        condition_overview="需结合现场调研与图纸补充建筑现状",
        evidence_items=[
            RenovationEvidence(
                id=evidence_id,
                description="资料中尚未形成完整现状证据，需补充调研",
                evidence_type="observation",
                origin=InformationOrigin.SYSTEM_INFERENCE,
            )
        ],
        issues=[
            RenovationIssue(
                id=issue_id,
                category="space",
                problem_statement="空间使用与流线问题待现场核实",
                severity="medium",
                linked_evidence_ids=[evidence_id],
                origin=InformationOrigin.SYSTEM_INFERENCE,
            )
        ],
        strategies=[
            RenovationStrategy(
                id="str1",
                title="总体改造策略待深化",
                approach="在补充现状证据后形成分区改造策略",
                linked_issue_ids=[issue_id],
                origin=InformationOrigin.SYSTEM_INFERENCE,
            )
        ],
        unsupported_claims=["需补充交通、立面、消防与结构专项资料"],
        version=version,
    )


def issue_map_from_draft(
    draft: RenovationIssueMapDraft,
    *,
    project_id: UUID,
    version: int = 1,
) -> RenovationIssueMap:
    return RenovationIssueMap(
        project_id=project_id,
        building_summary=draft.building_summary,
        condition_overview=draft.condition_overview,
        evidence_items=[
            RenovationEvidence(
                id=item.id,
                description=item.description,
                evidence_type=item.evidence_type,
                location=item.location,
                origin=InformationOrigin(item.origin),
                asset_refs=list(item.asset_refs),
            )
            for item in draft.evidence_items
        ],
        issues=[
            RenovationIssue(
                id=item.id,
                category=item.category,
                problem_statement=item.problem_statement,
                severity=item.severity,
                impact=item.impact,
                linked_evidence_ids=list(item.linked_evidence_ids),
                origin=InformationOrigin(item.origin),
            )
            for item in draft.issues
        ],
        strategies=[
            RenovationStrategy(
                id=item.id,
                title=item.title,
                approach=item.approach,
                category=item.category,
                linked_issue_ids=list(item.linked_issue_ids),
                phasing=item.phasing,
                scope_note=item.scope_note,
                origin=InformationOrigin(item.origin),
            )
            for item in draft.strategies
        ],
        unsupported_claims=list(draft.unsupported_claims),
        version=version,
    )


def validate_issue_map(plan: RenovationIssueMap) -> list[str]:
    """Return validation issues for renovation issue map quality."""
    issues: list[str] = []
    if not plan.building_summary.strip():
        issues.append("缺少 building_summary")

    evidence_ids = {item.id for item in plan.evidence_items}
    issue_ids = {item.id for item in plan.issues}

    for issue in plan.issues:
        if not issue.linked_evidence_ids:
            issues.append(f"问题未关联证据：{issue.problem_statement[:40]}")
        elif not set(issue.linked_evidence_ids).issubset(evidence_ids):
            issues.append(f"问题引用了不存在的证据：{issue.id}")
        elif issue.origin != InformationOrigin.SYSTEM_INFERENCE and not issue.source_citations:
            issues.append(f"问题描述缺少来源：{issue.problem_statement[:40]}")

    for strategy in plan.strategies:
        if not strategy.linked_issue_ids:
            issues.append(f"策略未关联问题：{strategy.title[:40]}")
        elif not set(strategy.linked_issue_ids).issubset(issue_ids):
            issues.append(f"策略引用了不存在的问题：{strategy.id}")

    return issues


def format_issue_map_for_prompt(plan: RenovationIssueMap) -> str:
    """Compact issue map summary for downstream Storyline / Outline agents."""
    payload = {
        "building_summary": plan.building_summary,
        "condition_overview": plan.condition_overview,
        "unsupported_claims": plan.unsupported_claims,
        "evidence_items": [
            {
                "id": item.id,
                "description": item.description,
                "type": item.evidence_type,
                "location": item.location,
            }
            for item in plan.evidence_items
        ],
        "issues": [
            {
                "id": issue.id,
                "category": issue.category,
                "problem": issue.problem_statement,
                "severity": issue.severity,
                "evidence": issue.linked_evidence_ids,
            }
            for issue in plan.issues
        ],
        "strategies": [
            {
                "id": strategy.id,
                "title": strategy.title,
                "approach": strategy.approach,
                "issues": strategy.linked_issue_ids,
                "phasing": strategy.phasing,
            }
            for strategy in plan.strategies
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

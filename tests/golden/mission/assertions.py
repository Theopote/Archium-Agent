"""Assertions for mission golden scenarios."""

from __future__ import annotations

from typing import Any

from archium.application.deliverable_execution import ArtifactExecutionPlan
from archium.application.mission_to_presentation_request import MissionPresentationBridge
from archium.application.project_mission_service import MissionGenerationResult
from archium.domain.deliverable import DeliverablePlan
from archium.domain.enums import DeliverableType, KnowledgeGapCategory
from archium.domain.workstream import Workstream


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def assert_mission_expectations(
    *,
    expectations: dict[str, Any],
    generation: MissionGenerationResult,
    workstreams: list[Workstream],
    plan: DeliverablePlan,
    bridge: MissionPresentationBridge | None = None,
    execution_plans: list[ArtifactExecutionPlan] | None = None,
) -> None:
    mission = generation.mission
    natures = {item.value for item in mission.task_natures}
    scales = {item.value for item in mission.intervention_scales}
    gap_categories = {gap.category.value for gap in generation.knowledge_gaps}
    gap_text = " ".join(gap.question for gap in generation.knowledge_gaps)
    question_text = " ".join(q.question for q in generation.clarifying_questions)
    out_scope = " ".join(mission.out_of_scope)
    ws_titles = " ".join(ws.title for ws in workstreams)
    ws_types = {ws.workstream_type.value for ws in workstreams}
    deliverable_types = {item.deliverable_type.value for item in plan.deliverables}
    selected_types = {
        item.deliverable_type.value for item in plan.deliverables if item.selected
    }

    for nature in expectations.get("task_natures_any") or []:
        assert nature in natures, f"expected task nature {nature} in {natures}"
    for nature in expectations.get("task_natures_none") or []:
        assert nature not in natures, f"unexpected task nature {nature}"

    if expectations.get("clarifying_questions_all_non_blocking"):
        assert all(not question.blocking for question in generation.clarifying_questions)

    intent = mission.design_intent
    if intent is not None:
        intent_blob = " ".join(
            [
                intent.theme,
                intent.problem_statement,
                intent.social_background,
                intent.cultural_context,
                intent.desired_experience,
                " ".join(intent.core_questions),
            ]
        )
        needles = expectations.get("design_intent_theme_contains_any") or []
        if needles:
            assert _contains_any(intent_blob, needles), (
                f"design_intent missing {needles}: {intent_blob}"
            )
    elif expectations.get("design_intent_theme_contains_any"):
        raise AssertionError("expected design_intent on mission but none was generated")

    for scale in expectations.get("intervention_scales_any") or []:
        assert scale in scales, f"expected scale {scale} in {scales}"

    for needle in expectations.get("forbidden_fabricated_substrings") or []:
        constraint_text = " ".join(c.value for c in mission.known_constraints)
        assert needle not in constraint_text, f"fabricated value leaked: {needle}"

    for category in expectations.get("knowledge_gap_categories_any") or []:
        assert category in gap_categories, f"expected gap category {category}"
    for category in expectations.get("knowledge_gap_categories_none") or []:
        assert category not in gap_categories, f"unexpected gap category {category}"

    if expectations.get("no_area_gap_when_confirmed_facts"):
        assert KnowledgeGapCategory.AREA.value not in gap_categories

    needles = expectations.get("knowledge_gap_question_contains_any") or []
    if needles:
        assert _contains_any(gap_text, needles), f"gap text missing {needles}: {gap_text}"

    needles = expectations.get("clarifying_question_contains_any") or []
    if needles:
        assert _contains_any(question_text, needles), (
            f"questions missing {needles}: {question_text}"
        )

    max_q = expectations.get("max_clarifying_questions")
    if max_q is not None:
        assert len(generation.clarifying_questions) <= int(max_q)

    min_stakeholders = expectations.get("stakeholder_min_count")
    if min_stakeholders is not None:
        assert len(mission.stakeholders) >= int(min_stakeholders)

    needles = expectations.get("out_of_scope_contains_any") or []
    if needles:
        assert _contains_any(out_scope, needles), f"out_of_scope missing {needles}"

    for value in expectations.get("preserve_fact_substrings") or []:
        constraint_text = " ".join(c.value for c in mission.known_constraints)
        assert value in constraint_text, f"confirmed fact {value} not preserved"

    for value in expectations.get("forbidden_text_anywhere") or []:
        mission_blob = " ".join(
            [
                mission.title,
                mission.task_statement,
                out_scope,
                gap_text,
                question_text,
                " ".join(mission.key_unknowns),
            ]
        )
        assert value not in mission_blob, f"forbidden text present in mission: {value}"

    needles = expectations.get("workstream_title_contains_any") or []
    if needles:
        assert _contains_any(ws_titles, needles), f"workstreams missing {needles}"

    for ws_type in expectations.get("workstream_type_any") or []:
        assert ws_type in ws_types, f"expected workstream type {ws_type} in {ws_types}"

    for dtype in expectations.get("deliverable_type_any") or []:
        assert dtype in deliverable_types, f"expected deliverable type {dtype}"

    if expectations.get("presentation_deliverable_required"):
        assert DeliverableType.PRESENTATION.value in selected_types or any(
            item.deliverable_type == DeliverableType.PRESENTATION and item.selected
            for item in plan.deliverables
        ), "expected a selected presentation deliverable"

    if expectations.get("prefer_report_not_default_scheme_ppt"):
        assert DeliverableType.REPORT.value in selected_types or any(
            item.deliverable_type == DeliverableType.REPORT and (item.required or item.selected)
            for item in plan.deliverables
        )
        scheme = [
            item
            for item in plan.deliverables
            if item.deliverable_type == DeliverableType.PRESENTATION
            and "完整建筑设计" in item.title
        ]
        assert scheme, "expected a not-recommended full-scheme PPT marker"
        assert all(not item.selected for item in scheme)

    for needle in expectations.get("not_recommended_title_contains_any") or []:
        matches = [item for item in plan.deliverables if needle in item.title]
        assert matches, f"expected not-recommended deliverable containing {needle}"
        assert all(not item.selected for item in matches)

    for needle in expectations.get("deliverable_title_contains_none") or []:
        selected_titles = " ".join(item.title for item in plan.selected_deliverables())
        assert needle not in selected_titles

    if bridge is not None:
        for needle in expectations.get("out_of_scope_contains_any") or []:
            excluded = " ".join(bridge.request.excluded_topics)
            if needle in out_scope:
                assert needle in excluded or any(
                    needle in topic for topic in bridge.request.excluded_topics
                )
        # Workstream titles must not become required_sections wholesale.
        for ws in workstreams:
            if ws.selected:
                assert ws.title not in bridge.request.required_sections
    elif execution_plans is not None and not expectations.get("presentation_deliverable_required"):
        # Non-PPT plans must never get a silent PresentationRequest.
        assert all(item.presentation_request is None for item in execution_plans)
        non_ppt = [item for item in execution_plans if not item.is_presentation]
        assert non_ppt
        for item in non_ppt:
            if item.supported:
                assert item.request_kind in {"question_list", "work_plan"}
            else:
                assert item.message

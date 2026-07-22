"""Tests for Archium Skill Registry / selection / prompt injection."""

from __future__ import annotations

from archium.application.agent_skills import (
    SkillPromptService,
    SkillRegistry,
    SkillSelectionService,
    apply_skills_to_request,
    get_skill_registry,
)
from archium.application.agent_skills.registry import default_skills_root
from archium.infrastructure.llm.base import LLMRequest


def test_registry_loads_all_shipped_skills() -> None:
    registry = SkillRegistry(default_skills_root())
    skills = registry.list_all()
    ids = {skill.id for skill in skills}
    assert "architectural-presentation-authoring" in ids
    assert "drawing-page-design" in ids
    assert "apply-studio-comments" in ids
    assert "visual-qa-review" in ids
    authoring = registry.require("architectural-presentation-authoring")
    assert authoring.version
    assert authoring.checksum
    assert authoring.prompt_uri.endswith("SKILL.md")
    assert "图纸不得 cover" in authoring.body or "contain" in authoring.body.lower()
    assert "drawing_contain" in authoring.required_rules


def test_selection_hospital_report_prefers_domain_pack() -> None:
    service = SkillSelectionService(get_skill_registry())
    selected = service.resolve_for_task(
        "renovation_report",
        project_type="hospital",
    )
    ids = [skill.id for skill in selected]
    assert "hospital-renovation-report" in ids
    assert "architectural-presentation-authoring" in ids


def test_selection_drawing_layout_includes_drawing_skill() -> None:
    service = SkillSelectionService(get_skill_registry())
    selected = service.resolve_for_task(
        "layout_plan",
        slide_type="drawing_focus",
    )
    ids = [skill.id for skill in selected]
    assert "drawing-page-design" in ids


def test_selection_studio_comment_uses_apply_skill() -> None:
    service = SkillSelectionService(get_skill_registry())
    selected = service.resolve_for_task("studio_comment")
    ids = [skill.id for skill in selected]
    assert ids == ["apply-studio-comments"] or "apply-studio-comments" in ids


def test_apply_skills_to_request_injects_bodies_and_metadata() -> None:
    request = LLMRequest(
        system_prompt="BASE SYSTEM",
        user_prompt="do work",
        temperature=0.1,
    )
    decorated, audit = apply_skills_to_request(
        request,
        task_type="art_direction",
        project_type="campus",
    )
    assert audit.skill_ids
    assert len(audit.skill_ids) == len(audit.skill_versions) == len(audit.skill_checksums)
    assert "campus-renovation-report" in audit.skill_ids or (
        "architectural-presentation-authoring" in audit.skill_ids
    )
    assert "Archium Agent Skills" in decorated.system_prompt
    assert decorated.metadata["skill_ids"]
    assert decorated.metadata["skill_versions"]
    assert decorated.metadata["skill_checksums"]
    assert decorated.user_prompt == "do work"


def test_prompt_service_audit_roundtrip() -> None:
    service = SkillPromptService()
    skills = service.resolve(task_type="visual_qa")
    audit = service.build_audit(skills, task_type="visual_qa")
    meta = audit.to_llm_metadata()
    assert meta["skill_task_type"] == "visual_qa"
    assert meta["skill_ids"].count(",") == max(0, len(audit.skill_ids) - 1)

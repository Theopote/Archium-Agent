"""Inject selected Archium skills into LLM prompts and request metadata."""

from __future__ import annotations

from archium.application.agent_skills.registry import SkillRegistry, get_skill_registry
from archium.application.agent_skills.selection import SkillSelectionService
from archium.domain.agent_skill import ArchiumSkillDefinition, SkillInvocationAudit
from archium.infrastructure.llm.base import LLMRequest

_MAX_BODY_CHARS = 6000


class SkillPromptService:
    """Resolve skills for a task and decorate LLMRequest for auditability."""

    def __init__(
        self,
        *,
        registry: SkillRegistry | None = None,
        selection: SkillSelectionService | None = None,
    ) -> None:
        self._registry = registry or get_skill_registry()
        self._selection = selection or SkillSelectionService(self._registry)

    def resolve(
        self,
        *,
        task_type: str,
        slide_type: str | None = None,
        project_type: str | None = None,
        audience: str | None = None,
        limit: int = 6,
    ) -> list[ArchiumSkillDefinition]:
        return self._selection.resolve_for_task(
            task_type,
            slide_type=slide_type,
            project_type=project_type,
            audience=audience,
            limit=limit,
        )

    def build_audit(
        self,
        skills: list[ArchiumSkillDefinition],
        *,
        task_type: str,
        slide_type: str | None = None,
        project_type: str | None = None,
        audience: str | None = None,
    ) -> SkillInvocationAudit:
        return SkillInvocationAudit.from_skills(
            skills,
            task_type=task_type,
            slide_type=slide_type,
            project_type=project_type,
            audience=audience,
        )

    def render_prompt_block(self, skills: list[ArchiumSkillDefinition]) -> str:
        if not skills:
            return ""
        parts = [
            "【Archium Agent Skills — 必须遵守的产品规则】",
            "以下技能已由 SkillSelectionService 选定；生成时不得违反 required_rules。",
        ]
        for skill in skills:
            body = skill.body.strip()
            if len(body) > _MAX_BODY_CHARS:
                body = body[:_MAX_BODY_CHARS].rstrip() + "\n…(truncated)"
            rules = ", ".join(skill.required_rules) if skill.required_rules else "(see body)"
            parts.append(
                f"\n### Skill `{skill.id}` v{skill.version} ({skill.checksum[:12]})\n"
                f"title: {skill.title}\n"
                f"required_rules: {rules}\n"
                f"prompt_uri: {skill.prompt_uri}\n\n"
                f"{body}"
            )
        return "\n".join(parts).rstrip() + "\n"

    def apply_to_request(
        self,
        request: LLMRequest,
        *,
        task_type: str,
        slide_type: str | None = None,
        project_type: str | None = None,
        audience: str | None = None,
        limit: int = 6,
        inject_bodies: bool = True,
    ) -> tuple[LLMRequest, SkillInvocationAudit]:
        skills = self.resolve(
            task_type=task_type,
            slide_type=slide_type,
            project_type=project_type,
            audience=audience,
            limit=limit,
        )
        audit = self.build_audit(
            skills,
            task_type=task_type,
            slide_type=slide_type,
            project_type=project_type,
            audience=audience,
        )
        system_prompt = request.system_prompt
        if inject_bodies and skills:
            block = self.render_prompt_block(skills)
            system_prompt = f"{request.system_prompt.rstrip()}\n\n{block}"
        metadata = dict(request.metadata)
        metadata.update(audit.to_llm_metadata())
        decorated = LLMRequest(
            system_prompt=system_prompt,
            user_prompt=request.user_prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            json_mode=request.json_mode,
            metadata=metadata,
            image_paths=request.image_paths,
        )
        return decorated, audit


def apply_skills_to_request(
    request: LLMRequest,
    *,
    task_type: str,
    slide_type: str | None = None,
    project_type: str | None = None,
    audience: str | None = None,
    limit: int = 6,
    inject_bodies: bool = True,
) -> tuple[LLMRequest, SkillInvocationAudit]:
    """Module-level helper used by workflow / application services."""
    return SkillPromptService().apply_to_request(
        request,
        task_type=task_type,
        slide_type=slide_type,
        project_type=project_type,
        audience=audience,
        limit=limit,
        inject_bodies=inject_bodies,
    )

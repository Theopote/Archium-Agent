"""Select Archium skills for a workflow / LLM task context."""

from __future__ import annotations

from archium.application.agent_skills.registry import SkillRegistry, get_skill_registry
from archium.domain.agent_skill import ArchiumSkillDefinition


class SkillSelectionService:
    """Resolve which product skills apply to a task (deterministic, no LLM)."""

    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self._registry = registry or get_skill_registry()

    def resolve_for_task(
        self,
        task_type: str,
        slide_type: str | None = None,
        project_type: str | None = None,
        audience: str | None = None,
        *,
        limit: int = 6,
    ) -> list[ArchiumSkillDefinition]:
        task = (task_type or "").strip().lower()
        slide = (slide_type or "").strip().lower() or None
        project = (project_type or "").strip().lower() or None
        aud = (audience or "").strip().lower() or None

        scored: list[tuple[int, str, ArchiumSkillDefinition]] = []
        for skill in self._registry.list_all():
            score = self._score(
                skill,
                task_type=task,
                slide_type=slide,
                project_type=project,
                audience=aud,
            )
            if score <= 0:
                continue
            scored.append((score, skill.id, skill))

        scored.sort(key=lambda item: (-item[0], item[1]))
        selected = [item[2] for item in scored[: max(1, limit)]]

        # Always keep the authoring spine when any presentation stage matches.
        authoring = self._registry.get("architectural-presentation-authoring")
        if (
            authoring is not None
            and authoring.id not in {skill.id for skill in selected}
            and task
            in {
                "art_direction",
                "outline",
                "slide_plan",
                "layout_plan",
                "manuscript",
                "renovation_report",
                "visual_qa",
            }
        ):
            selected = [authoring, *selected][:limit]
        return selected

    @staticmethod
    def _score(
        skill: ArchiumSkillDefinition,
        *,
        task_type: str,
        slide_type: str | None,
        project_type: str | None,
        audience: str | None,
    ) -> int:
        stages = {item.lower() for item in skill.applicable_stages}
        if task_type not in stages and "*" not in stages:
            return 0

        score = 10
        slide_types = {item.lower() for item in skill.applicable_slide_types}
        if slide_type:
            if "*" in slide_types:
                score += 1
            elif slide_type in slide_types:
                score += 8
            else:
                return 0
        elif "*" not in slide_types and slide_types:
            # Slide-specific skill without a slide context — weak match only.
            score -= 3

        projects = {item.lower() for item in skill.applicable_project_types}
        if project_type:
            if project_type in projects:
                score += 12
            elif "*" in projects:
                score += 1
            else:
                return 0

        audiences = {item.lower() for item in skill.applicable_audiences}
        if audience:
            if audience in audiences:
                score += 4
            elif "*" not in audiences and audiences:
                return 0

        # Prefer domain packs when project_type matches.
        if skill.id.endswith("-report") and project_type and project_type in projects:
            score += 5
        return score

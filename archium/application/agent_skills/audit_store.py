"""Persist SkillInvocationAudit for Planning / Layout / Critic runs."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from archium.config.settings import Settings, get_settings
from archium.domain.agent_skill import SkillInvocationAudit
from archium.logging import get_logger

logger = get_logger(__name__, operation="skill_audit")


class SkillAuditStore:
    """Append-only JSONL audits under ``data/projects/<id>/cache/skill_audits/``."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def record(
        self,
        audit: SkillInvocationAudit,
        *,
        project_id: UUID | None = None,
        presentation_id: UUID | None = None,
        slide_id: UUID | None = None,
    ) -> Path | None:
        if not audit.skill_ids:
            return None
        root = self._settings.project_storage_path
        if project_id is not None:
            directory = root / str(project_id) / "cache" / "skill_audits"
        else:
            directory = root / "_global" / "cache" / "skill_audits"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "invocations.jsonl"
        payload = {
            **audit.model_dump(mode="json"),
            "presentation_id": str(presentation_id) if presentation_id else None,
            "slide_id": str(slide_id) if slide_id else None,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        logger.info(
            "Skill audit recorded task=%s skills=%s",
            audit.task_type,
            ",".join(audit.skill_ids),
        )
        return path


def record_skill_audit(
    audit: SkillInvocationAudit,
    *,
    project_id: UUID | None = None,
    presentation_id: UUID | None = None,
    slide_id: UUID | None = None,
    settings: Settings | None = None,
) -> Path | None:
    return SkillAuditStore(settings).record(
        audit,
        project_id=project_id,
        presentation_id=presentation_id,
        slide_id=slide_id,
    )

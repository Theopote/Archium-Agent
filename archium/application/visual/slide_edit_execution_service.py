"""Execute unified SlideEditCommand via existing visual/content services."""

from __future__ import annotations

from sqlalchemy.orm import Session

from archium.domain.visual.slide_edit_command import SlideEditCommand, SlideEditScope
from archium.exceptions import WorkflowError
from archium.ui.studio_service import (
    apply_slide_content_adaptation,
    apply_slide_visual_edit,
)


class SlideEditExecutionService:
    """Route Studio edit commands to the correct application service."""

    def execute(self, session: Session, command: SlideEditCommand) -> object:
        if command.scope == SlideEditScope.VISUAL:
            if command.text:
                return apply_slide_visual_edit(
                    session,
                    command.slide_id,
                    text=command.text,
                )
            return apply_slide_visual_edit(
                session,
                command.slide_id,
                intent=command.action,
                params=dict(command.params),
            )
        if command.scope == SlideEditScope.CONTENT:
            if command.text:
                return apply_slide_content_adaptation(
                    session,
                    command.slide_id,
                    text=command.text,
                )
            return apply_slide_content_adaptation(
                session,
                command.slide_id,
                action=command.action,
            )
        raise WorkflowError(f"Unsupported edit scope: {command.scope}")

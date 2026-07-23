"""Execute unified SlideEditCommand via application visual/content services."""

from __future__ import annotations

from sqlalchemy.orm import Session

from archium.application.content_adaptation_service import ContentAdaptationService
from archium.application.visual.visual_edit_service import VisualEditService
from archium.config.settings import get_settings
from archium.domain.content_adaptation import (
    action_from_value,
    parse_content_adaptation_text,
)
from archium.domain.visual.edit_intent import intent_from_preset
from archium.domain.visual.slide_edit_command import SlideEditCommand, SlideEditScope
from archium.exceptions import WorkflowError


class SlideEditExecutionService:
    """Route Studio edit commands to the correct application service."""

    def execute(self, session: Session, command: SlideEditCommand) -> object:
        if command.scope == SlideEditScope.VISUAL:
            return self._apply_visual(session, command)
        if command.scope == SlideEditScope.CONTENT:
            return self._apply_content(session, command)
        raise WorkflowError(f"Unsupported edit scope: {command.scope}")

    def _apply_visual(self, session: Session, command: SlideEditCommand) -> object:
        service = VisualEditService(session, settings=get_settings())
        if command.text:
            return service.apply_text(command.slide_id, command.text)
        resolved = intent_from_preset(command.action or "")
        if resolved is None:
            raise WorkflowError(f"Unsupported visual edit intent: {command.action}")
        return service.apply_intent(
            command.slide_id,
            resolved,
            params=dict(command.params),
        )

    def _apply_content(self, session: Session, command: SlideEditCommand) -> object:
        service = ContentAdaptationService(session)
        if command.text:
            resolved = parse_content_adaptation_text(command.text)
            if resolved is None:
                raise WorkflowError("无法识别内容适配意图。")
            return service.apply(command.slide_id, resolved)
        resolved = action_from_value(command.action or "")
        if resolved is None:
            raise WorkflowError(f"Unsupported content adaptation: {command.action}")
        return service.apply(command.slide_id, resolved)

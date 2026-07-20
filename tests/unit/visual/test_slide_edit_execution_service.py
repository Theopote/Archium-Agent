"""Unit tests for unified SlideEditCommand execution."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.slide_edit_execution_service import SlideEditExecutionService
from archium.domain.visual.slide_edit_command import SlideEditCommand, SlideEditScope
from archium.exceptions import WorkflowError
from sqlalchemy.orm import Session


def test_execute_rejects_unknown_scope(db_session: Session) -> None:
    command = SlideEditCommand.model_construct(
        slide_id=uuid4(),
        scope="unknown",  # type: ignore[arg-type]
        action="reduce_text",
    )
    with pytest.raises(WorkflowError, match="Unsupported edit scope"):
        SlideEditExecutionService().execute(db_session, command)


def test_execute_visual_intent_requires_existing_slide(db_session: Session) -> None:
    command = SlideEditCommand(
        slide_id=uuid4(),
        scope=SlideEditScope.VISUAL,
        action="reduce_text",
    )
    with pytest.raises(WorkflowError):
        SlideEditExecutionService().execute(db_session, command)

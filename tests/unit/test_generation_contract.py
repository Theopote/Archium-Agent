from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from archium.application.generation_contract import (
    build_generation_contract,
    validate_generation_contract,
)
from archium.domain.enums import ApprovalStatus
from archium.exceptions import WorkflowError


def _artifact(kind: str) -> MagicMock:
    artifact = MagicMock()
    artifact.id = uuid4()
    artifact.version = 1
    artifact.approval_status = ApprovalStatus.APPROVED
    artifact.model_dump.return_value = {"kind": kind, "body": "approved"}
    return artifact


def test_generation_contract_rejects_changed_approved_content() -> None:
    brief = _artifact("brief")
    storyline = _artifact("storyline")
    outline = _artifact("outline")
    design_brief = MagicMock()
    design_brief.page_order = 0
    design_brief.model_dump.return_value = {"page_order": 0, "claim": "A"}
    outline.page_design_briefs = [design_brief]
    context = SimpleNamespace(
        presentation=SimpleNamespace(id=uuid4()),
        brief=brief,
        storyline=storyline,
        outline=outline,
    )
    contract = build_generation_contract(context, actor_id="reviewer-1")

    outline.model_dump.return_value = {"kind": "outline", "body": "changed"}

    with pytest.raises(WorkflowError, match="生成契约已失效"):
        validate_generation_contract(contract, context)

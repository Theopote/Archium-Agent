"""Unit tests for mission draft parsing and validation."""

from __future__ import annotations

from uuid import uuid4

from archium.application.mission_parser import parse_mission_draft, validate_mission_draft
from archium.domain.enums import VerificationStatus
from archium.domain.fact import ProjectFact
from archium.infrastructure.llm.mission_schemas import (
    MissionGenerationDraft,
)


def test_validate_rejects_unsupported_confirmed_metric() -> None:
    draft = MissionGenerationDraft.model_validate(
        {
            "title": "测试",
            "task_statement": "测试任务",
            "known_constraints": [
                {
                    "name": "建筑面积",
                    "value": "12000 ㎡",
                    "verification_status": "user_confirmed",
                }
            ],
        }
    )
    result = validate_mission_draft(draft, [])
    assert not result.ok
    assert any("缺少事实账本依据" in error for error in result.errors)


def test_parse_caps_clarifying_questions() -> None:
    draft = MissionGenerationDraft.model_validate(
        {
            "title": "测试",
            "task_statement": "测试",
            "clarifying_questions": [
                {"question": f"问题{i}", "why_asked": "原因"} for i in range(7)
            ],
        }
    )
    parsed = parse_mission_draft(draft, project_id=uuid4(), facts=[])
    assert len(parsed.clarifying_questions) == 5
    assert any("超过" in warning for warning in parsed.validation_warnings)


def test_parse_injects_confirmed_facts() -> None:
    project_id = uuid4()
    draft = MissionGenerationDraft(title="消防站", task_statement="新建消防站")
    facts = [
        ProjectFact(
            project_id=project_id,
            key="building_area",
            label="建筑面积",
            value=4500,
            unit="㎡",
            verification_status=VerificationStatus.USER_CONFIRMED,
        )
    ]
    facts[0].confirm()
    parsed = parse_mission_draft(draft, project_id=project_id, facts=facts)
    values = " ".join(item.value for item in parsed.mission.known_constraints)
    assert "4500" in values

"""Unit tests for schema usage validation helpers."""

from __future__ import annotations

from archium.application.visual.schema_usage_validator import (
    schema_supports_drawing,
    validate_schema_length_bounds,
    validate_usage_conditions,
)
from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    ContentRequirement,
    ContentRole,
    UsageCondition,
    VisualRequirement,
)
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
)


def test_validate_usage_conditions_functional_type_mismatch() -> None:
    schema = ArchitecturalContentSchema(
        name="content/site-plan",
        page_purpose="总平面",
        usage_conditions=[
            UsageCondition(field="functional_type", operator="eq", value="content"),
        ],
    )
    violations = validate_usage_conditions(
        schema,
        functional_type=FunctionalSlideType.COVER,
        content_type=ArchitecturalContentType.DRAWING_FOCUS,
    )
    assert any("functional_type" in item for item in violations)


def test_validate_usage_conditions_requires_drawing() -> None:
    schema = ArchitecturalContentSchema(
        name="content/text-only",
        page_purpose="说明",
        usage_conditions=[
            UsageCondition(field="requires_drawing", operator="eq", value=True),
        ],
    )
    violations = validate_usage_conditions(
        schema,
        functional_type=FunctionalSlideType.CONTENT,
        content_type=ArchitecturalContentType.PHOTO_ANALYSIS,
    )
    assert any("drawing-capable" in item for item in violations)


def test_validate_usage_conditions_evidence_count_and_section() -> None:
    schema = ArchitecturalContentSchema(
        name="content/evidence",
        page_purpose="证据页",
        usage_conditions=[
            UsageCondition(field="min_evidence_count", operator="gte", value=2),
            UsageCondition(
                field="section_category",
                operator="in",
                value=["problem", "solution"],
            ),
        ],
    )
    violations = validate_usage_conditions(
        schema,
        functional_type=FunctionalSlideType.CONTENT,
        content_type=ArchitecturalContentType.PHOTO_ANALYSIS,
        section_category="intro",
        evidence_count=1,
    )
    assert any("evidence_count" in item for item in violations)
    assert any("section_category" in item for item in violations)


def test_schema_supports_drawing_from_visual_evidence() -> None:
    schema = ArchitecturalContentSchema(
        name="content/plan",
        page_purpose="图纸",
        visual_evidence=[
            VisualRequirement(role="drawing", required=True, min_count=1),
        ],
    )
    assert schema_supports_drawing(schema) is True


def test_validate_schema_length_bounds_flags_requirement_ranges() -> None:
    schema = ArchitecturalContentSchema(
        name="content/bad-requirement",
        page_purpose="测试",
        required_content=[
            ContentRequirement(
                role=ContentRole.TITLE,
                required=True,
                min_length=200,
                max_length=50,
            )
        ],
    )
    blockers = validate_schema_length_bounds(schema)
    assert any("min_length exceeds max_length" in item for item in blockers)

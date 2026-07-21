"""Validate ArchitecturalContentSchema usage conditions and length bounds."""

from __future__ import annotations

from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    UsageCondition,
)
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
)


def validate_schema_length_bounds(schema: ArchitecturalContentSchema) -> list[str]:
    """Return blocker messages for invalid schema-level text length bounds."""
    hydrated = schema.hydrate_semantic_contract()
    blockers: list[str] = []
    if hydrated.min_text_length and hydrated.max_text_length:
        if hydrated.min_text_length > hydrated.max_text_length:
            blockers.append(
                "schema min_text_length exceeds max_text_length "
                f"({hydrated.min_text_length} > {hydrated.max_text_length})"
            )
    for requirement in hydrated.required_content + hydrated.evidence_items:
        if requirement.min_length > requirement.max_length:
            blockers.append(
                f"{requirement.role.value} min_length exceeds max_length"
            )
    return blockers


def validate_usage_conditions(
    schema: ArchitecturalContentSchema,
    *,
    functional_type: FunctionalSlideType,
    content_type: ArchitecturalContentType,
    section_category: str = "",
    evidence_count: int = 0,
) -> list[str]:
    """Return messages when schema usage_conditions are not satisfied."""
    violations: list[str] = []
    for condition in schema.usage_conditions:
        message = _evaluate_usage_condition(
            condition,
            schema=schema,
            functional_type=functional_type,
            content_type=content_type,
            section_category=section_category,
            evidence_count=evidence_count,
        )
        if message:
            violations.append(message)
    return violations


def _evaluate_usage_condition(
    condition: UsageCondition,
    *,
    schema: ArchitecturalContentSchema,
    functional_type: FunctionalSlideType,
    content_type: ArchitecturalContentType,
    section_category: str,
    evidence_count: int,
) -> str | None:
    field = condition.field
    operator = condition.operator
    value = condition.value

    if field == "functional_type":
        actual = functional_type.value
        expected = str(value)
        if operator == "eq" and actual != expected:
            return f"usage_condition functional_type must be {expected}"
        if operator == "not_eq" and actual == expected:
            return f"usage_condition functional_type must not be {expected}"
        if operator == "in" and isinstance(value, list) and actual not in value:
            return f"usage_condition functional_type must be one of {value}"
    elif field == "content_type":
        actual = content_type.value
        expected = str(value)
        if operator == "eq" and actual != expected:
            return f"usage_condition content_type must be {expected}"
        if operator == "in" and isinstance(value, list) and actual not in value:
            return f"usage_condition content_type must be one of {value}"
    elif field == "requires_drawing":
        required = bool(value)
        if required and not schema_supports_drawing(schema):
            return "usage_condition requires drawing-capable schema"
    elif field == "min_evidence_count":
        minimum = int(value) if isinstance(value, (int, str)) and str(value).isdigit() else 0
        if operator == "gte" and evidence_count < minimum:
            return f"usage_condition requires evidence_count >= {minimum}"
    elif field == "section_category":
        actual = section_category.strip().casefold()
        expected = str(value).strip().casefold()
        if operator == "eq" and actual != expected:
            return f"usage_condition section_category must be {value}"
        if operator == "in" and isinstance(value, list):
            allowed = {str(item).strip().casefold() for item in value}
            if actual not in allowed:
                return f"usage_condition section_category must be one of {value}"
    return None


def schema_supports_drawing(schema: ArchitecturalContentSchema) -> bool:
    hydrated = schema.hydrate_semantic_contract()
    if hydrated.supports_drawing:
        return True
    return any(item.role == "drawing" for item in hydrated.visual_evidence)

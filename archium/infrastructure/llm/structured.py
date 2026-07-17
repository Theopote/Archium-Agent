"""Structured output parsing and validation helpers."""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from archium.exceptions import StructuredOutputError

T = TypeVar("T", bound=BaseModel)

_CODE_FENCE_RE = re.compile(
    r"^```(?:json|markdown|md)?\s*\n(.*)\n```\s*$",
    re.DOTALL,
)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def strip_code_fence(text: str) -> str:
    """Remove Markdown code fences from model output."""
    stripped = text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    return match.group(1).strip() if match else stripped


def extract_json_text(text: str) -> str:
    """Extract a JSON object or array substring from model text."""
    cleaned = strip_code_fence(text)
    if cleaned.startswith("{") or cleaned.startswith("["):
        return cleaned
    match = _JSON_OBJECT_RE.search(cleaned)
    if match is None:
        raise StructuredOutputError("Model response does not contain JSON")
    return match.group(0)


def parse_json(text: str) -> Any:
    """Parse JSON from model output."""
    try:
        return json.loads(extract_json_text(text))
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(f"Invalid JSON in model response: {exc}") from exc


def validate_structured(data: Any, schema: type[T]) -> T:
    """Validate parsed data against a Pydantic schema."""
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise StructuredOutputError(f"Structured output validation failed: {exc}") from exc


def parse_and_validate(text: str, schema: type[T]) -> T:
    """Parse JSON from text and validate against schema."""
    return validate_structured(parse_json(text), schema)

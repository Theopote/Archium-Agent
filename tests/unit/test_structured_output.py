"""Tests for structured output parsing."""

from __future__ import annotations

import pytest
from archium.exceptions import StructuredOutputError
from archium.infrastructure.llm.structured import parse_and_validate, strip_code_fence
from pydantic import BaseModel


class SampleModel(BaseModel):
    name: str
    count: int


class TestStripCodeFence:
    def test_plain_json(self) -> None:
        assert strip_code_fence('{"a": 1}') == '{"a": 1}'

    def test_json_fence(self) -> None:
        raw = '```json\n{"a": 1}\n```'
        assert strip_code_fence(raw) == '{"a": 1}'


class TestParseAndValidate:
    def test_valid_json(self) -> None:
        result = parse_and_validate('{"name": "test", "count": 3}', SampleModel)
        assert result.name == "test"
        assert result.count == 3

    def test_json_in_fence(self) -> None:
        raw = '```json\n{"name": "x", "count": 1}\n```'
        result = parse_and_validate(raw, SampleModel)
        assert result.name == "x"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(StructuredOutputError):
            parse_and_validate("not json", SampleModel)

    def test_validation_error_raises(self) -> None:
        with pytest.raises(StructuredOutputError, match="validation failed"):
            parse_and_validate('{"name": "x", "count": "bad"}', SampleModel)

    def test_extract_embedded_object(self) -> None:
        text = 'Here is the result:\n{"name": "embedded", "count": 2}\nDone.'
        result = parse_and_validate(text, SampleModel)
        assert result.name == "embedded"

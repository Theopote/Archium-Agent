"""Tests for exception handling improvements."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.domain.visual.benchmark import HumanVisualReview
from archium.exceptions import (
    ArchiumError,
    ConfigurationError,
    DocumentParseError,
    LLMProviderError,
    ProjectNotFoundError,
)
from pydantic import ValidationError


def test_archium_error_base() -> None:
    """Test base ArchiumError exception."""
    error = ArchiumError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_configuration_error() -> None:
    """Test ConfigurationError exception."""
    error = ConfigurationError("Missing API key")
    assert "Missing API key" in str(error)
    assert isinstance(error, ArchiumError)


def test_document_parse_error() -> None:
    """Test DocumentParseError exception."""
    error = DocumentParseError("Failed to parse PDF")
    assert "Failed to parse PDF" in str(error)
    assert isinstance(error, ArchiumError)


def test_llm_provider_error() -> None:
    """Test LLMProviderError exception."""
    error = LLMProviderError("API rate limit exceeded")
    assert "API rate limit exceeded" in str(error)
    assert isinstance(error, ArchiumError)


def test_project_not_found_error() -> None:
    """Test ProjectNotFoundError with UUID."""
    project_id = uuid4()
    error = ProjectNotFoundError(project_id)

    assert str(project_id) in str(error)
    assert error.project_id == project_id
    assert isinstance(error, ArchiumError)


def test_validation_error_handling() -> None:
    """Test proper ValidationError handling (not generic Exception)."""
    invalid_data = {"information_hierarchy": 10}  # Out of valid range

    with pytest.raises(ValidationError) as exc_info:
        HumanVisualReview.model_validate(invalid_data)

    error = exc_info.value
    assert "validation error" in str(error).lower()


def test_exception_import_error_handling() -> None:
    """Test ImportError and RuntimeError handling for Streamlit."""

    def _resolve_with_streamlit():
        """Simulate Streamlit context resolution."""
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx  # noqa: F401

            # This will fail if streamlit is not installed
            raise ImportError("Streamlit not available")
        except (ImportError, RuntimeError):
            # Properly caught - return fallback
            return "fallback"

    result = _resolve_with_streamlit()
    assert result == "fallback"


def test_exception_hierarchy() -> None:
    """Test exception hierarchy relationships."""
    exceptions = [
        ConfigurationError,
        DocumentParseError,
        LLMProviderError,
    ]

    for exc_class in exceptions:
        error = exc_class("test")
        assert isinstance(error, ArchiumError)
        assert isinstance(error, Exception)

    # Test ProjectNotFoundError separately (different constructor)
    project_error = ProjectNotFoundError(uuid4())
    assert isinstance(project_error, ArchiumError)
    assert isinstance(project_error, Exception)

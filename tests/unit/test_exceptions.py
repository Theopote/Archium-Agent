"""Tests for the exception hierarchy."""

from archium.exceptions import (
    ArchiumError,
    ConfigurationError,
    DocumentParseError,
    LLMProviderError,
    RenderingError,
    RepositoryError,
    StructuredOutputError,
    WorkflowError,
)


def test_exception_hierarchy() -> None:
    assert issubclass(ConfigurationError, ArchiumError)
    assert issubclass(DocumentParseError, ArchiumError)
    assert issubclass(LLMProviderError, ArchiumError)
    assert issubclass(StructuredOutputError, ArchiumError)
    assert issubclass(RenderingError, ArchiumError)
    assert issubclass(RepositoryError, ArchiumError)
    assert issubclass(WorkflowError, ArchiumError)

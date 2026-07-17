"""Archium exception hierarchy."""


class ArchiumError(Exception):
    """Base exception for all Archium errors."""


class ConfigurationError(ArchiumError):
    """Raised when required configuration is missing or invalid."""


class DocumentParseError(ArchiumError):
    """Raised when document parsing fails."""


class LLMProviderError(ArchiumError):
    """Raised when an LLM provider call fails."""


class StructuredOutputError(ArchiumError):
    """Raised when structured model output cannot be validated."""


class RenderingError(ArchiumError):
    """Raised when presentation rendering fails."""


class RepositoryError(ArchiumError):
    """Raised when a database repository operation fails."""


class WorkflowError(ArchiumError):
    """Raised when a workflow execution fails."""

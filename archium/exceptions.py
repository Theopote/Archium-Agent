"""Archium exception hierarchy."""

from __future__ import annotations

from uuid import UUID


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


class AccessDeniedError(ArchiumError):
    """Raised when an actor lacks the required project permission."""

    def __init__(
        self,
        message: str = "Access denied",
        *,
        project_id: UUID | None = None,
        actor_id: str | None = None,
        permission: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.actor_id = actor_id
        self.permission = permission


class WorkflowError(ArchiumError):
    """Raised when a workflow execution fails."""


class ValidationError(ArchiumError):
    """Raised when domain or input validation fails."""


class ProjectNotFoundError(ArchiumError):
    """Raised when a project record does not exist."""

    def __init__(self, project_id: UUID) -> None:
        super().__init__(f"Project {project_id} not found")
        self.project_id = project_id


class PresentationNotFoundError(ArchiumError):
    """Raised when a presentation record does not exist."""

    def __init__(self, presentation_id: UUID) -> None:
        super().__init__(f"Presentation {presentation_id} not found")
        self.presentation_id = presentation_id


class SlideRevisionNotFoundError(ArchiumError):
    """Raised when a slide revision record does not exist."""

    def __init__(self, revision_id: UUID) -> None:
        super().__init__(f"Slide revision {revision_id} not found")
        self.revision_id = revision_id


class UnsupportedOperationError(ArchiumError):
    """Raised when a deprecated or removed API surface is invoked incorrectly."""


class ExternalServiceError(ArchiumError):
    """Raised when an external service (API, database, etc.) fails."""
    
    def __init__(
        self,
        message: str,
        *,
        service_name: str | None = None,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.service_name = service_name
        self.status_code = status_code
        self.retryable = retryable


class FileOperationError(ArchiumError):
    """Raised when file operations fail."""
    
    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        operation: str | None = None,
    ) -> None:
        super().__init__(message)
        self.file_path = file_path
        self.operation = operation


class ConcurrencyError(ArchiumError):
    """Raised when concurrent operations conflict."""
    
    def __init__(
        self,
        message: str = "Concurrent modification conflict",
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.resource_type = resource_type
        self.resource_id = resource_id


class RateLimitError(ArchiumError):
    """Raised when rate limits are exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: int | None = None,
        limit_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.limit_type = limit_type


# Audit / product aliases — prefer these names at call sites when clearer.
UserInputError = ValidationError
LLMExecutionError = LLMProviderError
WorkflowStateError = WorkflowError
ArtifactValidationError = ValidationError
ExternalToolUnavailableError = ExternalServiceError

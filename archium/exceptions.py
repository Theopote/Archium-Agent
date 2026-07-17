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

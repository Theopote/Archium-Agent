"""Domain enumerations — review bounded context (DOM-018)."""

from enum import StrEnum


class PipelineRole(StrEnum):
    """Logical pipeline roles — annotation vocabulary, not runtime Agent classes.

    See ``docs/architecture/pipeline-roles.md``. Services and workflow nodes
    implement these roles; do not add one Agent class per role.
    """

    RESEARCH = "research"
    NARRATIVE = "narrative"
    ARCHITECTURE = "architecture"
    COMPOSITION = "composition"
    LAYOUT = "layout"
    RENDER = "render"
    CRITIC = "critic"

class ReviewLayer(StrEnum):
    CONTENT = "content"
    EVIDENCE = "evidence"
    ARCHITECTURAL = "architectural"
    LAYOUT = "layout"
    SEMANTIC = "semantic"

class ReviewCategory(StrEnum):
    CITATION = "citation"
    CONTENT = "content"
    STRUCTURE = "structure"
    VISUAL = "visual"
    CONSISTENCY = "consistency"
    COVERAGE = "coverage"
    LENGTH = "length"
    OTHER = "other"

class ReviewSeverity(StrEnum):
    """Persisted review-issue severity. Convert via ``domain.visual.severity`` for gates."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    SUGGESTION = "suggestion"

class ValidationSeverity(StrEnum):
    """Severity for MissionValidationIssue (mission planning, not slide export gates).

    Map through ``domain.visual.severity.validation_to_gate`` if a gate view is needed.
    """

    FATAL = "fatal"
    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"

class ReviewStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"

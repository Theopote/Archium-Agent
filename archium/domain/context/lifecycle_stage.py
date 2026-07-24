"""Project lifecycle stage — where the project sits in the design process."""

from __future__ import annotations

from enum import StrEnum


class ProjectLifecycleStage(StrEnum):
    """Coarse design-process stage (not the same as ProjectStage or KnowledgeMaturityStage)."""

    IDEA = "idea"
    CONCEPT = "concept"
    RESEARCH = "research"
    DESIGN = "design"
    DOCUMENTATION = "documentation"

"""Shared architectural prompt frameworks (not Agent classes).

Inject these fragments into task SYSTEM prompts so building-related LLM calls
share one reasoning protocol instead of only role-play + field lists.
"""

from archium.prompts.frameworks.architectural_reasoning import (
    ARCHITECTURAL_REASONING_FRAMEWORK,
    ARCHITECTURAL_REASONING_VERSION,
)
from archium.prompts.frameworks.design_critique import (
    DESIGN_CRITIQUE_FRAMEWORK,
    DESIGN_CRITIQUE_FRAMEWORK_VERSION,
)
from archium.prompts.frameworks.research_knowledge import (
    RESEARCH_KNOWLEDGE_FRAMEWORK,
    RESEARCH_KNOWLEDGE_FRAMEWORK_VERSION,
)

__all__ = [
    "ARCHITECTURAL_REASONING_FRAMEWORK",
    "ARCHITECTURAL_REASONING_VERSION",
    "DESIGN_CRITIQUE_FRAMEWORK",
    "DESIGN_CRITIQUE_FRAMEWORK_VERSION",
    "RESEARCH_KNOWLEDGE_FRAMEWORK",
    "RESEARCH_KNOWLEDGE_FRAMEWORK_VERSION",
]

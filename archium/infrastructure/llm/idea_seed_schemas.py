"""Structured LLM output for IdeaSeed enrichment."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IdeaSeedDraft(BaseModel):
    theme: str = ""
    inspiration: str = ""
    keywords: list[str] = Field(default_factory=list)
    imagination_level: str = "open"

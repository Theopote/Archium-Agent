"""Structured idea seed — one-line inspiration before Mission."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel

_VALID_IMAGINATION = frozenset({"open", "grounded", "speculative"})


class IdeaSeed(DomainModel):
    """User's raw idea plus light structured enrichment (not a Mission)."""

    raw_input: str = Field(min_length=1)
    theme: str = ""
    inspiration: str = ""
    keywords: list[str] = Field(default_factory=list)
    imagination_level: str = "open"
    source: str = Field(default="user", max_length=40)

    def model_post_init(self, __context: object) -> None:
        level = (self.imagination_level or "open").strip().lower()
        if level not in _VALID_IMAGINATION:
            object.__setattr__(self, "imagination_level", "open")
        else:
            object.__setattr__(self, "imagination_level", level)

    @property
    def is_enriched(self) -> bool:
        return bool(
            self.theme.strip()
            or self.inspiration.strip()
            or any(item.strip() for item in self.keywords)
        )

    def to_prompt_block(self) -> str:
        """Compact text for direction / mission generation context."""
        sections: list[str] = [f"原始想法: {self.raw_input.strip()}"]
        if self.theme.strip():
            sections.append(f"主题线索: {self.theme.strip()}")
        if self.inspiration.strip():
            sections.append(f"灵感: {self.inspiration.strip()}")
        if self.keywords:
            cleaned = [item.strip() for item in self.keywords if item.strip()]
            if cleaned:
                sections.append("关键词: " + "、".join(cleaned))
        if self.imagination_level.strip():
            sections.append(f"想象尺度: {self.imagination_level.strip()}")
        return "\n".join(sections)

    @classmethod
    def from_raw(cls, raw_input: str, *, source: str = "user") -> IdeaSeed:
        text = raw_input.strip()
        return cls(raw_input=text, source=source)

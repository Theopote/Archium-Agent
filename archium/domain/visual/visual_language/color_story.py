"""ColorStory — color as emotion / concept roles, not a flat palette."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class ColorRole(StrEnum):
    EXISTING = "existing"
    INTERVENTION = "intervention"
    FUTURE = "future"
    CONFLICT = "conflict"
    NEUTRAL = "neutral"
    ACCENT = "accent"


class ColorStory(DomainModel):
    """Semantic color narrative bound to a design concept."""

    roles: dict[str, str] = Field(
        default_factory=dict,
        description="role → named swatch id (stone_gray, alert_red, …)",
    )
    meaning: dict[str, str] = Field(
        default_factory=dict,
        description="swatch or hue word → semantic meaning (existing, conflict, …)",
    )
    source: str = Field(default="rules", max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "roles": dict(self.roles),
            "meaning": dict(self.meaning),
            "source": self.source,
        }

    def as_legacy_list(self) -> list[str]:
        """Compat with VisualConcept.color_story list form."""
        ordered: list[str] = []
        for role in (
            ColorRole.EXISTING,
            ColorRole.CONFLICT,
            ColorRole.INTERVENTION,
            ColorRole.FUTURE,
            ColorRole.NEUTRAL,
            ColorRole.ACCENT,
        ):
            value = self.roles.get(role.value)
            if value and value not in ordered:
                ordered.append(value)
        for value in self.roles.values():
            if value not in ordered:
                ordered.append(value)
        return ordered[:6]


# Named swatches used by Case 001 / Grammar (hex resolved at render via DesignSystem).
NAMED_SWATCHES: dict[str, str] = {
    "gray": "#8A8680",
    "stone_gray": "#8A8680",
    "red": "#C45C26",
    "alert_red": "#C45C26",
    "white": "#F7F4EF",
    "warm_white": "#F7F4EF",
    "renew_green": "#4A7C59",
    "ink_black": "#1A1A1A",
    "axis_line": "#2C2C2C",
}

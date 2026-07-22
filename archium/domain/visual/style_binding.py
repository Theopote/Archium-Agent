"""Style bindings: token references vs explicit local overrides.

Theme changes should resolve as::

    Base RenderScene (geometry + content + token refs)
    + DesignSystem / DeckThemeTokens
    → Resolved RenderScene (for preview / export)

Nodes default to ``ThemeTokenReference``. Only Studio local edits write
``ExplicitStyleValue`` (hard-coded hex / pt). Accepting a ThemeChangeProposal
must switch DesignSystem — not bake colors into every node via SceneRevision.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from archium.domain._base import DomainModel


class ThemeTokenReference(DomainModel):
    """Indirection into DesignSystem / ThemeTokens (preferred default)."""

    kind: Literal["token"] = "token"
    token_key: str = Field(min_length=1, description="e.g. primary_text, colors.accent, typography.title")


class ExplicitStyleValue(DomainModel):
    """Hard-coded local override — only when the user intentionally pins a value."""

    kind: Literal["explicit"] = "explicit"
    value: str = Field(min_length=1)


StyleBinding = Annotated[
    ThemeTokenReference | ExplicitStyleValue,
    Field(discriminator="kind"),
]


def token_ref(token_key: str) -> ThemeTokenReference:
    return ThemeTokenReference(token_key=token_key)


def explicit_value(value: str) -> ExplicitStyleValue:
    return ExplicitStyleValue(value=value)


def is_token_binding(binding: StyleBinding | None) -> bool:
    return isinstance(binding, ThemeTokenReference)


def resolve_binding_value(
    binding: StyleBinding | None,
    *,
    token_lookup: dict[str, str],
    fallback: str,
) -> str:
    if binding is None:
        return fallback
    if isinstance(binding, ExplicitStyleValue):
        return binding.value
    return token_lookup.get(binding.token_key, fallback)

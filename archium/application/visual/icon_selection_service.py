"""Icon selection constrained by TemplateUsageBrief + IconUsagePolicy."""

from __future__ import annotations

from dataclasses import dataclass

from archium.application.visual.architectural_icon_registry import ArchitecturalIconMatcher
from archium.application.visual.icon_usage import accept_match, icons_allowed_for_family
from archium.application.visual.template_usage_brief_context import (
    TemplateUsageConstraints,
    constraints_from_brief,
)
from archium.domain.visual.architectural_icon import ArchitecturalIconMatch
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.icon_usage_policy import IconUsagePolicy, default_icon_usage_policy
from archium.domain.visual.template_usage_brief import TemplateUsageBrief


@dataclass(frozen=True)
class IconSelectionResult:
    query: str
    match: ArchitecturalIconMatch | None
    preferred_style: str
    template_usage_brief_id: str | None = None
    template_usage_brief_version: int | None = None
    notes: tuple[str, ...] = ()


class IconSelectionService:
    """Select architectural icons while honouring Brief style + usage policy."""

    def __init__(
        self,
        matcher: ArchitecturalIconMatcher | None = None,
        *,
        policy: IconUsagePolicy | None = None,
    ) -> None:
        self._matcher = matcher or ArchitecturalIconMatcher()
        self._policy = policy or default_icon_usage_policy()

    def select(
        self,
        query: str,
        *,
        brief: TemplateUsageBrief | None = None,
        constraints: TemplateUsageConstraints | None = None,
        layout_family: LayoutFamily | str | None = None,
    ) -> IconSelectionResult:
        notes: list[str] = []
        if layout_family is not None and not icons_allowed_for_family(
            layout_family, policy=self._policy
        ):
            return IconSelectionResult(
                query=query,
                match=None,
                preferred_style="line",
                notes=("icons forbidden for this layout family by IconUsagePolicy",),
            )

        resolved = constraints
        if resolved is None and brief is not None:
            resolved = constraints_from_brief(brief)
        preferred = (
            resolved.preferred_icon_style
            if resolved is not None
            else (brief.preferred_icon_style if brief is not None else "line")
        )
        raw = self._matcher.match(
            query, min_score=self._policy.min_match_confidence
        )
        match = accept_match(raw, policy=self._policy)
        if raw is not None and match is None:
            notes.append("match rejected by IconUsagePolicy confidence/decorative rules")

        if match is not None and preferred == "line":
            blob = " ".join(
                [
                    match.icon.id,
                    match.icon.canonical_name,
                    match.icon.description,
                    *match.icon.categories,
                ]
            ).lower()
            if any(token in blob for token in ("filled", "3d", "emoji", "photo-real")):
                notes.append(
                    f"rejected `{match.icon.id}` — brief prefers line icons"
                )
                match = None

        return IconSelectionResult(
            query=query,
            match=match,
            preferred_style=preferred,
            template_usage_brief_id=(
                str(brief.id)
                if brief is not None
                else (str(resolved.brief_id) if resolved is not None else None)
            ),
            template_usage_brief_version=(
                brief.version
                if brief is not None
                else (resolved.brief_version if resolved is not None else None)
            ),
            notes=tuple(notes),
        )

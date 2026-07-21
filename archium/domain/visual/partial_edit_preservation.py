"""System-level preservation contract for single-page Studio fine-tuning.

Interaction language: 「只修改我提到的部分」

Archium must not regenerate a whole-page lookalike image. Edits go:
RenderScene + StudioCommand → targeted node/block mutation → Before/After → Revision.

Hard invariants enforced by the preservation guard:
- unspecified nodes stay unchanged
- locked nodes stay unchanged
- asset identity stays unchanged unless an explicit replace command targets it
- page facts (SlideSpec message / key_points) stay unchanged
- citations (SlideSpec.source_citations + source-role nodes) stay unchanged
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel

PARTIAL_EDIT_INTERACTION_RULE = "只修改我提到的部分"

PRESERVATION_RULE_CAPTIONS: dict[str, str] = {
    "unspecified_nodes_unchanged": "未指定节点保持不变",
    "locked_nodes_unchanged": "锁定节点保持不变",
    "asset_identity_unchanged": "素材身份保持不变",
    "page_facts_unchanged": "页面事实保持不变",
    "citations_unchanged": "引用保持不变",
}


class PartialEditPreservationRule(StrEnum):
    UNSPECIFIED_NODES_UNCHANGED = "unspecified_nodes_unchanged"
    LOCKED_NODES_UNCHANGED = "locked_nodes_unchanged"
    ASSET_IDENTITY_UNCHANGED = "asset_identity_unchanged"
    PAGE_FACTS_UNCHANGED = "page_facts_unchanged"
    CITATIONS_UNCHANGED = "citations_unchanged"


class PreservationViolation(DomainModel):
    """One hard violation of the partial-edit contract."""

    rule: PartialEditPreservationRule
    message: str = Field(min_length=1)
    node_id: str | None = None
    detail: str = ""


class PartialEditPreservationReport(DomainModel):
    """Audit result attached to a SceneChangeProposal."""

    interaction_rule: str = PARTIAL_EDIT_INTERACTION_RULE
    enforced_rules: list[PartialEditPreservationRule] = Field(
        default_factory=lambda: list(PartialEditPreservationRule)
    )
    allowed_node_ids: list[str] = Field(default_factory=list)
    changed_node_ids: list[str] = Field(default_factory=list)
    violations: list[PreservationViolation] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def captions(self) -> list[str]:
        return [
            PRESERVATION_RULE_CAPTIONS.get(rule.value, rule.value)
            for rule in self.enforced_rules
        ]

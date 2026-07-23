"""DOM-009: shared ProposalStatus for scene and theme proposals."""

from __future__ import annotations

from archium.domain.visual.proposal_status import ProposalStatus
from archium.domain.visual.scene_change_proposal import (
    ProposalStatus as SceneProposalStatus,
)
from archium.domain.visual.theme_change_proposal import (
    ProposalStatus as ThemeSideProposalStatus,
)


def test_scene_and_theme_share_proposal_status_enum() -> None:
    assert SceneProposalStatus is ProposalStatus
    assert ThemeSideProposalStatus is ProposalStatus
    assert ProposalStatus.PARTIALLY_ACCEPTED.value == "partially_accepted"
    assert ProposalStatus.READY_WITH_WARNINGS.value == "ready_with_warnings"


def test_theme_proposal_status_type_removed() -> None:
    import archium.domain.visual.theme_change_proposal as theme_mod

    assert not hasattr(theme_mod, "ThemeProposalStatus")

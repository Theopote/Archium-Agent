"""Shared proposal lifecycle status (DOM-009).

Used by SceneChangeProposal and ThemeChangeProposal. Theme proposals are
all-or-nothing and do not emit ``PARTIALLY_ACCEPTED``; the value remains on
the shared vocabulary for scene partial accepts.
"""

from __future__ import annotations

from enum import StrEnum


class ProposalStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    ACCEPTED = "accepted"
    PARTIALLY_ACCEPTED = "partially_accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"

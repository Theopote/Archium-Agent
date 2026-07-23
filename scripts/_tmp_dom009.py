"""One-shot DOM-009 + DOM-014 helpers."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_slide_design_brief() -> None:
    path = ROOT / "archium/domain/slide_design_brief.py"
    text = path.read_text(encoding="utf-8")
    # Replace imports and BriefStatus block
    old_header = '''from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class BriefStatus(StrEnum):
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    CHANGES_PENDING = "changes_pending"


BRIEF_STATUS_LABELS_ZH: dict[BriefStatus, str] = {
    BriefStatus.DRAFT: "草稿",
    BriefStatus.READY_FOR_REVIEW: "待确认",
    BriefStatus.APPROVED: "已批准",
    BriefStatus.CHANGES_PENDING: "待重新确认",
}
'''
    new_header = '''from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from archium.domain._base import DomainModel
from archium.domain.enums import ApprovalStatus

# Brief UI labels keyed by ApprovalStatus (DOM-009).
# Legacy persisted value ``ready_for_review`` coerces to ``pending``.
BRIEF_STATUS_LABELS_ZH: dict[ApprovalStatus, str] = {
    ApprovalStatus.DRAFT: "草稿",
    ApprovalStatus.PENDING: "待确认",
    ApprovalStatus.APPROVED: "已批准",
    ApprovalStatus.CHANGES_PENDING: "待重新确认",
    ApprovalStatus.REJECTED: "已驳回",
}

_LEGACY_BRIEF_STATUS = {
    "ready_for_review": ApprovalStatus.PENDING,
}


def coerce_brief_approval_status(value: object) -> ApprovalStatus:
    """Accept ApprovalStatus, legacy brief strings, or ApprovalStatus values."""
    if isinstance(value, ApprovalStatus):
        return value
    raw = str(value).strip().casefold()
    if raw in _LEGACY_BRIEF_STATUS:
        return _LEGACY_BRIEF_STATUS[raw]
    return ApprovalStatus(raw)


# Deprecated alias name for call-site migration (same enum as ApprovalStatus).
BriefStatus = ApprovalStatus
'''
    if "class BriefStatus(StrEnum)" not in text:
        print("slide_design_brief already patched?")
    else:
        text = text.replace(old_header, new_header, 1)

    text = text.replace("status: BriefStatus = BriefStatus.DRAFT", "status: ApprovalStatus = ApprovalStatus.DRAFT")
    text = text.replace("self.status = BriefStatus.APPROVED", "self.status = ApprovalStatus.APPROVED")
    text = text.replace("if self.status == BriefStatus.APPROVED:", "if self.status == ApprovalStatus.APPROVED:")
    text = text.replace("self.status = BriefStatus.CHANGES_PENDING", "self.status = ApprovalStatus.CHANGES_PENDING")
    text = text.replace("if self.status == BriefStatus.DRAFT:", "if self.status == ApprovalStatus.DRAFT:")
    text = text.replace(
        "self.status = BriefStatus.READY_FOR_REVIEW",
        "self.status = ApprovalStatus.PENDING",
    )
    text = text.replace(
        "return self.status == BriefStatus.APPROVED",
        "return self.status == ApprovalStatus.APPROVED",
    )

    # Insert validator after status field if missing
    if "_coerce_legacy_brief_status" not in text:
        text = text.replace(
            "    status: ApprovalStatus = ApprovalStatus.DRAFT\n\n    def approve(self) -> None:",
            "    status: ApprovalStatus = ApprovalStatus.DRAFT\n\n"
            "    @field_validator(\"status\", mode=\"before\")\n"
            "    @classmethod\n"
            "    def _coerce_legacy_brief_status(cls, value: object) -> object:\n"
            "        if isinstance(value, str):\n"
            "            key = value.strip().casefold()\n"
            "            if key in _LEGACY_BRIEF_STATUS:\n"
            "                return _LEGACY_BRIEF_STATUS[key]\n"
            "        return value\n\n"
            "    def approve(self) -> None:",
        )
    path.write_text(text, encoding="utf-8")
    print("patched slide_design_brief")


def replace_brief_status_usages() -> None:
    replacements = [
        (
            "archium/workflow/visual_nodes.py",
            [
                (
                    "from archium.domain.slide_design_brief import BriefStatus, SlideDesignBrief",
                    "from archium.domain.enums import ApprovalStatus\n"
                    "from archium.domain.slide_design_brief import SlideDesignBrief",
                ),
                (
                    "usable = {BriefStatus.APPROVED, BriefStatus.READY_FOR_REVIEW}",
                    "usable = {ApprovalStatus.APPROVED, ApprovalStatus.PENDING}",
                ),
            ],
        ),
        (
            "archium/application/slide_design_brief_service.py",
            [
                (
                    "BriefStatus,",
                    "coerce_brief_approval_status,\n",
                ),
            ],
        ),
    ]
    # Simpler: read each known file and do global replaces
    files = {
        "archium/application/slide_design_brief_service.py": None,
        "archium/application/visual/visual_intent_service.py": None,
        "archium/application/review_service.py": None,
        "archium/ui/outline/design_brief_panel.py": None,
        "tests/unit/visual/test_visual_planning_contracts.py": None,
        "tests/application/test_slide_design_brief_service.py": None,
        "tests/domain/test_slide_design_brief.py": None,
    }
    for rel in files:
        path = ROOT / rel
        t = path.read_text(encoding="utf-8")
        t2 = t
        t2 = t2.replace("BriefStatus.READY_FOR_REVIEW", "ApprovalStatus.PENDING")
        t2 = t2.replace("BriefStatus.APPROVED", "ApprovalStatus.APPROVED")
        t2 = t2.replace("BriefStatus.CHANGES_PENDING", "ApprovalStatus.CHANGES_PENDING")
        t2 = t2.replace("BriefStatus.DRAFT", "ApprovalStatus.DRAFT")
        # Imports
        if "from archium.domain.slide_design_brief import" in t2 and "ApprovalStatus" not in t2.split("slide_design_brief")[0][-200:]:
            # ensure ApprovalStatus imported where BriefStatus was used
            if "ApprovalStatus" not in t2:
                t2 = t2.replace(
                    "from archium.domain.slide_design_brief import",
                    "from archium.domain.enums import ApprovalStatus\n"
                    "from archium.domain.slide_design_brief import",
                )
        # Remove BriefStatus from imports if unused
        t2 = t2.replace(", BriefStatus", "")
        t2 = t2.replace("BriefStatus, ", "")
        t2 = t2.replace("BriefStatus\n", "\n")
        # Special: BriefStatus(x) → coerce
        if "BriefStatus(" in t2:
            if "coerce_brief_approval_status" not in t2:
                t2 = t2.replace(
                    "from archium.domain.slide_design_brief import",
                    "from archium.domain.slide_design_brief import coerce_brief_approval_status,",
                )
            t2 = t2.replace("BriefStatus(", "coerce_brief_approval_status(")
        # visual_intent frozenset
        t2 = t2.replace(
            "_USABLE_BRIEF_STATUSES = frozenset(\n    {ApprovalStatus.APPROVED, ApprovalStatus.PENDING}\n)",
            "_USABLE_BRIEF_STATUSES = frozenset({ApprovalStatus.APPROVED, ApprovalStatus.PENDING})",
        )
        path.write_text(t2, encoding="utf-8")
        print("updated", rel)

    # Fix visual_nodes specially
    vn = ROOT / "archium/workflow/visual_nodes.py"
    vt = vn.read_text(encoding="utf-8")
    vt = vt.replace(
        "from archium.domain.slide_design_brief import BriefStatus, SlideDesignBrief",
        "from archium.domain.enums import ApprovalStatus\n"
        "from archium.domain.slide_design_brief import SlideDesignBrief",
    )
    vt = vt.replace(
        "usable = {BriefStatus.APPROVED, BriefStatus.READY_FOR_REVIEW}",
        "usable = {ApprovalStatus.APPROVED, ApprovalStatus.PENDING}",
    )
    vt = vt.replace(
        "usable = {ApprovalStatus.APPROVED, ApprovalStatus.PENDING}",
        "usable = {ApprovalStatus.APPROVED, ApprovalStatus.PENDING}",
    )
    # if BriefStatus still referenced
    vt = vt.replace("BriefStatus.APPROVED", "ApprovalStatus.APPROVED")
    vt = vt.replace("BriefStatus.READY_FOR_REVIEW", "ApprovalStatus.PENDING")
    vn.write_text(vt, encoding="utf-8")
    print("visual_nodes done")


if __name__ == "__main__":
    patch_slide_design_brief()
    replace_brief_status_usages()

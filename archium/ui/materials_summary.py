"""Materials-stage summary counts for the product-flow dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.asset_metadata_service import AssetMetadataService
from archium.application.fact_ledger_service import FactLedgerService
from archium.application.project_knowledge_service import ProjectKnowledgeService
from archium.ui.workspace_service import get_project_overview


@dataclass(frozen=True)
class MaterialsSummary:
    file_count: int
    fact_count: int
    asset_count: int
    gap_count: int
    pending_confirm_count: int

    @property
    def pending_issues_label(self) -> str:
        return f"{self.pending_confirm_count} 个待确认问题"


def load_materials_summary(session: Session, project_id: UUID) -> MaterialsSummary:
    overview = get_project_overview(session, project_id)
    file_count = overview.document_count if overview is not None else 0

    ledger = FactLedgerService(session).get_ledger(project_id)
    fact_count = ledger.confirmed_count + ledger.pending_count + ledger.conflict_count
    # Prefer total ledger rows when available.
    fact_rows = len(ledger.entries) + len(ledger.extra_facts)
    if fact_rows > fact_count:
        fact_count = fact_rows

    assets = AssetMetadataService(session).list_project_assets(project_id)
    knowledge = ProjectKnowledgeService(session).get_view(project_id)
    gap_count = knowledge.gap_report.gap_count if knowledge.gap_report is not None else 0
    pending_confirm = ledger.pending_count + gap_count

    return MaterialsSummary(
        file_count=file_count,
        fact_count=fact_count,
        asset_count=len(assets),
        gap_count=gap_count,
        pending_confirm_count=pending_confirm,
    )

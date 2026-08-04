"""Attach weak IdeaSeed from site photos / drawings (Topic 05 Phase M2 / APP-019).

Never enrich LLM, never generate_directions, never select/commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from archium.application.knowledge_isolation import document_purpose_from_metadata
from archium.application.unit_of_work import SessionLike, session_of
from archium.application.visual_evidence_service import document_purpose_for_asset
from archium.config.settings import Settings, get_settings
from archium.domain.architectural_asset import (
    ArchitecturalAssetRole,
    architectural_asset_from_parts,
)
from archium.domain.asset import Asset
from archium.domain.document import SourceDocument
from archium.domain.enums import DocumentPurpose, ExplorationSessionStatus
from archium.domain.exploration_session import ExplorationSession
from archium.domain.intent.idea_seed import IdeaSeed
from archium.domain.knowledge_reference import KnowledgeUsage
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    ExplorationSessionRepository,
)
from archium.logging import get_logger

logger = get_logger(__name__, operation="visual_idea_seed")

_SEED_ROLES = frozenset(
    {
        ArchitecturalAssetRole.SITE_PHOTO,
        ArchitecturalAssetRole.DRAWING,
    }
)
_VISUAL_SOURCES = frozenset({"site_photo", "sketch", "visual_upload"})


@dataclass(frozen=True)
class VisualIdeaSeedResult:
    attached: bool = False
    created_session: bool = False
    merged: bool = False
    exploration_id: UUID | None = None
    message: str = ""
    source: str = ""


def maybe_attach_visual_idea_seed(
    session: SessionLike,
    project_id: UUID,
    *,
    assets: list[Asset],
    document: SourceDocument | None = None,
    settings: Settings | None = None,
) -> VisualIdeaSeedResult:
    """Create or merge a weak IdeaSeed from evidence-grade site photos/drawings."""
    session = session_of(session)
    resolved = settings or get_settings()
    if not getattr(resolved, "visual_idea_seed_on_upload", True):
        return VisualIdeaSeedResult(message="visual idea seed disabled")
    if not assets:
        return VisualIdeaSeedResult(message="no assets")

    purpose = DocumentPurpose.PROJECT_MATERIAL
    if document is not None:
        purpose = document_purpose_from_metadata(document.metadata or {})
    elif assets[0].document_id is not None:
        doc = DocumentRepository(session).get_document(assets[0].document_id)
        purpose = document_purpose_for_asset(doc)

    eligible: list[tuple[Asset, ArchitecturalAssetRole]] = []
    for asset in assets:
        facade = architectural_asset_from_parts(asset, document_purpose=purpose)
        if facade.role not in _SEED_ROLES:
            continue
        if facade.usage != KnowledgeUsage.EVIDENCE:
            continue
        eligible.append((asset, facade.role))

    if not eligible:
        return VisualIdeaSeedResult(message="no evidence-grade site photo/drawing")

    raw_input = build_visual_seed_raw_input(eligible)
    session_source = _session_source_for_roles([role for _, role in eligible])

    explorations = ExplorationSessionRepository(session)
    latest = explorations.get_latest_for_project(project_id)
    if (
        latest is not None
        and latest.status != ExplorationSessionStatus.COMMITTED
    ):
        return _merge_into_open_session(
            session,
            latest,
            raw_input=raw_input,
            session_source=session_source,
            explorations=explorations,
        )

    from archium.exceptions import WorkflowError
    from archium.infrastructure.database.repositories import ProjectRepository

    project = ProjectRepository(session).get_by_id(project_id)
    if project is None:
        raise WorkflowError(f"Project {project_id} not found")

    seed = IdeaSeed.from_raw(raw_input, source=session_source)
    exploration = ExplorationSession(
        project_id=project_id,
        idea_text=seed.raw_input,
        idea_seed=seed,
        status=ExplorationSessionStatus.EXPLORING,
        source=session_source,
    )
    created = explorations.create(exploration)
    session.commit()
    logger.info(
        "Attached weak visual IdeaSeed for project %s (exploration=%s source=%s)",
        project_id,
        created.id,
        session_source,
    )
    return VisualIdeaSeedResult(
        attached=True,
        created_session=True,
        exploration_id=created.id,
        message="已记为探索弱种子（未推演方向、未选定）",
        source=session_source,
    )


def build_visual_seed_raw_input(
    eligible: list[tuple[Asset, ArchitecturalAssetRole]],
    *,
    max_assets: int = 4,
) -> str:
    lines: list[str] = ["【视觉证据弱种子】以下来自上传现场图/图纸，尚未形成正式设计方向。"]
    for asset, role in eligible[:max_assets]:
        label = "现场照片" if role == ArchitecturalAssetRole.SITE_PHOTO else "图纸/草图"
        caption = _caption_for_asset(asset)
        if caption:
            lines.append(f"- {label}（{asset.filename}）：{caption}")
        else:
            lines.append(f"- {label}：{asset.filename}")
    lines.append("请基于上述视觉线索形成问题意识；勿编造未给出的指标。")
    return "\n".join(lines)


def build_visual_evidence_prompt_block(
    session: SessionLike,
    project_id: UUID,
    *,
    max_lines: int = 8,
) -> str:
    """Soft prompt block for explicit direction generation (not auto-harden)."""
    session = session_of(session)
    from archium.application.visual_evidence_service import build_visual_evidence_pack

    pack = build_visual_evidence_pack(session, project_id)
    evidence_only = [a for a in pack.assets if a.usage == KnowledgeUsage.EVIDENCE]
    if not evidence_only:
        return ""
    lines = ["【项目视觉证据】（上传素材；示意/生成图未列入）"]
    lines.extend(item.to_prompt_line() for item in evidence_only[:max_lines])
    return "\n".join(lines)


def _merge_into_open_session(
    session: SessionLike,
    exploration: ExplorationSession,
    *,
    raw_input: str,
    session_source: str,
    explorations: ExplorationSessionRepository,
) -> VisualIdeaSeedResult:
    session = session_of(session)
    existing_seed = exploration.idea_seed or IdeaSeed.from_raw(
        exploration.idea_text or "（空）",
        source=exploration.source or "user",
    )
    existing_raw = (existing_seed.raw_input or exploration.idea_text or "").strip()
    # Avoid duplicate append of the same filenames
    new_lines = [
        line
        for line in raw_input.splitlines()
        if line.startswith("- ") and line not in existing_raw
    ]
    if not new_lines and "【视觉证据弱种子】" in existing_raw:
        return VisualIdeaSeedResult(
            attached=False,
            exploration_id=exploration.id,
            message="开放探索已含相同视觉线索，未重复写入",
            source=existing_seed.source,
        )

    visual_origin = (
        existing_seed.source in _VISUAL_SOURCES
        or (exploration.source or "") in _VISUAL_SOURCES
    )
    if visual_origin or not existing_raw or existing_raw == "（空）":
        merged_raw = (
            f"{existing_raw.rstrip()}\n" + "\n".join(new_lines)
            if existing_raw and "【视觉证据弱种子】" in existing_raw
            else raw_input
            if not existing_raw or existing_raw == "（空）"
            else f"{existing_raw.rstrip()}\n\n{raw_input}"
        )
        seed = IdeaSeed.from_raw(merged_raw.strip(), source=session_source)
        exploration.idea_seed = seed
        exploration.idea_text = seed.raw_input
        exploration.source = session_source
    else:
        # Preserve user-authored seed; append visual appendix only
        appendix = "\n".join(["", "【补充视觉证据】", *new_lines])
        if appendix.strip() in existing_raw:
            return VisualIdeaSeedResult(
                attached=False,
                exploration_id=exploration.id,
                message="用户想法已存在；视觉线索已记录过",
                source=existing_seed.source,
            )
        merged_raw = existing_raw.rstrip() + appendix
        keywords = list(existing_seed.keywords)
        for tag in ("视觉证据", session_source):
            if tag not in keywords:
                keywords.append(tag)
        seed = existing_seed.model_copy(
            update={
                "raw_input": merged_raw.strip(),
                "keywords": keywords[:12],
            }
        )
        exploration.idea_seed = seed
        exploration.idea_text = seed.raw_input

    exploration.touch()
    updated = explorations.update(exploration)
    session.commit()
    return VisualIdeaSeedResult(
        attached=True,
        merged=True,
        exploration_id=updated.id,
        message="已并入当前探索弱种子（未推演方向、未选定）",
        source=session_source,
    )


def _session_source_for_roles(roles: list[ArchitecturalAssetRole]) -> str:
    if any(role == ArchitecturalAssetRole.SITE_PHOTO for role in roles):
        if any(role == ArchitecturalAssetRole.DRAWING for role in roles):
            return "visual_upload"
        return "site_photo"
    return "sketch"


def _caption_for_asset(asset: Asset) -> str:
    meta = asset.metadata or {}
    for key in ("vision_caption", "caption", "ocr_text"):
        value = str(meta.get(key) or "").strip()
        if value:
            return value[:280]
    desc = (asset.description or "").strip()
    return desc[:280]

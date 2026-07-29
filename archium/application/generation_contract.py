"""Auditable input contract for presentation generation."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from archium.application.review_models import PresentationReviewContext
from archium.domain.enums import ApprovalStatus
from archium.exceptions import WorkflowError

GENERATION_CONTRACT_SCHEMA = "archium.generation-contract/v1"


def build_generation_contract(
    context: PresentationReviewContext,
    *,
    actor_id: str | None,
) -> dict[str, Any]:
    """Freeze the approved human inputs used by a generation run."""
    if context.brief is None or context.storyline is None or context.outline is None:
        raise WorkflowError("批准输入不完整：需要 Brief、Storyline 和 Outline。")
    artifacts = {
        "brief": _artifact_ref(context.brief),
        "storyline": _artifact_ref(context.storyline),
        "outline": _artifact_ref(context.outline),
    }
    design_briefs = [
        _stable_dump(item)
        for item in sorted(
            context.outline.page_design_briefs,
            key=lambda item: item.page_order,
        )
    ]
    payload = {
        "schema": GENERATION_CONTRACT_SCHEMA,
        "presentation_id": str(context.presentation.id),
        "actor_id": actor_id,
        "created_at": datetime.now(UTC).isoformat(),
        "artifacts": artifacts,
        "page_design_brief_count": len(design_briefs),
        "page_design_briefs_sha256": _digest(design_briefs),
    }
    payload["contract_sha256"] = _digest(
        {key: value for key, value in payload.items() if key != "created_at"}
    )
    return payload


def validate_generation_contract(
    contract: dict[str, Any],
    context: PresentationReviewContext,
) -> None:
    """Fail closed when an approved input changed after the run was prepared."""
    current = build_generation_contract(context, actor_id=contract.get("actor_id"))
    expected = contract.get("contract_sha256")
    if not expected or current["contract_sha256"] != expected:
        raise WorkflowError(
            "生成契约已失效：Brief、Storyline、Outline 或页面设计摘要在任务创建后发生了变化。"
            "请返回大纲阶段复核并重新发起生成。"
        )


def _artifact_ref(artifact: Any) -> dict[str, Any]:
    if artifact.approval_status != ApprovalStatus.APPROVED:
        raise WorkflowError("生成契约只能冻结已批准的输入。")
    return {
        "id": str(artifact.id),
        "version": int(artifact.version),
        "approval_status": artifact.approval_status.value,
        "content_sha256": _digest(_stable_dump(artifact)),
    }


def _stable_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude={"created_at", "updated_at"})
    return value


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

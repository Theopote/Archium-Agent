"""Slide snapshot comparison utilities."""

from __future__ import annotations

import difflib
from uuid import UUID

from archium.domain.enums import RevisionSource, SlideStatus, SlideType
from archium.domain.slide import SlideSpec
from archium.domain.slide_history import SlideDiffResult, SlideFieldChange

_TRACKED_FIELDS: tuple[tuple[str, str], ...] = (
    ("title", "标题"),
    ("message", "核心观点"),
    ("chapter_id", "章节 ID"),
    ("order", "顺序"),
    ("slide_type", "页面类型"),
    ("layout_id", "版式"),
    ("speaker_notes", "演讲备注"),
    ("status", "状态"),
    ("key_points", "要点"),
)


def slide_to_snapshot(slide: SlideSpec) -> dict[str, object]:
    return {
        "id": str(slide.id),
        "lineage_id": str(slide.lineage_id),
        "logical_key": slide.logical_key,
        "presentation_id": str(slide.presentation_id),
        "chapter_id": slide.chapter_id,
        "order": slide.order,
        "title": slide.title,
        "message": slide.message,
        "slide_type": slide.slide_type.value,
        "layout_id": slide.layout_id,
        "key_points": list(slide.key_points),
        "speaker_notes": slide.speaker_notes,
        "status": slide.status.value,
        "version": slide.version,
    }


def snapshot_content_fingerprint(snapshot: dict[str, object]) -> tuple[object, ...]:
    """Compare slide content snapshots ignoring version/id churn."""
    key_points = snapshot.get("key_points")
    normalized_key_points: tuple[object, ...]
    normalized_key_points = tuple(key_points) if isinstance(key_points, list) else ()
    return (
        snapshot.get("title"),
        snapshot.get("message"),
        normalized_key_points,
        snapshot.get("speaker_notes"),
        snapshot.get("slide_type"),
        snapshot.get("status"),
    )


def snapshot_to_slide(snapshot: dict[str, object], slide: SlideSpec) -> SlideSpec:
    """Rebuild a SlideSpec from a stored snapshot, preserving identity fields."""
    layout_id_raw = snapshot.get("layout_id")
    layout_id = str(layout_id_raw) if layout_id_raw is not None else slide.layout_id
    key_points_raw = snapshot.get("key_points")
    key_points = [str(item) for item in key_points_raw] if isinstance(key_points_raw, list) else []
    speaker_notes_raw = snapshot.get("speaker_notes")
    speaker_notes = (
        str(speaker_notes_raw) if speaker_notes_raw is not None else slide.speaker_notes
    )
    order_raw = snapshot.get("order", slide.order)
    order = int(order_raw) if isinstance(order_raw, int) else slide.order
    return slide.model_copy(
        update={
            "title": str(snapshot.get("title") or slide.title),
            "message": str(snapshot.get("message") or slide.message),
            "chapter_id": str(snapshot.get("chapter_id") or slide.chapter_id),
            "order": order,
            "slide_type": SlideType(str(snapshot.get("slide_type", slide.slide_type.value))),
            "layout_id": layout_id,
            "key_points": key_points,
            "speaker_notes": speaker_notes,
            "status": SlideStatus(str(snapshot.get("status", slide.status.value))),
            "version": slide.version + 1,
        }
    )


def snapshot_label(snapshot: dict[str, object], *, prefix: str) -> str:
    revision_number = snapshot.get("version")
    title = snapshot.get("title", "")
    if revision_number is not None:
        return f"{prefix} · v{revision_number} · {title}"
    return f"{prefix} · {title}"


def _format_value(field: str, value: object) -> str:
    if value is None:
        return ""
    if field == "key_points" and isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def _unified_diff(before: str, after: str, *, field: str) -> str | None:
    if before == after:
        return None
    if field not in {"message", "title", "speaker_notes", "key_points"}:
        return None
    lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile="before",
        tofile="after",
        lineterm="",
    )
    rendered = "\n".join(lines)
    return rendered or None


def diff_snapshots(
    before: dict[str, object],
    after: dict[str, object],
    *,
    slide_id: UUID | None,
    presentation_id: UUID,
    before_label: str,
    after_label: str,
) -> SlideDiffResult:
    """Compare two slide snapshots and return field-level differences."""
    changes: list[SlideFieldChange] = []
    for field, label in _TRACKED_FIELDS:
        before_value = _format_value(field, before.get(field))
        after_value = _format_value(field, after.get(field))
        if before_value == after_value:
            continue
        changes.append(
            SlideFieldChange(
                field=field,
                label=label,
                before=before_value,
                after=after_value,
                unified_diff=_unified_diff(before_value, after_value, field=field),
            )
        )
    return SlideDiffResult(
        slide_id=slide_id,
        presentation_id=presentation_id,
        before_label=before_label,
        after_label=after_label,
        changes=changes,
    )


def change_source_label(source: RevisionSource) -> str:
    labels = {
        RevisionSource.GENERATED: "首次生成",
        RevisionSource.MANUAL_EDIT: "人工编辑",
        RevisionSource.REGENERATION: "重新生成前归档",
        RevisionSource.AUTO_REPAIR: "自动修复",
        RevisionSource.CLARIFICATION: "澄清修订",
        RevisionSource.APPROVAL: "审批",
        RevisionSource.IMPORT: "导入",
    }
    return labels.get(source, source.value)

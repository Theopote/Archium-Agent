"""Architecture case identity helpers — ``case:{id}`` refs and bare ids."""

from __future__ import annotations

import re

_CASE_PREFIX = "case:"
_CASE_ID_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,79}$")


def normalize_case_id(raw: str | None) -> str | None:
    """Return bare case id (e.g. ``ningbo_museum``) or None if empty/invalid."""
    text = (raw or "").strip()
    if not text:
        return None
    if text.lower().startswith(_CASE_PREFIX):
        text = text[len(_CASE_PREFIX) :].strip()
    if not _CASE_ID_RE.fullmatch(text):
        return None
    return text


def normalize_precedent_ref(raw: str | None) -> str | None:
    """Return canonical ``case:{id}`` or None."""
    case_id = normalize_case_id(raw)
    if case_id is None:
        return None
    return f"{_CASE_PREFIX}{case_id}"


def case_id_from_ref(ref: str | None) -> str | None:
    """Extract bare id from ``case:{id}`` or bare id input."""
    return normalize_case_id(ref)


def normalize_case_id_list(values: list[str] | None, *, max_items: int = 8) -> list[str]:
    """Dedupe bare case ids preserving order."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        case_id = normalize_case_id(raw)
        if case_id is None or case_id in seen:
            continue
        seen.add(case_id)
        out.append(case_id)
        if len(out) >= max_items:
            break
    return out

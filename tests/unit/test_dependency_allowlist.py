"""Guards for docs/security dependency allowlist shape."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_ALLOWLIST = _ROOT / "docs" / "security" / "dependency-allowlist.json"


def test_dependency_allowlist_entries_have_required_fields() -> None:
    payload = json.loads(_ALLOWLIST.read_text(encoding="utf-8"))
    assert payload.get("version") == 1
    today = date.today()
    max_expiry = today + timedelta(days=90)
    for entry in payload.get("entries") or []:
        assert entry.get("id") or entry.get("aliases"), entry
        assert str(entry.get("risk_owner") or "").strip(), entry
        assert str(entry.get("rationale") or "").strip(), entry
        expires = date.fromisoformat(str(entry["expires_on"]))
        assert expires >= today, f"expired allowlist entry: {entry}"
        assert expires <= max_expiry, f"expires_on beyond 90 days: {entry}"
        assert str(entry.get("ticket") or "").strip(), entry

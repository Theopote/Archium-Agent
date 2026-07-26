"""Inspect Case 001 page claims after a render."""
from __future__ import annotations

import json
from pathlib import Path

p = Path("scripts/showcase/case_001_hospital/outputs/page_claims.json")
data = json.loads(p.read_text(encoding="utf-8"))
for page in data["pages"]:
    vc = page.get("visual_concept")
    meta = vc["visual_metaphor"] if vc else None
    fams = page.get("preferred_layout_families") or []
    print(
        f"{page['order']:02d} {page['title']}: "
        f"emotion={page['emotion']} fam={fams[:2]} metaphor={meta}"
    )
    print(f"   claim: {page['claim'][:80]}")

"""Guard: infrastructure must not import relocated application helpers."""

from __future__ import annotations

import re
from pathlib import Path

# Modules moved in layering phase-one — infrastructure must use domain/infra paths.
_FORBIDDEN_HELPERS = re.compile(
    r"^\s*(?:from|import)\s+archium\.application\.(?:"
    r"visual\.(?:"
    r"icon_stroke_resolve|text_style_resolve|icon_usage|"
    r"placeholder_binding_normalize|visual_grammar_assets|"
    r"drawing_inference_service|svg_icon_recolor|asset_path_resolver|"
    r"induction_screenshot_embedding|scene_fonts|"
    r"vision\.lora_pack_service"
    r")|"
    r"visual_qa_calibration"
    r")\b"
)


def test_infrastructure_does_not_import_relocated_helpers() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "infrastructure"
    package_root = root.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _FORBIDDEN_HELPERS.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], (
        "infrastructure must not import relocated application helpers "
        "(use domain/visual or infrastructure.*):\n" + "\n".join(hits)
    )

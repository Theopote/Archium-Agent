"""Compare Case 001 Style Presets (technical vs minimal) — measurable contrast."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from archium.application.visual.showcase_case_001 import (  # noqa: E402
    build_case_001_render_bundle,
    case_001_design_system,
)


def _fingerprint(style_preset_id: str) -> dict:
    design = case_001_design_system(style_preset_id)
    bundle = build_case_001_render_bundle(style_preset_id=style_preset_id)
    from archium.domain.visual.style import get_style_preset

    preset = get_style_preset(style_preset_id)
    return {
        "style_preset_id": style_preset_id,
        "margin_left": design.page.margin_left,
        "min_hero_area_ratio": design.thresholds.min_hero_area_ratio,
        "min_whitespace_ratio": design.thresholds.min_whitespace_ratio,
        "narrative_logic": preset.presentation_personality.logic.value,
        "emotion": preset.presentation_personality.emotion.value,
        "image_role": preset.presentation_personality.image_role.value,
        "max_key_points": preset.content_policy.max_key_points,
        "max_message_chars": preset.content_policy.max_message_chars,
        "page_direction_hits": sum(
            1 for intent in bundle.intents if intent.page_direction is not None
        ),
        "situation_rules": list(
            dict.fromkeys(
                intent.page_direction.situation_rule_id
                for intent in bundle.intents
                if intent.page_direction and intent.page_direction.situation_rule_id
            )
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--left",
        default="architecture_technical",
        help="First preset id",
    )
    parser.add_argument(
        "--right",
        default="architecture_minimal",
        help="Second preset id",
    )
    args = parser.parse_args(argv)
    left = _fingerprint(args.left)
    right = _fingerprint(args.right)
    contrasted = (
        left["margin_left"] != right["margin_left"]
        or left["min_hero_area_ratio"] != right["min_hero_area_ratio"]
        or left["min_whitespace_ratio"] != right["min_whitespace_ratio"]
    )
    payload = {"left": left, "right": right, "measurable_contrast": contrasted}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if contrasted else 1


if __name__ == "__main__":
    raise SystemExit(main())

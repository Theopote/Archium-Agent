#!/usr/bin/env python3
"""Extended engineer rehearsal: move → set_text → undo → export verify.

Complements browser HITL; does not close UI-006.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from uuid import UUID

from archium.application.visual.scene_undo_service import SceneUndoService
from archium.application.visual.studio_scene_edit_service import StudioSceneEditService
from archium.config.settings import get_settings
from archium.domain.visual.render_scene import TextNode, ImageNode
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.session import get_session
from archium.infrastructure.database.visual_repositories import RenderSceneRepository
from archium.ui.studio_service import export_presentation_from_studio, undo_slide_visual_edit

MARKER = "剧本E浏览器预演-20260803"
# Latest seed from session-meta
PRESENTATION_ID = UUID("fd7cde92-3f53-4902-a001-06c67f61a8c2")
OUT = Path(__file__).resolve().parent / "browser-rehearsal-service.json"


def _pptx_has_text(path: Path, needle: str) -> bool:
    with zipfile.ZipFile(path) as zf:
        blobs = [
            zf.read(name).decode("utf-8", errors="ignore")
            for name in zf.namelist()
            if name.startswith("ppt/slides/") and name.endswith(".xml")
        ]
        return needle in "".join(blobs)


def main() -> int:
    settings = get_settings()
    report: dict[str, object] = {"presentation_id": str(PRESENTATION_ID), "steps": {}}

    with get_session() as session:
        slides = PresentationRepository(session).list_slides(PRESENTATION_ID)
        slide = sorted(slides, key=lambda s: s.order)[0]
        scenes = RenderSceneRepository(session)
        scene = scenes.list_by_slide(slide.id)[0]
        editor = StudioSceneEditService(session, settings=settings)

        # Prefer image for geometry move; fall back to title text
        image_nodes = [n for n in scene.nodes if isinstance(n, ImageNode)]
        text_nodes = [n for n in scene.nodes if isinstance(n, TextNode) and (n.text or "").strip()]
        move_target = image_nodes[0] if image_nodes else text_nodes[0]
        text_target = text_nodes[0]

        before_x, before_y = float(move_target.x), float(move_target.y)
        moved = editor.move_layout_element(
            slide.id,
            element_id=move_target.id,
            x=before_x + 0.4,
            y=before_y + 0.3,
        )
        after = scenes.list_by_slide(slide.id)[0].node_by_id(move_target.id)
        report["steps"]["E2_move"] = {
            "ok": abs(float(after.x) - (before_x + 0.4)) < 1e-6,
            "node_id": move_target.id,
            "before": [before_x, before_y],
            "after": [float(after.x), float(after.y)],
            "actions": [a.action_type for a in moved.applied_actions],
        }

        original_text = text_target.text
        editor.set_layout_element_text_runs(
            slide.id,
            element_id=text_target.id,
            runs=[{"text": MARKER}],
        )
        live_text = scenes.list_by_slide(slide.id)[0].node_by_id(text_target.id)
        assert isinstance(live_text, TextNode)
        report["steps"]["E3_set_text"] = {
            "ok": MARKER in (live_text.text or ""),
            "node_id": text_target.id,
        }

        undo_count = SceneUndoService(session, settings=settings).count_undo_steps(slide)
        undo_slide_visual_edit(session, slide.id)  # undo text
        after_text = scenes.list_by_slide(slide.id)[0].node_by_id(text_target.id)
        assert isinstance(after_text, TextNode)
        text_restored = (after_text.text or "") == original_text
        # Keep geometry move for export visibility check: re-apply marker then export
        editor.set_layout_element_text_runs(
            slide.id,
            element_id=text_target.id,
            runs=[{"text": MARKER}],
        )
        export = export_presentation_from_studio(session, PRESENTATION_ID, settings=settings)
        pptx = Path(export.editable_pptx_path) if export.editable_pptx_path else None
        pptx_ok = bool(pptx and pptx.is_file() and _pptx_has_text(pptx, MARKER))
        if pptx and pptx.is_file():
            dest = Path(__file__).resolve().parent / "browser-rehearsal-export.pptx"
            dest.write_bytes(pptx.read_bytes())
            report["pptx_evidence"] = str(dest)

        # Restore clean state for human operator
        undo_slide_visual_edit(session, slide.id)  # undo marker
        undo_slide_visual_edit(session, slide.id)  # undo move if still present
        final = scenes.list_by_slide(slide.id)[0]
        final_move = final.node_by_id(move_target.id)
        final_text = final.node_by_id(text_target.id)
        assert isinstance(final_text, TextNode)

        report["steps"]["E4_undo"] = {
            "undo_steps_after_two_edits": undo_count,
            "text_restored_after_first_undo": text_restored,
            "final_text_clean": (final_text.text or "") == original_text,
            "final_geometry_near_original": abs(float(final_move.x) - before_x) < 1e-6,
        }
        report["steps"]["E5_export"] = {
            "ok": pptx_ok,
            "path": str(pptx) if pptx else None,
            "warnings": list(export.warnings),
        }
        report["ok"] = bool(
            report["steps"]["E2_move"]["ok"]
            and report["steps"]["E3_set_text"]["ok"]
            and text_restored
            and pptx_ok
            and report["steps"]["E4_undo"]["final_text_clean"]
        )
        report["slide_id"] = str(slide.id)
        report["deck_page_count"] = len(slides)

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

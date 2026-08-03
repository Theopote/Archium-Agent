#!/usr/bin/env python3
"""Browser-assisted Playbook E rehearsal: E2 move + E3 text + E4 undo + E5 export.

Operator is engineering dry-run (cannot close UI-006).
"""

from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path
from uuid import UUID

from archium.application.visual.scene_undo_service import SceneUndoService
from archium.application.visual.studio_scene_edit_service import StudioSceneEditService
from archium.config.settings import get_settings
from archium.domain.visual.render_scene import TextNode
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.session import get_session
from archium.infrastructure.database.visual_repositories import RenderSceneRepository
from archium.ui.studio_service import export_presentation_from_studio, undo_slide_visual_edit

PRESENTATION_ID = UUID("fd7cde92-3f53-4902-a001-06c67f61a8c2")
MARKER = "预演改题-PlaybookE-20260803"
OUT_DIR = Path(__file__).resolve().parent
OUT = OUT_DIR / "rehearsal-e2-e5-result.json"


def _pptx_has(path: Path, needle: str) -> bool:
    with zipfile.ZipFile(path) as zf:
        return needle in "".join(
            zf.read(n).decode("utf-8", errors="ignore")
            for n in zf.namelist()
            if n.startswith("ppt/slides/") and n.endswith(".xml")
        )


def main() -> int:
    t0 = time.perf_counter()
    settings = get_settings()
    report: dict[str, object] = {
        "mode": "engineering_browser_assisted_rehearsal",
        "closes_ui_006": False,
        "presentation_id": str(PRESENTATION_ID),
        "steps": {},
    }

    with get_session() as session:
        slides = sorted(
            PresentationRepository(session).list_slides(PRESENTATION_ID),
            key=lambda s: s.order,
        )
        # E0 pick: P6 hero often visually weakest in benchmark set (index 5)
        slide = slides[5]
        report["e0_worst_slide"] = {
            "slide_id": str(slide.id),
            "order": slide.order,
            "title": slide.title,
            "reason": "工程预演选定 P6 hero 页作为改稿对象（封面类占位图常见问题）。",
        }

        scenes = RenderSceneRepository(session).list_by_slide(slide.id)
        scene = scenes[0]
        text_nodes = [n for n in scene.nodes if isinstance(n, TextNode) and (n.text or "").strip()]
        target = text_nodes[0]
        original_text = target.text
        original_x = float(target.x)
        original_y = float(target.y)

        editor = StudioSceneEditService(session, settings=settings)

        # E2 move
        moved = editor.move_layout_element(
            slide.id,
            element_id=target.id,
            x=original_x + 0.4,
            y=original_y + 0.2,
        )
        live = RenderSceneRepository(session).list_by_slide(slide.id)[0]
        live_node = live.node_by_id(target.id)
        assert live_node is not None
        report["steps"]["E2_move"] = {
            "pass": abs(float(live_node.x) - (original_x + 0.4)) < 1e-6,
            "node_id": target.id,
            "before": {"x": original_x, "y": original_y},
            "after": {"x": float(live_node.x), "y": float(live_node.y)},
            "message": moved.message,
        }

        # E3 set text
        edited = editor.set_layout_element_text_runs(
            slide.id,
            element_id=target.id,
            runs=[{"text": MARKER}],
        )
        live = RenderSceneRepository(session).list_by_slide(slide.id)[0]
        live_node = live.node_by_id(target.id)
        assert isinstance(live_node, TextNode)
        report["steps"]["E3_set_text"] = {
            "pass": MARKER in (live_node.text or ""),
            "message": edited.message,
            "text": live_node.text,
        }

        # E5 export BEFORE undo (keep edit in PPTX)
        export = export_presentation_from_studio(session, PRESENTATION_ID, settings=settings)
        pptx_path = Path(export.editable_pptx_path) if export.editable_pptx_path else None
        pptx_ok = bool(pptx_path and pptx_path.is_file() and _pptx_has(pptx_path, MARKER))
        if pptx_path and pptx_path.is_file():
            evidence = OUT_DIR / "E5-rehearsal-export.pptx"
            evidence.write_bytes(pptx_path.read_bytes())
        else:
            evidence = None
        report["steps"]["E5_export"] = {
            "pass": pptx_ok,
            "path": str(pptx_path) if pptx_path else None,
            "evidence": str(evidence) if evidence else None,
            "warnings": list(export.warnings),
        }

        # E4 undo (after export evidence captured)
        undo_before = SceneUndoService(session, settings=settings).count_undo_steps(slide)
        undo_slide_visual_edit(session, slide.id)
        live = RenderSceneRepository(session).list_by_slide(slide.id)[0]
        live_node = live.node_by_id(target.id)
        assert isinstance(live_node, TextNode)
        # One undo should revert latest text edit; geometry may remain if separate revision
        report["steps"]["E4_undo"] = {
            "undo_steps_before": undo_before,
            "pass": undo_before >= 1 and (live_node.text or "") != MARKER,
            "after_text": (live_node.text or "")[:80],
            "note": "Undid after export so E5 evidence retains marker.",
        }

    report["elapsed_seconds"] = round(time.perf_counter() - t0, 2)
    report["overall_service_pass"] = all(
        bool(step.get("pass")) for step in report["steps"].values()  # type: ignore[union-attr]
    )
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["overall_service_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

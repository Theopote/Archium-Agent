#!/usr/bin/env python3
"""Engineer dry-run for Playbook E prep: set_text → export → verify → undo.

Does NOT close UI-006. Surfaces the 2026-07-27 e_blocker (edit missing from PPTX).
"""

from __future__ import annotations

import json
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

MARKER = "剧本E工程预演-20260803"
PRESENTATION_ID = UUID("fd7cde92-3f53-4902-a001-06c67f61a8c2")
OUT = Path(__file__).resolve().parent / "dry-run-result.json"


def _pptx_has_text(path: Path, needle: str) -> bool:
    with zipfile.ZipFile(path) as zf:
        blobs: list[str] = []
        for name in zf.namelist():
            if name.startswith("ppt/slides/") and name.endswith(".xml"):
                blobs.append(zf.read(name).decode("utf-8", errors="ignore"))
        return needle in "".join(blobs)


def main() -> int:
    settings = get_settings()
    report: dict[str, object] = {
        "presentation_id": str(PRESENTATION_ID),
        "marker": MARKER,
        "steps": {},
    }

    with get_session() as session:
        presentations = PresentationRepository(session)
        slides = presentations.list_slides(PRESENTATION_ID)
        report["deck_page_count"] = len(slides)
        if len(slides) < 3:
            report["ok"] = False
            report["error"] = f"expected >=3 slides, got {len(slides)}"
            OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1

        slide = sorted(slides, key=lambda s: s.order)[0]
        report["slide_id"] = str(slide.id)
        scenes = RenderSceneRepository(session)
        scene_list = scenes.list_by_slide(slide.id)
        scene = scene_list[0] if scene_list else None
        if scene is None:
            report["ok"] = False
            report["error"] = "first slide has no RenderScene"
            OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1

        text_nodes = [n for n in scene.nodes if isinstance(n, TextNode) and (n.text or "").strip()]
        if not text_nodes:
            report["ok"] = False
            report["error"] = "no TextNode with content on first slide"
            OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1

        target = text_nodes[0]
        original = target.text
        report["target_node_id"] = target.id
        report["original_text"] = original[:80]

        editor = StudioSceneEditService(session, settings=settings)
        edit = editor.set_layout_element_text_runs(
            slide.id,
            element_id=target.id,
            runs=[{"text": MARKER}],
        )
        report["steps"]["set_text"] = {
            "ok": True,
            "message": edit.message,
            "actions": [a.action_type for a in edit.applied_actions],
        }

        live_list = scenes.list_by_slide(slide.id)
        live = live_list[0] if live_list else None
        assert live is not None
        live_node = live.node_by_id(target.id)
        assert isinstance(live_node, TextNode)
        scene_has_marker = MARKER in (live_node.text or "")
        report["steps"]["scene_contains_marker"] = scene_has_marker

        export = export_presentation_from_studio(session, PRESENTATION_ID, settings=settings)
        pptx_path = export.editable_pptx_path
        report["steps"]["export"] = {
            "ok": pptx_path is not None and Path(pptx_path).is_file(),
            "path": str(pptx_path) if pptx_path else None,
            "warnings": list(export.warnings),
        }

        pptx_has_marker = False
        if pptx_path and Path(pptx_path).is_file():
            pptx_has_marker = _pptx_has_text(Path(pptx_path), MARKER)
            # Keep a copy under evidence for facilitator
            dest = Path(__file__).resolve().parent / "dry-run-export.pptx"
            dest.write_bytes(Path(pptx_path).read_bytes())
            report["steps"]["export"]["evidence_copy"] = str(dest)
        report["steps"]["pptx_contains_marker"] = pptx_has_marker

        undo_svc = SceneUndoService(session, settings=settings)
        before_steps = undo_svc.count_undo_steps(slide)
        undo_slide_visual_edit(session, slide.id)
        after_list = scenes.list_by_slide(slide.id)
        after_live = after_list[0] if after_list else None
        assert after_live is not None
        after_node = after_live.node_by_id(target.id)
        assert isinstance(after_node, TextNode)
        restored = (after_node.text or "") == original
        report["steps"]["undo"] = {
            "undo_steps_before": before_steps,
            "restored_original_text": restored,
            "after_text": (after_node.text or "")[:80],
        }

        ok = bool(
            scene_has_marker
            and report["steps"]["export"]["ok"]
            and pptx_has_marker
            and restored
        )
        report["ok"] = ok
        if not pptx_has_marker:
            report["blocker_tag"] = "e_blocker"
            report["blocker"] = (
                "Scene has marker after set_text but exported PPTX does not — "
                "same class as 2026-07-27-playbook-e-1 E5 failure."
            )

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

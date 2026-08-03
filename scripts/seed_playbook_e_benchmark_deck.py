#!/usr/bin/env python3
"""Seed a Studio-ready ~20-page deck from architectural_slides benchmark cases.

Imports case_001..case_N scene.json into the local DB so Playbook E can open a
non-toy deck in Studio. Benchmark assets are copied into project storage and
``benchmark://`` URIs are rewritten to ``storage://`` for export/Studio.

Example::

    python scripts/seed_playbook_e_benchmark_deck.py
    python scripts/seed_playbook_e_benchmark_deck.py --count 20 --session 2026-07-28-playbook-e-2
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from uuid import UUID, uuid4

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_BENCHMARK_ROOT = _PROJECT_ROOT / "tests" / "benchmark" / "architectural_slides"
_SESSIONS_ROOT = _PROJECT_ROOT / "docs" / "rehearsal" / "sessions"


def _rewrite_benchmark_uri(
    uri: str,
    *,
    project_id: UUID,
    case_id: str,
    dest_dir: Path,
    case_dir: Path,
) -> str:
    """Copy benchmark asset into project storage; return storage:// URI."""
    text = (uri or "").strip()
    if not text.startswith("benchmark://"):
        return text
    # benchmark://case_xxx/assets/file.png
    remainder = text.removeprefix("benchmark://")
    parts = remainder.replace("\\", "/").split("/", 1)
    if len(parts) != 2:
        return text
    rel = parts[1]
    src = case_dir / Path(*[p for p in rel.split("/") if p])
    if not src.is_file():
        # Fall back to benchmark root layout
        src = _BENCHMARK_ROOT / case_id / Path(*[p for p in rel.split("/") if p])
    if not src.is_file():
        print(f"  warn: missing asset {text}", file=sys.stderr)
        return text
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dest)
    rel_storage = f"assets/{case_id}/{src.name}"
    return f"storage://projects/{project_id}/{rel_storage}"


def _plan_from_scene(scene, *, slide_id: UUID, design_system_id: UUID) -> object:
    from archium.application.visual.studio_scene_edit_service import (
        _layout_element_from_scene_node,
        sync_layout_geometry_from_scene,
    )
    from archium.domain.visual.enums import LayoutFamily
    from archium.domain.visual.layout import LayoutPlan

    elements = []
    reading: list[str] = []
    for node in scene.nodes:
        if not getattr(node, "visible", True):
            continue
        layout_id = (node.source_layout_element_id or node.id).strip()
        if not layout_id or layout_id in reading:
            continue
        elements.append(_layout_element_from_scene_node(node, layout_id))
        reading.append(layout_id)

    family = LayoutFamily.HERO
    # Prefer family hint from case notes if present on scene theme — default hero.
    plan = LayoutPlan(
        slide_id=slide_id,
        layout_family=family,
        layout_variant="benchmark_import",
        page_width=scene.page_width,
        page_height=scene.page_height,
        hero_element_id=reading[0] if reading else None,
        reading_order=reading,
        whitespace_ratio=0.3,
        elements=elements,
        design_system_id=design_system_id,
        visual_intent_id=uuid4(),
    )
    return sync_layout_geometry_from_scene(scene, plan)


def seed_deck(*, count: int, project_name: str) -> dict[str, object]:
    import archium.infrastructure.database.models  # noqa: F401
    from archium.application.artifact_policy_service import save_render_scene
    from archium.application.visual.scene_history_service import SceneHistoryService
    from archium.config.settings import get_settings
    from archium.domain.document import SourceDocument
    from archium.domain.enums import (
        ApprovalStatus,
        DocumentType,
        ProcessingStatus,
        RevisionSource,
        SlideType,
    )
    from archium.domain.presentation import Presentation, PresentationBrief, Storyline
    from archium.domain.project import Project
    from archium.domain.slide import SlideSpec
    from archium.domain.visual.defaults import default_presentation_design_system
    from archium.domain.visual.render_scene import RenderScene
    from archium.infrastructure.database.repositories import (
        DocumentRepository,
        PresentationRepository,
        ProjectRepository,
    )
    from archium.infrastructure.database.session import get_session
    from archium.infrastructure.database.visual_repositories import (
        DesignSystemRepository,
        LayoutPlanRepository,
        RenderSceneRepository,
    )
    from tests.benchmark.architectural_slides.case_registry import BENCHMARK_CASE_IDS

    case_ids = list(BENCHMARK_CASE_IDS[:count])
    if len(case_ids) < count:
        raise SystemExit(f"Only {len(BENCHMARK_CASE_IDS)} cases available; asked for {count}")

    settings = get_settings()
    storage_root = settings.project_storage_path

    with get_session() as session:
        project = ProjectRepository(session).create(
            Project(name=project_name, description="Playbook E HITL — architectural_slides import")
        )
        # Minimal materials so 交付 formal PPTX gate is not blocked by concept-draft.
        materials_dir = storage_root / str(project.id) / "materials"
        materials_dir.mkdir(parents=True, exist_ok=True)
        stub = materials_dir / "playbook-e-materials-stub.pdf"
        if not stub.exists():
            stub.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
        DocumentRepository(session).create_document(
            SourceDocument(
                project_id=project.id,
                filename=stub.name,
                original_path=str(stub.resolve()),
                stored_path=str(stub.resolve()),
                file_type=DocumentType.PDF,
                file_hash="b" * 64,
                size_bytes=stub.stat().st_size,
                processing_status=ProcessingStatus.COMPLETED,
            )
        )
        presentations = PresentationRepository(session)
        presentation = presentations.create_presentation(
            Presentation(
                project_id=project.id,
                title=f"{project_name} · {count} 页",
            )
        )
        brief = presentations.save_brief(
            PresentationBrief(
                project_id=project.id,
                presentation_id=presentation.id,
                title=presentation.title,
                audience="甲方 / 内部评审",
                purpose="Playbook E Studio 修改闭环验收",
                core_message="用真实建筑汇报页验证选中、改图、改字、提案、Undo、导出。",
                approval_status=ApprovalStatus.APPROVED,
            )
        )
        storyline = presentations.save_storyline(
            Storyline(
                presentation_id=presentation.id,
                thesis="Benchmark 导入页可作为 Studio HITL 验收载体。",
                approval_status=ApprovalStatus.APPROVED,
            )
        )
        presentation.current_brief_id = brief.id
        presentation.current_storyline_id = storyline.id
        presentations.update_presentation(presentation)

        design = DesignSystemRepository(session).save(default_presentation_design_system())
        asset_base = storage_root / str(project.id) / "assets"

        imported: list[dict[str, str]] = []
        for order, case_id in enumerate(case_ids):
            case_dir = _BENCHMARK_ROOT / case_id
            scene_path = case_dir / "scene.json"
            slide_path = case_dir / "slide_spec.json"
            if not scene_path.is_file():
                print(f"skip {case_id}: no scene.json", file=sys.stderr)
                continue

            slide_meta = {}
            if slide_path.is_file():
                slide_meta = json.loads(slide_path.read_text(encoding="utf-8"))

            raw = json.loads(scene_path.read_text(encoding="utf-8"))
            # Drop identity fields; rebind below
            for key in ("id", "created_at", "updated_at", "version"):
                raw.pop(key, None)

            slide = presentations.save_slide(
                SlideSpec(
                    presentation_id=presentation.id,
                    chapter_id=str(slide_meta.get("chapter_id") or case_id),
                    order=order,
                    title=str(slide_meta.get("title") or case_id),
                    message=str(slide_meta.get("message") or f"Benchmark {case_id}"),
                    slide_type=SlideType.CONTENT,
                    key_points=list(slide_meta.get("key_points") or []),
                )
            )

            # Rewrite asset URIs before validate
            case_asset_dir = asset_base / case_id
            nodes = raw.get("nodes") or []
            for node in nodes:
                for field in ("storage_uri", "preview_storage_uri"):
                    if field in node and node[field]:
                        node[field] = _rewrite_benchmark_uri(
                            str(node[field]),
                            project_id=project.id,
                            case_id=case_id,
                            dest_dir=case_asset_dir,
                            case_dir=case_dir,
                        )
                # Drop absolute resolved_path if present
                node.pop("resolved_path", None)
                node.pop("preview_resolved_path", None)
                node.pop("asset_path", None)

            bg = raw.get("background") or {}
            if bg.get("image_asset_path"):
                bg["image_asset_path"] = _rewrite_benchmark_uri(
                    str(bg["image_asset_path"]),
                    project_id=project.id,
                    case_id=case_id,
                    dest_dir=case_asset_dir,
                    case_dir=case_dir,
                )

            scene = RenderScene.model_validate(
                {
                    **raw,
                    "id": str(uuid4()),
                    "slide_id": str(slide.id),
                    "presentation_id": str(presentation.id),
                    "layout_plan_id": str(uuid4()),  # temporary; replaced after plan save
                    "design_system_id": str(design.id),
                }
            )

            plan = _plan_from_scene(scene, slide_id=slide.id, design_system_id=design.id)
            saved_plan = LayoutPlanRepository(session).save(plan)
            slide.layout_plan_id = saved_plan.id
            presentations.save_slide(slide)

            scene = scene.model_copy(
                update={
                    "layout_plan_id": saved_plan.id,
                    "id": uuid4(),
                }
            )
            saved_scene = save_render_scene(RenderSceneRepository(session), scene)
            # Baseline revision so the first Studio edit has a parent and Undo works.
            SceneHistoryService(session).record_scene(
                slide=slide,
                scene=saved_scene,
                change_source=RevisionSource.IMPORT,
                scene_revision_source="import_recovery",
                parent_revision_id=None,
                note="playbook-e benchmark seed baseline",
                summary="benchmark import baseline",
                qa_status="imported",
            )
            imported.append(
                {
                    "case_id": case_id,
                    "slide_id": str(slide.id),
                    "title": slide.title,
                    "order": str(order),
                }
            )
            print(f"  [{order:02d}] {case_id} → {slide.title}")

        session.commit()
        return {
            "project_id": str(project.id),
            "project_name": project.name,
            "presentation_id": str(presentation.id),
            "deck_page_count": len(imported),
            "slides": imported,
        }


def _update_session_meta(session_id: str, payload: dict[str, object]) -> Path | None:
    session_dir = _SESSIONS_ROOT / session_id
    meta_path = session_dir / "session-meta.json"
    if not meta_path.is_file():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["project_id"] = payload["project_id"]
    meta["project_name"] = payload["project_name"]
    meta["deck_page_count"] = payload["deck_page_count"]
    meta["presentation_id"] = payload["presentation_id"]
    notes = str(meta.get("notes") or "")
    marker = "Seeded from architectural_slides"
    if marker not in notes:
        meta["notes"] = (
            f"{notes} {marker} case_001–case_{int(payload['deck_page_count']):03d}."
        ).strip()
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=20, help="Number of cases (default 20)")
    parser.add_argument(
        "--name",
        default="Playbook E · Architectural Benchmark",
        help="Project display name",
    )
    parser.add_argument(
        "--session",
        default="",
        help="Optional rehearsal session_id to update session-meta.json",
    )
    args = parser.parse_args(argv)

    print(f"Seeding {args.count} pages from {_BENCHMARK_ROOT} …")
    payload = seed_deck(count=args.count, project_name=args.name)
    out = _PROJECT_ROOT / "docs" / "rehearsal" / "sessions" / "playbook-e-benchmark-seed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nproject_id:       {payload['project_id']}")
    print(f"presentation_id:  {payload['presentation_id']}")
    print(f"deck_page_count:  {payload['deck_page_count']}")
    print(f"seed record:      {out.relative_to(_PROJECT_ROOT)}")

    if args.session:
        meta = _update_session_meta(args.session, payload)
        if meta:
            print(f"updated session:  {meta.relative_to(_PROJECT_ROOT)}")
        else:
            print(f"warn: session meta not found for {args.session}", file=sys.stderr)

    print("\nNext: open Archium → 切换项目 → Studio → walk Playbook E.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

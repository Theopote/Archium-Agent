"""Tests for benchmark human review export/import."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from archium.application.architectural_benchmark_review_store import (
    build_human_review_export,
    export_human_review_bundle,
    import_human_review_bundle,
    load_case_review,
    parse_human_review_import_payload,
    save_case_review,
)
from archium.domain.visual.benchmark import (
    HumanVisualReview,
    HumanVisualReviewSource,
)


def _seed_case(root: Path, case_id: str, *, title: str = "Demo") -> Path:
    case_dir = root / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "input.json").write_text(
        json.dumps(
            {
                "case_id": case_id,
                "title": title,
                "category": "drawing",
                "page_type": "demo",
                "page_task": "demo",
                "visual_focus": "demo",
                "expected_layout_family": "drawing_focus",
                "allowed_layout_variants": ["drawing_only"],
                "layout_variant": "drawing_only",
                "chapter_id": "ch1",
                "slide_order": 1,
            }
        ),
        encoding="utf-8",
    )
    (case_dir / "preview.png").write_bytes(b"png")
    _seed_visual_review_ready(case_dir)
    return case_dir


def _seed_visual_review_ready(case_dir: Path) -> None:
    """Seed minimal same-generation render artifacts so the case passes eligibility."""
    from archium.domain.visual.benchmark import BenchmarkRenderManifest
    from archium.domain.visual.render_scene import (
        BackgroundStyle,
        RenderScene,
        compute_scene_hash,
    )
    from tests.benchmark.architectural_slides.render_manifest import (
        SCENE_JSON_NAME,
        SCENE_PREVIEW_NAME,
        sha256_file,
        write_pptx_render_sidecar,
        write_pptx_sidecar,
        write_render_manifest,
    )

    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[],
    )
    (case_dir / SCENE_JSON_NAME).write_text(
        json.dumps(scene.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (case_dir / SCENE_PREVIEW_NAME).write_bytes(b"png")
    scene_hash = compute_scene_hash(scene)

    from pptx import Presentation

    pptx_path = case_dir / "output.pptx"
    Presentation().save(str(pptx_path))
    pptx_hash = sha256_file(pptx_path)
    (case_dir / "pptx_render.png").write_bytes(b"png")
    write_pptx_sidecar(case_dir, scene_hash=scene_hash, pptx_content_hash=pptx_hash)
    write_pptx_render_sidecar(case_dir, scene_hash=scene_hash, pptx_content_hash=pptx_hash)
    write_render_manifest(
        case_dir,
        BenchmarkRenderManifest(
            render_source="pptx_screenshot",
            render_valid=True,
            scene_id=str(scene.id),
            scene_hash=scene_hash,
            asset_count=0,
            real_asset_count=0,
            placeholder_asset_count=0,
            rendered_at=datetime.now(UTC),
            renderer="test",
            screenshot_tools_available=True,
            pptx_screenshot_generated=True,
            pptx_screenshot_reused=False,
            pptx_screenshot_source_hash=scene_hash,
            pptx_content_hash=pptx_hash,
            post_render_qa_passed=True,
            post_render_qa_issues=[],
        ),
    )


def _manual_review(case_id: str, *, accepted: bool = True) -> HumanVisualReview:
    return HumanVisualReview(
        case_id=case_id,
        source=HumanVisualReviewSource.MANUAL,
        information_hierarchy=4,
        visual_focus=4,
        reading_order=4,
        image_text_relationship=4,
        whitespace_density=4,
        architectural_expression=4,
        aesthetic_finish=4,
        editability=4,
        accepted=accepted,
        reviewer="张工",
        reviewed_at=datetime.now(UTC),
        reviewer_notes="exported",
    )


def test_build_export_lists_manual_and_pending(tmp_path: Path) -> None:
    _seed_case(tmp_path, "case_a")
    _seed_case(tmp_path, "case_b", title="Second")
    save_case_review(_manual_review("case_a"), root=tmp_path)
    (tmp_path / "case_b" / "human_review.json").write_text(
        json.dumps(
            {
                "case_id": "case_b",
                "source": "placeholder",
                "information_hierarchy": 4,
                "visual_focus": 4,
                "reading_order": 4,
                "image_text_relationship": 4,
                "whitespace_density": 4,
                "architectural_expression": 4,
                "aesthetic_finish": 4,
                "editability": 4,
                "reviewer_notes": "占位",
            }
        ),
        encoding="utf-8",
    )

    bundle = build_human_review_export(root=tmp_path)
    assert bundle.case_count == 2
    assert bundle.manual_review_count == 1
    assert bundle.pending_count == 1
    assert bundle.reviews[0].case_id == "case_a"
    assert bundle.pending_cases[0].case_id == "case_b"
    assert bundle.human_quality_gate_passed is False


def test_export_and_import_round_trip(tmp_path: Path) -> None:
    _seed_case(tmp_path, "case_a")
    _seed_case(tmp_path, "case_b")
    save_case_review(_manual_review("case_a"), root=tmp_path)

    export_path = tmp_path / "export.json"
    export_human_review_bundle(export_path, root=tmp_path)
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert payload["bundle_version"] == 1
    assert payload["manual_review_count"] == 1

    # Simulate fresh tree without manual review on case_a
    (tmp_path / "case_a" / "human_review.json").unlink()
    result = import_human_review_bundle(export_path, root=tmp_path)
    assert result.imported_count == 1
    loaded = load_case_review("case_a", root=tmp_path)
    assert loaded is not None
    assert loaded.is_manual_review()
    assert loaded.reviewer == "张工"


def test_import_accepts_plain_review_list(tmp_path: Path) -> None:
    _seed_case(tmp_path, "case_a")
    list_path = tmp_path / "reviews.json"
    list_path.write_text(
        json.dumps([_manual_review("case_a").model_dump(mode="json")]),
        encoding="utf-8",
    )
    reviews = parse_human_review_import_payload(json.loads(list_path.read_text(encoding="utf-8")))
    assert len(reviews) == 1
    result = import_human_review_bundle(list_path, root=tmp_path)
    assert result.imported_count == 1


def test_import_rejects_placeholder_source(tmp_path: Path) -> None:
    _seed_case(tmp_path, "case_a")
    bundle_path = tmp_path / "bad.json"
    bundle_path.write_text(
        json.dumps(
            {
                "bundle_version": 1,
                "exported_at": datetime.now(UTC).isoformat(),
                "case_count": 1,
                "manual_review_count": 1,
                "pending_count": 0,
                "reviews": [
                    {
                        "case_id": "case_a",
                        "source": "placeholder",
                        "information_hierarchy": 4,
                        "visual_focus": 4,
                        "reading_order": 4,
                        "image_text_relationship": 4,
                        "whitespace_density": 4,
                        "architectural_expression": 4,
                        "aesthetic_finish": 4,
                        "editability": 4,
                    }
                ],
                "pending_cases": [],
                "human_quality_gate_passed": False,
                "human_quality_gate_reasons": [],
            }
        ),
        encoding="utf-8",
    )
    result = import_human_review_bundle(bundle_path, root=tmp_path)
    assert result.imported_count == 0
    assert result.rejected_count == 1


def test_import_skip_existing_manual(tmp_path: Path) -> None:
    _seed_case(tmp_path, "case_a")
    save_case_review(_manual_review("case_a"), root=tmp_path)
    export_path = tmp_path / "export.json"
    export_human_review_bundle(export_path, root=tmp_path)
    result = import_human_review_bundle(export_path, root=tmp_path, skip_existing_manual=True)
    assert result.imported_count == 0
    assert result.skipped_count == 1

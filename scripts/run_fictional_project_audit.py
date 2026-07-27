#!/usr/bin/env python3
"""Run one fictional project through content, visual, PPTX, and screenshot stages."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_FICTIONAL_CHAPTERS = (
    ("ch1", "区位背景", 4),
    ("ch2", "设计理念", 4),
    ("ch3", "空间结构", 4),
    ("ch4", "立面材料", 4),
    ("ch5", "总结决策", 4),
)


def _fictional_brief() -> dict[str, object]:
    return {
        "title": "滨海文化综合体方案汇报",
        "presentation_type": "client_review",
        "audience": "规划主管部门与业主代表",
        "purpose": "汇报新建方案空间结构与实施策略",
        "duration_minutes": 40,
        "target_slide_count": 20,
        "core_message": "以公共开放空间串联文化、办公与商业功能",
        "decisions_required": ["确认总体空间结构", "确认首期建设范围", "确认立面材料方向"],
        "audience_concerns": ["公共开放空间落实", "一期投资与二期扩展", "滨海城市界面"],
        "tone": "professional",
        "required_sections": [title for _, title, _ in _FICTIONAL_CHAPTERS],
        "excluded_topics": [],
        "language": "zh-CN",
    }


def _fictional_storyline() -> dict[str, object]:
    return {
        "thesis": "公共开放空间是组织复合功能与滨海城市界面的核心骨架",
        "narrative_pattern": "problem_solution",
        "narrative_arc": {
            "opening_context": "滨海片区需要兼顾公共文化、办公与商业活力",
            "central_problem": "多功能叠加容易形成封闭体量和割裂流线",
            "tension_building": ["城市界面开放性", "首期建设与远期弹性"],
            "turning_point": "以连续公共空间替代单体功能拼接",
            "proposed_resolution": "构建一条连接城市、展厅与滨海平台的公共脊柱",
            "final_decision": "确认空间骨架、首期范围和材料方向",
        },
        "chapters": [
            {
                "id": chapter_id,
                "title": title,
                "purpose": f"说明{title}",
                "key_message": f"{title}共同支撑公共空间主线",
                "order": order,
                "estimated_slide_count": count,
            }
            for order, (chapter_id, title, count) in enumerate(_FICTIONAL_CHAPTERS)
        ],
    }


def _fictional_slides() -> list[dict[str, object]]:
    slides: list[dict[str, object]] = []
    order = 0
    detail_titles = {
        "区位背景": ["项目愿景", "城市联系", "规划约束", "核心机会"],
        "设计理念": ["公共脊柱", "开放首层", "立体慢行", "空间体验"],
        "空间结构": ["功能分区", "交通组织", "公共空间", "分期弹性"],
        "立面材料": ["滨海意象", "遮阳策略", "材料体系", "夜景表达"],
        "总结决策": ["价值总结", "关键指标", "实施路径", "待确认事项"],
    }
    for chapter_index, (chapter_id, chapter_title, count) in enumerate(_FICTIONAL_CHAPTERS):
        for local_index in range(count):
            title = chapter_title if local_index == 0 else detail_titles[chapter_title][local_index]
            slide_type = "section" if local_index == 0 else "content"
            if order == 0:
                slide_type = "title"
            elif chapter_index == len(_FICTIONAL_CHAPTERS) - 1 and local_index == count - 1:
                slide_type = "closing"
            slides.append(
                {
                    "chapter_id": chapter_id,
                    "order": order,
                    "title": title,
                    "message": f"{title}服务于连续公共空间这一总体策略",
                    "slide_type": slide_type,
                    "layout_id": "default",
                    "key_points": [
                        f"{title}的核心判断",
                        f"{title}对空间与实施的影响",
                    ],
                    "visual_requirements": [],
                    "source_citations": [],
                    "speaker_notes": None,
                }
            )
            order += 1
    return slides


def fictional_project_selector(request):  # noqa: ANN001, ANN201
    """Return deterministic content aligned with the fictional project."""
    prompt = request.user_prompt
    if "生成 PresentationBrief JSON" in prompt:
        return json.dumps(_fictional_brief(), ensure_ascii=False)
    if "生成 Storyline JSON" in prompt:
        return json.dumps(_fictional_storyline(), ensure_ascii=False)
    if "生成单页 SlideSpec JSON" in prompt:
        order_match = re.search(r"页序：(\d+)", prompt)
        if order_match:
            order = int(order_match.group(1))
            slides = _fictional_slides()
            if 0 <= order < len(slides):
                return json.dumps(slides[order], ensure_ascii=False)
    if "SlidePlan JSON" in prompt:
        return json.dumps({"slides": _fictional_slides()}, ensure_ascii=False)

    from tests.fixtures.mock_llm import brief_alignment_ok_selector

    return brief_alignment_ok_selector(request)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=(
            _PROJECT_ROOT
            / "tests"
            / "e2e"
            / "real_projects"
            / "manifests"
            / "project_001_new_building.json"
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    run_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = (
        args.output_dir or _PROJECT_ROOT / ".data" / "fictional_project_audit" / run_stamp
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    from archium.application.formal_pptx_export_service import FormalPptxExportService
    from archium.application.project_acceptance_service import ProjectAcceptanceService
    from archium.config.settings import Settings
    from archium.infrastructure.database.base import Base
    from archium.infrastructure.database.repositories import PresentationRepository
    from archium.infrastructure.database.session import create_engine_from_settings, get_session
    from archium.infrastructure.llm import MockLLMProvider
    from archium.infrastructure.renderers.pptx_screenshot import (
        export_pptx_slide_pngs,
        screenshot_tools_available,
    )
    from tests.e2e.real_projects.loader import seed_real_project_case

    settings = Settings(
        _env_file=None,
        database_path=output_dir / "database" / "audit.db",
        workflow_checkpoint_path=output_dir / "database" / "checkpoints.db",
        project_storage_path=output_dir / "projects",
        output_path=output_dir / "outputs",
        chroma_path=output_dir / "chroma",
        llm_api_key=None,
        embedding_provider="mock",
        retrieval_enabled=True,
        visual_capacity_block_overloaded=False,
    )
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)

    with tempfile.TemporaryDirectory() as scratch, get_session(engine) as session:
        loaded, project, input_paths = seed_real_project_case(
            session,
            args.manifest.resolve(),
            scratch_dir=Path(scratch),
            settings=settings,
        )
        acceptance = ProjectAcceptanceService(
            session,
            MockLLMProvider(selector=fictional_project_selector),
            settings=settings,
        ).run(
            loaded.manifest,
            project=project,
            presentation_request=loaded.request,
        )
        presentations = PresentationRepository(session).list_by_project(project.id)
        if not presentations:
            raise RuntimeError("Workflow completed without a presentation")
        presentation = presentations[0]
        slides = PresentationRepository(session).list_slides(presentation.id)
        export = FormalPptxExportService(session, settings=settings).export_editable_pptx(
            presentation.id,
        )

        screenshot_paths: list[Path] = []
        screenshot_error: str | None = None
        tools_available = screenshot_tools_available()
        if tools_available:
            try:
                screenshot_paths = export_pptx_slide_pngs(
                    export.path,
                    output_dir / "screenshots",
                )
                if not screenshot_paths:
                    screenshot_error = "截图工具可用，但没有生成任何页面截图。"
            except Exception as exc:  # pragma: no cover - host tool dependent
                screenshot_error = str(exc)

        audit_passed = (
            acceptance.metrics.deliverable_ready
            and export.is_formal
            and len(screenshot_paths) == len(slides)
        )

        report = {
            "run_at": datetime.now(UTC).isoformat(),
            "execution_mode": "mock_llm_real_layout_real_pptx",
            "project": {
                "id": str(project.id),
                "name": project.name,
                "manifest": str(args.manifest.resolve()),
                "input_count": len(input_paths),
            },
            "presentation": {
                "id": str(presentation.id),
                "slide_count": len(slides),
                "titles": [slide.title for slide in slides],
            },
            "acceptance": acceptance.model_dump(mode="json"),
            "audit_passed": audit_passed,
            "export": {
                "path": str(export.path),
                "authority": str(export.authority),
                "is_formal": export.is_formal,
                "warnings": export.warnings,
                "screenshot_tools_available": tools_available,
                "screenshot_count": len(screenshot_paths),
                "screenshot_paths": [str(path) for path in screenshot_paths],
                "screenshot_error": screenshot_error,
            },
        }
        report_path = output_dir / "audit_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"AUDIT_REPORT={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

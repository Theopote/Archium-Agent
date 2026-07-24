#!/usr/bin/env python3
"""Run Playbook F F1–F5 service rehearsal and fill session templates.

Uses the same partial-knowledge scenario as integration tests (mock LLM).
Does not replace a non-developer Streamlit walkthrough — marks session accordingly.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SESSIONS_ROOT = _PROJECT_ROOT / "docs" / "rehearsal" / "sessions"

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

PARTIAL_KNOWLEDGE_PROMPT = (
    "西安市某医院老院区改造，手头有一张老门诊楼照片、"
    "地址和一份旧院区介绍，甲方还没说清功能分区。"
)


@dataclass
class StepResult:
    step_id: str
    step_name: str
    passed: bool
    notes: str = ""
    evidence_path: str = ""
    waived: bool = False
    waive_reason: str = ""


@dataclass
class RehearsalReport:
    session_id: str
    steps: list[StepResult] = field(default_factory=list)
    gate_passed: bool = False
    gate_output: str = ""
    commit: str = ""
    issues: list[dict[str, str]] = field(default_factory=list)

    @property
    def f1_f5_pass(self) -> bool:
        core = [s for s in self.steps if s.step_id in {"F1", "F2", "F3", "F4", "F5"}]
        return all(s.passed or s.waived for s in core)


def _git_short_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _run_gate() -> tuple[bool, str]:
    cmd = [sys.executable, "-m", "pytest", *_gate_targets(), "-q", "--tb=line"]
    proc = subprocess.run(cmd, cwd=_PROJECT_ROOT, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output.strip()


def _gate_targets() -> list[str]:
    return [
        "tests/integration/test_partial_knowledge_project_flow.py",
        "tests/unit/test_project_context.py",
        "tests/unit/test_project_context_routing.py",
        "tests/unit/test_knowledge_state_routing.py",
        "tests/unit/test_workspace_mode_service.py",
    ]


@dataclass
class _RehearsalPayload:
    evidence: dict[str, object]
    steps: list[StepResult]


def _ensure_session_dir(session_id: str, *, force: bool) -> Path:
    session_dir = _SESSIONS_ROOT / session_id
    if session_dir.exists() and not force:
        return session_dir
    cmd = [sys.executable, str(_PROJECT_ROOT / "scripts" / "new_playbook_f_session.py"), session_id]
    if force:
        cmd.append("--force")
    proc = subprocess.run(cmd, cwd=_PROJECT_ROOT)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return session_dir


def _run_f1_f5_rehearsal() -> _RehearsalPayload:
    import archium.infrastructure.database.models  # noqa: F401
    from archium.application.context_intelligence_service import ContextIntelligenceService
    from archium.application.exploration_service import ExplorationService
    from archium.application.ingestion_service import IngestionService
    from archium.application.project_context_builder import build_project_context
    from archium.application.workspace_mode_service import WorkspaceModeService
    from archium.config.settings import Settings, reset_settings
    from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
    from archium.domain.context.recommended_workflow import RecommendedWorkflow
    from archium.domain.document import DocumentChunk, SourceDocument
    from archium.domain.enums import (
        ConceptDirectionStatus,
        DocumentType,
        ExplorationSessionStatus,
        ProcessingStatus,
        ProjectOriginMode,
        VerificationStatus,
    )
    from archium.domain.fact import ProjectFact
    from archium.domain.intent.next_best_action import NextBestActionType
    from archium.domain.project import Project
    from archium.infrastructure.database.base import Base
    from archium.infrastructure.database.repositories import (
        DocumentRepository,
        FactRepository,
        ProjectRepository,
    )
    from archium.infrastructure.database.session import create_engine_from_settings, reset_engine_cache
    from archium.infrastructure.llm.concept_direction_schemas import (
        ConceptDirectionBatchDraft,
        ConceptDirectionDraft,
        ConceptVisualPromptDraft,
    )
    from archium.infrastructure.llm.context_intelligence_schemas import (
        ContextAssessmentDraft,
        NextBestActionDraft,
    )
    from archium.infrastructure.llm.idea_seed_schemas import IdeaSeedDraft
    from archium.infrastructure.llm.mission_schemas import (
        DesignIntentDraft,
        MissionGenerationDraft,
    )
    from sqlalchemy.orm import Session
    from tests.fixtures.sample_files import create_sample_docx

    reset_settings()
    reset_engine_cache()

    with tempfile.TemporaryDirectory(prefix="playbook-f-rehearsal-") as tmp:
        base = Path(tmp) / "archium"
        (base / "database").mkdir(parents=True)
        settings = Settings(
            _env_file=None,
            database_path=base / "database" / "rehearsal.db",
            workflow_checkpoint_path=base / "database" / "checkpoints.db",
            project_storage_path=base / "projects",
            output_path=base / "outputs",
            chroma_path=base / "chroma",
            llm_api_key=None,
            embedding_provider="mock",
        )
        engine = create_engine_from_settings(settings)
        Base.metadata.create_all(engine)
        session = Session(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

        evidence: dict[str, object] = {}
        steps: list[StepResult] = []

        try:
            project = ProjectRepository(session).create(
                Project(
                    name="西安某医院老院区改造",
                    description=PARTIAL_KNOWLEDGE_PROMPT,
                )
            )
            session.commit()

            FactRepository(session).create(
                ProjectFact(
                    project_id=project.id,
                    key="location",
                    label="地点",
                    value="西安",
                    verification_status=VerificationStatus.USER_CONFIRMED,
                )
            )
            docx = create_sample_docx(
                Path(tmp) / "旧院区介绍.docx",
                heading="老院区概况",
                body="现状门诊楼建于1998年，南北向布局，需保留部分历史立面。",
            )
            doc = DocumentRepository(session).create_document(
                SourceDocument(
                    project_id=project.id,
                    filename="旧院区介绍.docx",
                    original_path=str(docx),
                    stored_path=str(docx),
                    file_type=DocumentType.DOCX,
                    file_hash="c" * 64,
                    size_bytes=docx.stat().st_size,
                    processing_status=ProcessingStatus.COMPLETED,
                )
            )
            DocumentRepository(session).create_chunk(
                DocumentChunk(
                    document_id=doc.id,
                    project_id=project.id,
                    content="现状门诊楼建于1998年，南北向布局，需保留部分历史立面。",
                    chunk_index=0,
                    page_number=1,
                    content_type="text",
                )
            )
            session.commit()

            assess_llm = MagicMock()
            assess_llm.generate_structured.return_value = ContextAssessmentDraft(
                completeness_score=0.34,
                maturity_stage="design_analysis",
                evidence_ratio=0.22,
                assumption_ratio=0.72,
                known={"location": "西安", "type": "医院改造"},
                unknown=["功能分区", "规模", "投资"],
                missing_information=["功能分区", "规模"],
                suggested_origin_mode="existing_project",
                understanding_summary="部分资料：有地点与旧楼背景，仍缺功能与规模。",
                actions=[
                    NextBestActionDraft(
                        action="ask",
                        reason="甲方尚未说清功能分区",
                        question="本次改造优先解决哪些科室或流线问题？",
                        priority=0,
                    ),
                    NextBestActionDraft(
                        action="explore_directions",
                        reason="在已知约束内并行推演改造策略",
                        priority=1,
                    ),
                    NextBestActionDraft(
                        action="upload_materials",
                        reason="可继续补充图纸与照片",
                        priority=2,
                    ),
                ],
            )
            assessment = ContextIntelligenceService(session, assess_llm).assess_and_persist(
                project.id,
                PARTIAL_KNOWLEDGE_PROMPT,
            )
            ctx = assessment.project_context
            f1_ok = (
                ctx is not None
                and assessment.suggested_origin_mode == ProjectOriginMode.CONCEPT_EXPLORATION
                and 0.2 <= assessment.knowledge_state.completeness_score < 0.5
                and ctx.lifecycle_stage
                in {ProjectLifecycleStage.RESEARCH, ProjectLifecycleStage.CONCEPT}
            )
            evidence["F1"] = {
                "completeness_score": assessment.knowledge_state.completeness_score,
                "lifecycle_stage": ctx.lifecycle_stage.value if ctx else None,
                "recommended_workflow": ctx.recommended_workflow.value if ctx else None,
                "suggested_origin_mode": assessment.suggested_origin_mode.value,
                "understanding_summary": assessment.understanding_summary,
            }
            steps.append(
                StepResult(
                    "F1",
                    "Genesis 单次描述",
                    f1_ok,
                    notes=(
                        f"completeness={assessment.knowledge_state.completeness_score:.2f}, "
                        f"stage={ctx.lifecycle_stage.value if ctx else 'n/a'}, "
                        f"legacy_origin={assessment.suggested_origin_mode.value}"
                    ),
                    evidence_path="evidence/F1-assessment.json",
                )
            )

            first_action = assessment.actions[0].action if assessment.actions else None
            upload_rank = next(
                (idx for idx, item in enumerate(assessment.actions) if item.action.value == "upload_materials"),
                99,
            )
            f2_ok = first_action in {
                NextBestActionType.ASK,
                NextBestActionType.EXPLORE_DIRECTIONS,
                NextBestActionType.GENERATE_MISSION,
            } and upload_rank > 0
            evidence["F2"] = {
                "actions": [
                    {"action": a.action.value, "reason": a.reason, "priority": a.priority}
                    for a in assessment.actions
                ]
            }
            steps.append(
                StepResult(
                    "F2",
                    "建议下一步 NBA",
                    f2_ok,
                    notes=f"first_action={first_action.value if first_action else 'none'}",
                    evidence_path="evidence/F2-actions.json",
                )
            )

            f3_ok = (
                "location" in (assessment.knowledge_state.known or {})
                or "西安" in str(assessment.knowledge_state.known)
            ) and assessment.knowledge_state.completeness_score < 0.7
            evidence["F3"] = {
                "known": assessment.knowledge_state.known,
                "unknown": assessment.knowledge_state.unknown,
                "document_count": 1,
            }
            steps.append(
                StepResult(
                    "F3",
                    "补资料后刷新",
                    f3_ok,
                    notes="Seeded 1 DOCX + confirmed location fact before assess",
                    evidence_path="evidence/F3-knowledge.json",
                )
            )

            explore_llm = MagicMock()
            explore_llm.generate_structured.side_effect = [
                IdeaSeedDraft(
                    theme="医院老院区再生",
                    inspiration="在有限资料下保留历史与更新流线",
                    keywords=["改造", "老院区", "西安"],
                    imagination_level="moderate",
                ),
                ConceptDirectionBatchDraft(
                    directions=[
                        ConceptDirectionDraft(
                            title="微创更新",
                            summary="保留立面与结构，局部加建",
                            theme="最小干预",
                            spatial_idea="沿既有轴线插入新核",
                            spatial_strategy="保留南北主轴线，点状加建",
                            formal_language="新旧并置，克制体量",
                            material_strategy="保留砖墙，局部玻璃连廊",
                            reference_dna=["医院改扩建类型"],
                            visual_prompt=ConceptVisualPromptDraft(
                                image_prompt="hospital campus renovation axonometric",
                                camera="axonometric",
                                style="concept sketch",
                            ),
                            experience_focus="流线清晰",
                            differentiator="资料有限仍可比较",
                            open_questions=["功能分区？"],
                            risks=["结构鉴定未做"],
                        ),
                        ConceptDirectionDraft(
                            title="片区重组",
                            summary="重新组织入口与门诊流线",
                            theme="流线重组",
                            spatial_idea="新入口广场 + 内部连廊",
                            spatial_strategy="入口外移，内部环形流线",
                            formal_language="清晰几何与开放灰空间",
                            material_strategy="浅色石材与金属雨棚",
                            reference_dna=["当代医疗建筑入口策略"],
                            visual_prompt=ConceptVisualPromptDraft(
                                image_prompt="hospital entrance plaza concept",
                                camera="eye-level",
                                style="soft atmosphere",
                            ),
                            experience_focus="患者到达体验",
                            differentiator="重新定义院区界面",
                            open_questions=["市政退线？"],
                            risks=["拆迁范围未定"],
                        ),
                    ]
                ),
                MissionGenerationDraft(
                    title="西安某医院老院区改造",
                    task_statement="在部分资料条件下明确改造策略与待澄清问题",
                    design_intent=DesignIntentDraft(
                        theme="最小干预",
                        problem_statement="如何在资料不完整时推进改造讨论？",
                        target_users=["医护", "患者"],
                        desired_experience="流线清晰",
                    ),
                    assumptions=[],
                    clarifying_questions=[],
                    knowledge_gaps=[],
                ),
            ]
            exploration_service = ExplorationService(session, explore_llm, settings=settings)
            exploration = exploration_service.start_session(
                project.id,
                PARTIAL_KNOWLEDGE_PROMPT,
            ).exploration
            generated = exploration_service.generate_directions(exploration.id)
            structured = [
                {
                    "title": d.title,
                    "spatial_strategy": d.spatial_strategy,
                    "formal_language": d.formal_language,
                    "has_visual_prompt": bool(d.visual_prompt and d.visual_prompt.image_prompt),
                }
                for d in generated.directions
            ]
            f4_ok = (
                len(generated.directions) >= 2
                and all(d.spatial_strategy and d.formal_language for d in generated.directions)
                and any(d.visual_prompt and d.visual_prompt.image_prompt for d in generated.directions)
            )
            evidence["F4"] = {"directions": structured}
            steps.append(
                StepResult(
                    "F4",
                    "结构化概念方向",
                    f4_ok,
                    notes=f"direction_count={len(generated.directions)}",
                    evidence_path="evidence/F4-directions.json",
                )
            )

            selected = exploration_service.select_direction(generated.directions[0].id)
            committed = exploration_service.commit_to_mission(exploration.id)
            workspace = WorkspaceModeService(session)
            f5_ok = (
                selected.direction.status == ConceptDirectionStatus.SELECTED
                and committed.exploration.status == ExplorationSessionStatus.COMMITTED
                and committed.mission.design_intent is not None
                and bool(committed.mission.title)
            )
            evidence["F5"] = {
                "mission_title": committed.mission.title,
                "design_intent_theme": committed.mission.design_intent.theme
                if committed.mission.design_intent
                else None,
                "exploration_status": committed.exploration.status.value,
                "workspace_mode": workspace.resolve_mode(project.id).value,
                "primary_page": workspace.resolve_primary_page_key(project.id),
            }
            steps.append(
                StepResult(
                    "F5",
                    "选定方向并 Mission",
                    f5_ok,
                    notes=f"mission={committed.mission.title!r}",
                    evidence_path="evidence/F5-mission.json",
                )
            )

            for optional_id, optional_name in (
                ("F6", "概念示意"),
                ("F7", "草稿与 evidence gate"),
            ):
                steps.append(
                    StepResult(
                        optional_id,
                        optional_name,
                        False,
                        waived=True,
                        waive_reason="Not exercised in engineer service rehearsal",
                    )
                )

            return _RehearsalPayload(evidence=evidence, steps=steps)
        finally:
            session.close()
            Base.metadata.drop_all(engine)
            engine.dispose()
            reset_engine_cache()
            reset_settings()


def _write_evidence(session_dir: Path, evidence: dict[str, object]) -> None:
    evidence_dir = session_dir / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    mapping = {
        "F1": "F1-assessment.json",
        "F2": "F2-actions.json",
        "F3": "F3-knowledge.json",
        "F4": "F4-directions.json",
        "F5": "F5-mission.json",
    }
    for key, filename in mapping.items():
        if key in evidence:
            (evidence_dir / filename).write_text(
                json.dumps(evidence[key], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )


def _write_step_log(session_dir: Path, steps: list[StepResult]) -> None:
    path = session_dir / "playbook-f-step-log.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "step_id",
                "step_name",
                "scenario_variant",
                "pass",
                "notes",
                "evidence_path",
                "blocker_level",
            ],
        )
        writer.writeheader()
        for step in steps:
            writer.writerow(
                {
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "scenario_variant": "standard_hospital_renovation",
                    "pass": "Y" if step.passed else ("Waive" if step.waived else "N"),
                    "notes": step.notes or step.waive_reason,
                    "evidence_path": step.evidence_path,
                    "blocker_level": "",
                }
            )


def _write_session_meta(session_dir: Path, report: RehearsalReport) -> None:
    meta_path = session_dir / "session-meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["date"] = date.today().isoformat()
    meta["status"] = "engineer_service_rehearsal"
    meta["facilitator"] = "Cursor agent (automated service rehearsal)"
    meta["operator"] = "engineering dry-run"
    meta["operator_is_non_developer"] = False
    meta["llm_configured"] = False
    meta["vision_image_enabled"] = False
    meta["scenario_prompt"] = PARTIAL_KNOWLEDGE_PROMPT
    meta["automated_gate"] = {
        "command": "python scripts/run_playbook_f_gate.py -q",
        "passed": report.gate_passed,
        "run_date": date.today().isoformat(),
        "commit": report.commit,
    }
    meta["rehearsal_mode"] = "service_layer_mock_llm"
    meta["ui_walkthrough"] = False
    meta["pending_human_signoff"] = {
        "required_for": "Context Intelligence full acceptance",
        "missing": "Non-developer Streamlit F1–F4 with real LLM",
    }
    for step in report.steps:
        if step.step_id in meta["steps"]:
            meta["steps"][step.step_id] = {
                "pass": bool(step.passed) if not step.waived else None,
                "waived": step.waived,
                "waive_reason": step.waive_reason,
                "notes": step.notes,
            }
    meta["overall_pass"] = report.f1_f5_pass and report.gate_passed
    meta["overall_pass_scope"] = "F1-F5 service rehearsal only"
    meta["completed_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_rehearsal(session_id: str, *, force_scaffold: bool = False) -> RehearsalReport:
    session_dir = _ensure_session_dir(session_id, force=force_scaffold)
    gate_passed, gate_output = _run_gate()
    payload = _run_f1_f5_rehearsal()
    report = RehearsalReport(
        session_id=session_id,
        steps=payload.steps,
        gate_passed=gate_passed,
        gate_output=gate_output,
        commit=_git_short_commit(),
    )
    _write_evidence(session_dir, payload.evidence)
    _write_step_log(session_dir, payload.steps)
    _write_session_meta(session_dir, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "session_id",
        nargs="?",
        default=f"{date.today().isoformat()}-playbook-f-1",
        help="Session folder under docs/rehearsal/sessions/",
    )
    parser.add_argument(
        "--force-scaffold",
        action="store_true",
        help="Recreate session templates",
    )
    args = parser.parse_args(argv)

    report = run_rehearsal(args.session_id, force_scaffold=args.force_scaffold)
    session_dir = _SESSIONS_ROOT / args.session_id

    print(f"Session: {session_dir.relative_to(_PROJECT_ROOT)}")
    print(f"Automated gate: {'PASS' if report.gate_passed else 'FAIL'}")
    for step in report.steps:
        status = "PASS" if step.passed else ("WAIVE" if step.waived else "FAIL")
        print(f"  {step.step_id} {status} — {step.notes or step.waive_reason}")
    print(
        f"Overall (F1-F5 service): {'PASS' if report.f1_f5_pass and report.gate_passed else 'FAIL'}"
    )
    print(
        "\nNote: Context Intelligence full acceptance still needs a non-developer Streamlit walkthrough."
    )
    return 0 if report.f1_f5_pass and report.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Format PresentationManuscript for LLM planning prompts (no raw RAG)."""

from __future__ import annotations

from archium.application.chunk_models import ProjectContextBundle
from archium.domain.presentation_manuscript import PresentationManuscript


def format_manuscript_for_prompt(manuscript: PresentationManuscript) -> str:
    """Compact manuscript text — design agents read this instead of document chunks."""
    lines = [
        "【Presentation Manuscript · 已核实研究产物】",
        f"标题：{manuscript.title}",
        f"项目摘要：{manuscript.project_summary}",
        f"叙事论点：{manuscript.narrative_thesis}",
    ]
    if manuscript.verified_facts:
        lines.append("【已核实事实】")
        for fact in manuscript.verified_facts[:40]:
            flag = "✓" if fact.verified else "?"
            lines.append(f"- [{flag}] {fact.statement}")
    if manuscript.sections:
        lines.append("【章节论证结构】")
        for section in sorted(manuscript.sections, key=lambda s: s.order):
            lines.append(f"## {section.title} (order={section.order})")
            lines.append(f"目的：{section.purpose}")
            lines.append(f"主张：{section.argument}")
            for point in section.key_points[:6]:
                lines.append(f"  - {point}")
    if manuscript.evidence_catalog:
        lines.append("【证据目录】")
        for item in manuscript.project_evidence_only()[:24]:
            lines.append(f"- ({item.evidence_type}) {item.summary}")
    if manuscript.citations:
        lines.append("【引用】")
        for cite in manuscript.citations[:20]:
            label = cite.label or cite.citation.document_name
            page = f", p.{cite.citation.page_number}" if cite.citation.page_number else ""
            lines.append(f"- [{cite.id}] {label}{page}")
    if manuscript.unresolved_questions:
        lines.append("【待澄清】")
        for q in manuscript.unresolved_questions[:10]:
            lines.append(f"- {q}")
    if manuscript.missing_information:
        lines.append("【缺失信息】")
        for m in manuscript.missing_information[:10]:
            lines.append(f"- {m}")
    return "\n".join(lines)


def context_bundle_from_manuscript(manuscript: PresentationManuscript) -> ProjectContextBundle:
    """Citation-light bundle for slide planning when manuscript pipeline is active."""
    return ProjectContextBundle(text=format_manuscript_for_prompt(manuscript))

"""Format SlideGenerationContext for LLM prompts."""

from __future__ import annotations

from archium.application.context_budget_manager import ContextBudgetManager
from archium.domain.slide_generation_context import SlideGenerationContext


def format_slide_generation_context(context: SlideGenerationContext) -> str:
    """Compact, page-scoped prompt block (not full project dump)."""
    slide = context.slide_spec
    lines = [
        "【当前页面任务】",
        f"标题：{slide.title}",
        f"核心观点：{slide.message}",
    ]
    if slide.key_points:
        lines.append("要点：")
        for point in slide.key_points[:5]:
            lines.append(f"- {point}")
    if context.section_summary.strip():
        lines.append(f"\n【章节背景】\n{context.section_summary.strip()}")
    if context.previous_slide_summary:
        lines.append(f"\n【上一页摘要】\n{context.previous_slide_summary}")
    if context.next_slide_intent:
        lines.append(f"\n【下一页意图】\n{context.next_slide_intent}")
    if context.verified_facts:
        lines.append("\n【相关已核实事实】")
        for fact in context.verified_facts:
            flag = "✓" if fact.verified else "?"
            lines.append(f"- [{flag}] {fact.statement}")
    if context.project_facts:
        lines.append("\n【相关项目事实】")
        for pfact in context.project_facts:
            suffix = f" {pfact.unit}" if pfact.unit else ""
            lines.append(f"- {pfact.label}: {pfact.value}{suffix}")
    if context.relevant_assets:
        lines.append("\n【相关素材】")
        for asset in context.relevant_assets:
            desc = asset.description or asset.filename
            lines.append(f"- [{asset.asset_type.value}] {asset.filename}: {desc}")
    if context.relevant_citations:
        lines.append("\n【相关引用】")
        for cite in context.relevant_citations:
            page = f", p.{cite.page_number}" if cite.page_number else ""
            quote = f' — "{cite.quote}"' if cite.quote else ""
            lines.append(f"- {cite.document_name}{page}{quote}")
    if context.template_schema is not None:
        lines.append(
            f"\n【版式语义契约】\nschema_id={context.template_schema.id}"
        )
    return ContextBudgetManager().trim_prompt_block("\n".join(lines), stage="slide_generate")

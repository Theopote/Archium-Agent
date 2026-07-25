from pathlib import Path

path = Path("archium/ui/mission_panel.py")
text = path.read_text(encoding="utf-8")
start = text.find("    # Vision loop stays under selected")
end = text.find("\ndef _render_autonomous_research_section")
if start < 0 or end < 0 or end <= start:
    raise SystemExit(f"markers not found: {start=} {end=}")

replacement = '''    # Visual Thinking slots under each direction
    from archium.ui.components.visual_thinking_panel import render_visual_thinking_panel

    settings = get_ui_effective_settings()
    for direction in directions:
        badge = {
            ConceptDirectionStatus.SELECTED: "已选中",
            ConceptDirectionStatus.DRAFT: "草稿",
            ConceptDirectionStatus.ARCHIVED: "已归档",
        }.get(direction.status, direction.status.value)
        with st.expander(
            f"Visual Thinking · {direction.title} · {badge}",
            expanded=direction.status == ConceptDirectionStatus.SELECTED,
        ):
            render_visual_thinking_panel(
                direction,
                key_prefix=f"{key_prefix}_vt",
                settings=settings,
            )


'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
print("ok", start, end)

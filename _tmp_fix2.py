from pathlib import Path
import re

root = Path(r"C:\Users\navib\Desktop\development\Archium-Agent")

# slide_preview_service: bool() wrap
p = root / "archium/application/visual/slide_preview_service.py"
t = p.read_text(encoding="utf-8")
old = "            return (max(pixels) - min(pixels)) < 12"
new = "            return bool((max(pixels) - min(pixels)) < 12)"
if old not in t:
    raise SystemExit("slide_preview bool line missing")
p.write_text(t.replace(old, new), encoding="utf-8")
print("slide_preview_service")

# trace.py
p = root / "archium/infrastructure/llm/trace.py"
t = p.read_text(encoding="utf-8")
old = """            if callable(list_fn):
                return list_fn(limit)"""
new = """            if callable(list_fn):
                result = list_fn(limit)
                return list(result) if result is not None else []"""
if old not in t:
    raise SystemExit("trace list_recent missing")
t = t.replace(old, new)
old = """def _as_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None"""
new = """def _as_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type,call-overload]
    except (TypeError, ValueError):
        return None"""
# Prefer cast-based fix without ignore if possible
new = """def _as_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, (str, bytes, bytearray)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None"""
if old not in t:
    raise SystemExit("_as_optional_int missing")
p.write_text(t.replace(old, new), encoding="utf-8")
print("trace.py")

# design_process_pointer: cast loaded
p = root / "archium/application/process/design_process_pointer.py"
t = p.read_text(encoding="utf-8")
if "from typing import" in t and "cast" not in t.split("from typing import",1)[1].split("\n",1)[0]:
    t = re.sub(r"from typing import ([^\n]+)", lambda m: f"from typing import {m.group(1)}, cast" if "cast" not in m.group(1) else m.group(0), t, count=1)
elif "from typing import" not in t:
    t = t.replace("from __future__ import annotations\n", "from __future__ import annotations\n\nfrom typing import cast\n", 1)
old = """    loaded = directions_repo.get(exploration.selected_direction_id)
    if loaded is None or loaded.status == ConceptDirectionStatus.ARCHIVED:
        return None
    return loaded"""
new = """    loaded = directions_repo.get(exploration.selected_direction_id)
    if loaded is None or loaded.status == ConceptDirectionStatus.ARCHIVED:
        return None
    return cast(ConceptDirection, loaded)"""
if old not in t:
    raise SystemExit("design_process_pointer return missing")
p.write_text(t.replace(old, new), encoding="utf-8")
print("design_process_pointer")

# workflow_orchestration_service: active_stage None + reflection typing
p = root / "archium/application/orchestration/workflow_orchestration_service.py"
t = p.read_text(encoding="utf-8")
# Fix line 172 - maybe active_stage() return is Optional and chained .stage
# Error: Item "None" of "OrchestrationStageSpec | None" has no attribute "stage"
# Code: plan.active_stage().stage.value if plan.active_stage() else ""
# The issue is plan.active_stage().stage is evaluated before the ternary's else in some analysis?
# Actually: `x.stage if x else ""` when x is Optional - mypy should narrow. Unless it's:
# `(plan.active_stage().stage.value if plan.active_stage() else "")` - mypy may not narrow across two calls.
old = '                    stage=(plan.active_stage().stage.value if plan.active_stage() else ""),'
new = '''                    stage=(
                        (_active.stage.value if (_active := plan.active_stage()) is not None else "")
                    ),'''
if old not in t:
    # try to find nearby
    if "plan.active_stage()" in t:
        print("orchestration stage line variant; searching...")
        for i,l in enumerate(t.splitlines(),1):
            if "active_stage()" in l and "stage=" in l:
                print(i, l)
    else:
        raise SystemExit("orchestration stage line missing")
else:
    t = t.replace(old, new)

old = """                evidence_refs=[
                    str(item)
                    for item in (reflection.get(\"top_risks\") or [])[:3]
                    if str(item).strip()
                ],"""
new = """                evidence_refs=[
                    str(item)
                    for item in list(reflection.get(\"top_risks\") or [])[:3]
                    if str(item).strip()
                ],"""
# Better fix for index on object:
if 'reflection.get("top_risks")' in t:
    t = t.replace(
        '(reflection.get("top_risks") or [])[:3]',
        '(list(reflection["top_risks"]) if isinstance(reflection.get("top_risks"), list) else [])[:3]',
    )
p.write_text(t, encoding="utf-8")
print("workflow_orchestration_service")

# rag_preview_panel
p = root / "archium/ui/rag_preview_panel.py"
t = p.read_text(encoding="utf-8")
old = """            arch = chunk.metadata.get("architectural_type")
            if not arch:
                arch = getattr(chunk, "architectural_type", None)
                arch = arch.value if hasattr(arch, "value") else arch
            rows.append(
                {
"""
# Need to see exact keys - use safer rewrite of the arch block
old = """            arch = chunk.metadata.get("architectural_type")
            if not arch:
                arch = getattr(chunk, "architectural_type", None)
                arch = arch.value if hasattr(arch, "value") else arch
"""
new = """            arch = chunk.metadata.get("architectural_type")
            if not arch:
                arch_attr = getattr(chunk, "architectural_type", None)
                if arch_attr is not None and hasattr(arch_attr, "value"):
                    arch = arch_attr.value
                else:
                    arch = arch_attr
            arch_label: float | str = str(arch) if arch is not None else "—"
"""
# Wait - the Chinese dash might be different. Don't invent arch_label key wrong.
# Just fix union-attr and cast arch for dict
new = """            arch = chunk.metadata.get("architectural_type")
            if not arch:
                arch_attr = getattr(chunk, "architectural_type", None)
                if arch_attr is not None and hasattr(arch_attr, "value"):
                    arch = getattr(arch_attr, "value")
                else:
                    arch = arch_attr
            arch_cell: float | str = arch if isinstance(arch, (float, str)) else (str(arch) if arch is not None else "")
"""
if old not in t:
    raise SystemExit("rag arch block missing")
t = t.replace(old, new)
# replace arch or "..." in dict with arch_cell
t2 = re.sub(r'("(?:[^"]|\\")*"\s*:\s*)arch or ("[^"]*")', r'\1arch_cell or \2', t, count=1)
# simpler: find line with arch or
lines = t.splitlines()
for i,l in enumerate(lines):
    if "arch or" in l and ":" in l:
        lines[i] = l.replace("arch or", "arch_cell or", 1)
        break
else:
    raise SystemExit("arch or line missing")
p.write_text("\n".join(lines) + ("\n" if t.endswith("\n") else ""), encoding="utf-8")
print("rag_preview_panel")

# Remove unused type: ignore
for path, needle in [
    (root / "archium/ui/pages/template_induction.py", "def _render_phase35_signoff(service, workspace, presentation, induction) -> None:  # type: ignore[no-untyped-def]"),
    (root / "archium/ui/pages/template_induction.py", "def _render_publication_readiness(presentation, induction) -> None:  # type: ignore[no-untyped-def]"),
    (root / "archium/ui/studio/slide_canvas_enhanced.py", "def _render_content_slide_preview(slide) -> None:  # type: ignore[no-untyped-def]"),
    (root / "archium/ui/studio/slide_canvas_enhanced.py", "def _render_empty_preview_placeholder(*, has_layout_plan: bool = False, slide=None) -> None:  # type: ignore[no-untyped-def]"),
]:
    t = path.read_text(encoding="utf-8")
    if needle not in t:
        print("WARN missing", path.name, needle[:50])
        continue
    fixed = needle.replace("  # type: ignore[no-untyped-def]", "")
    path.write_text(t.replace(needle, fixed), encoding="utf-8")
    print("removed unused-ignore", path.name)

# planning_service cast
p = root / "archium/ui/planning_service.py"
t = p.read_text(encoding="utf-8")
if "from typing import" in t and "cast" not in t:
    t = re.sub(r"from typing import ([^\n]+)", r"from typing import \1, cast", t, count=1)
elif "cast" not in t:
    # maybe already has typing imports with cast elsewhere
    pass
# check ArtifactOutput return
if "return result.output" in t and "raise WorkflowError(f\"{kind_label}" in t:
    t = t.replace(
        """    if result.output is None:
        raise WorkflowError(f"{kind_label}任务未返回产物")
    return result.output""",
        """    if result.output is None:
        raise WorkflowError(f"{kind_label}任务未返回产物")
    return cast("ArtifactOutput", result.output)""",
    )
    # encoding of Chinese may differ - use regex
    t = p.read_text(encoding="utf-8")
    if "from typing import" in t and not re.search(r"from typing import[^\n]*\bcast\b", t):
        t = re.sub(r"(from typing import [^\n]+)", lambda m: m.group(1) if "cast" in m.group(1) else m.group(1) + ", cast", t, count=1)
    t = re.sub(
        r"(if result\.output is None:\n\s+raise WorkflowError\([^\n]+\)\n\s+)return result\.output",
        r"\1return cast(\"ArtifactOutput\", result.output)",
        t,
        count=1,
    )
    p.write_text(t, encoding="utf-8")
    print("planning_service")
else:
    print("planning_service pattern check failed, trying regex only")
    t = p.read_text(encoding="utf-8")
    if not re.search(r"from typing import[^\n]*\bcast\b", t):
        if "from typing import" in t:
            t = re.sub(r"(from typing import [^\n]+)", lambda m: m.group(1) if "cast" in m.group(1) else m.group(1) + ", cast", t, count=1)
        else:
            t = t.replace("from __future__ import annotations\n", "from __future__ import annotations\n\nfrom typing import cast\n", 1)
    t2, n = re.subn(
        r"(if result\.output is None:\n\s+raise WorkflowError\([^\n]+\)\n\s+)return result\.output",
        r"\1return cast(\"ArtifactOutput\", result.output)",
        t,
        count=1,
    )
    if n != 1:
        raise SystemExit(f"planning_service replace count={n}")
    p.write_text(t2, encoding="utf-8")
    print("planning_service regex ok")

# concept_exploration: list() wrap
p = root / "archium/ui/pages/concept_exploration.py"
t = p.read_text(encoding="utf-8")
# find function returning directions at 279
lines = t.splitlines()
# look at function signature above 279
for i in range(250, 280):
    print(f"CE{i+1}:{lines[i]}")

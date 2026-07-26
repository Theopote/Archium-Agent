from pathlib import Path
import re

root = Path(r"C:\Users\navib\Desktop\development\Archium-Agent")

# Fix planning_service cast syntax + import
p = root / "archium/ui/planning_service.py"
t = p.read_text(encoding="utf-8")
# Fix bad escaped cast
t = t.replace('return cast(\\"ArtifactOutput\\", result.output)', 'return cast("ArtifactOutput", result.output)')
t = t.replace("return cast(\\\"ArtifactOutput\\\", result.output)", 'return cast("ArtifactOutput", result.output)')
if 'return cast("ArtifactOutput", result.output)' not in t:
    # show nearby
    for i,l in enumerate(t.splitlines(),1):
        if "result.output" in l and ("return" in l or "cast" in l):
            print(repr(l))
    raise SystemExit("cast line still wrong")
if not re.search(r"from typing import[^\n]*\bcast\b", t) and "from typing import cast" not in t:
    # insert after future
    if "from __future__ import annotations\n" in t:
        t = t.replace(
            "from __future__ import annotations\n",
            "from __future__ import annotations\n\nfrom typing import cast\n",
            1,
        )
    else:
        t = "from typing import cast\n" + t
p.write_text(t, encoding="utf-8")
print("planning_service fixed")

# Add TypedDict key
p = root / "archium/workflow/planning_state.py"
t = p.read_text(encoding="utf-8")
needle = "    warnings: Annotated[list[str], operator.add]\n    mission_validation: dict[str, Any] | None\n"
insert = "    warnings: Annotated[list[str], operator.add]\n    autonomous_research_item_count: int\n    mission_validation: dict[str, Any] | None\n"
if "autonomous_research_item_count" not in t:
    if needle not in t:
        raise SystemExit("typeddict needle missing")
    t = t.replace(needle, insert)
    p.write_text(t, encoding="utf-8")
    print("planning_state key added")
else:
    print("planning_state key already present")

# genesis: ensure nested import has as_session_state
p = root / "archium/ui/pages/project_genesis.py"
t = p.read_text(encoding="utf-8")
t2 = t.replace(
    "from archium.ui.context_navigation import dispatch_next_best_action",
    "from archium.ui.context_navigation import as_session_state, dispatch_next_best_action",
)
p.write_text(t2, encoding="utf-8")
print("genesis nested import")

# compile-check key files
import py_compile
for rel in [
    "archium/ui/planning_service.py",
    "archium/application/context/workflow_navigation.py",
    "archium/ui/rag_preview_panel.py",
    "archium/application/orchestration/workflow_orchestration_service.py",
    "archium/workflow/workstream_execution_graph.py",
    "archium/application/process/design_process_pointer.py",
]:
    py_compile.compile(str(root / rel), doraise=True)
    print("syntax ok", rel)

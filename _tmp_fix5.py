from pathlib import Path
import re

root = Path(r"C:\Users\navib\Desktop\development\Archium-Agent")

# Remove unused as_session_state from context_navigation; point UI imports at workflow_navigation
p = root / "archium/ui/context_navigation.py"
t = p.read_text(encoding="utf-8")
t = t.replace(
    """from archium.application.context.workflow_navigation import (
    SessionStateLike,
    apply_workflow_entry,
    as_session_state,
)""",
    """from archium.application.context.workflow_navigation import (
    SessionStateLike,
    apply_workflow_entry,
)""",
)
p.write_text(t, encoding="utf-8")

# Update callers that imported as_session_state from context_navigation
patches = [
    (
        root / "archium/ui/workspace_mode_chrome.py",
        "from archium.ui.context_navigation import as_session_state, navigate_workflow_entry",
        "from archium.application.context.workflow_navigation import as_session_state\nfrom archium.ui.context_navigation import navigate_workflow_entry",
    ),
    (
        root / "archium/ui/pages/flow/generate.py",
        "from archium.ui.context_navigation import as_session_state, dispatch_next_best_action",
        "from archium.application.context.workflow_navigation import as_session_state\nfrom archium.ui.context_navigation import dispatch_next_best_action",
    ),
    (
        root / "archium/ui/pages/project_genesis.py",
        "from archium.ui.context_navigation import as_session_state, dispatch_next_best_action",
        "from archium.application.context.workflow_navigation import as_session_state\nfrom archium.ui.context_navigation import dispatch_next_best_action",
    ),
]
for path, old, new in patches:
    t = path.read_text(encoding="utf-8")
    if old not in t:
        print("WARN missing", path.name, old[:60])
    else:
        path.write_text(t.replace(old, new), encoding="utf-8")
        print("patched", path.name)

# project_knowledge_profile multi-import
p = root / "archium/ui/project_knowledge_profile.py"
t = p.read_text(encoding="utf-8")
if "as_session_state," in t and "from archium.ui.context_navigation import" in t:
    # remove as_session_state from the import block and add workflow_navigation import nearby
    t = t.replace("\n    as_session_state,", "", 1)
    if "from archium.application.context.workflow_navigation import as_session_state" not in t:
        t = t.replace(
            "from archium.ui.context_navigation import (",
            "from archium.application.context.workflow_navigation import as_session_state\nfrom archium.ui.context_navigation import (",
            1,
        )
    p.write_text(t, encoding="utf-8")
    print("patched project_knowledge_profile")

# Fix orchestration list(object)
p = root / "archium/application/orchestration/workflow_orchestration_service.py"
t = p.read_text(encoding="utf-8")
old = '(list(reflection["top_risks"]) if isinstance(reflection.get("top_risks"), list) else [])[:3]'
new = '(cast(list[object], reflection["top_risks"]) if isinstance(reflection.get("top_risks"), list) else [])[:3]'
# Need cast imported
if "from typing import" in t:
    m = re.search(r"from typing import ([^\n]+)", t)
    if m and "cast" not in m.group(1):
        t = t.replace(m.group(0), m.group(0) + ", cast" if False else f"from typing import {m.group(1)}, cast")
        # avoid double
        t = re.sub(r"from typing import ([^\n]+), cast, cast", r"from typing import \1, cast", t)
if old not in t:
    # show line
    for i,l in enumerate(t.splitlines(),1):
        if "top_risks" in l:
            print(i, l)
    raise SystemExit("top_risks line missing")
# Simpler without cast on list():
new = '([item for item in reflection.get("top_risks", [])] if isinstance(reflection.get("top_risks"), list) else [])[:3]'
# even simpler:
new = """(
                    [
                        item
                        for item in (
                            reflection.get("top_risks")
                            if isinstance(reflection.get("top_risks"), list)
                            else []
                        )
                    ][:3]
                )"""
# Wait that changes structure of evidence_refs comprehension. Keep simple:
fix = '''                evidence_refs=[
                    str(item)
                    for item in (
                        reflection["top_risks"]
                        if isinstance(reflection.get("top_risks"), list)
                        else []
                    )[:3]
                    if str(item).strip()
                ],'''
# Find and replace the evidence_refs block
pat = re.compile(
    r"evidence_refs=\[\s*str\(item\)\s*for item in \([^)]+\)\[:3\]\s*if str\(item\)\.strip\(\)\s*\],",
    re.S,
)
m = pat.search(t)
if not m:
    # try current one-liner form
    pat2 = re.compile(r"evidence_refs=\[\n(?:.*\n)*?\s*\],", re.M)
    for i,l in enumerate(t.splitlines(),1):
        if "evidence_refs" in l or "top_risks" in l:
            if 615 <= i <= 630:
                print(f"{i}:{l}")
else:
    t = pat.sub(fix.rstrip(","), t)  # messy

# Direct line replace of the for-item-in expression
t = p.read_text(encoding="utf-8")
t2 = t.replace(
    '(list(reflection["top_risks"]) if isinstance(reflection.get("top_risks"), list) else [])[:3]',
    '(reflection["top_risks"] if isinstance(reflection.get("top_risks"), list) else [])[:3]',
)
if t2 == t:
    raise SystemExit("could not replace list(reflection...)")
p.write_text(t2, encoding="utf-8")
print("orchestration top_risks fixed")

# Fix UP034 parentheses manually for clarity
t = p.read_text(encoding="utf-8")
t = t.replace(
    """                    stage=(
                        (_active.stage.value if (_active := plan.active_stage()) is not None else "")
                    ),""",
    """                    stage=(
                        _active.stage.value if (_active := plan.active_stage()) is not None else ""
                    ),""",
)
p.write_text(t, encoding="utf-8")

# Fix rag getattr B009
p = root / "archium/ui/rag_preview_panel.py"
t = p.read_text(encoding="utf-8")
t = t.replace("                    arch = getattr(arch_attr, \"value\")", "                    arch = arch_attr.value")
p.write_text(t, encoding="utf-8")
print("rag B009 fixed")

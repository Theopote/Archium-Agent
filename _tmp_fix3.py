from pathlib import Path
import re

root = Path(r"C:\Users\navib\Desktop\development\Archium-Agent")

# concept_exploration return list()
p = root / "archium/ui/pages/concept_exploration.py"
t = p.read_text(encoding="utf-8")
# Find the specific return directions after the compare block — change final return
# Safer: locate function def and only last return
# Use unique context
old = """        except Exception as exc:
            st.error(format_user_error(exc))
    return directions


def _render_selected_direction_vision"""
new = """        except Exception as exc:
            st.error(format_user_error(exc))
    return list(directions)


def _render_selected_direction_vision"""
if old not in t:
    raise SystemExit("concept_exploration return context missing")
p.write_text(t.replace(old, new), encoding="utf-8")
print("concept_exploration")

# planning_nodes TypedDict — find PlanningWorkflowState
found = None
for p in (root / "archium").rglob("*.py"):
    txt = p.read_text(encoding="utf-8")
    if "class PlanningWorkflowState" in txt or "PlanningWorkflowState =" in txt:
        found = p
        print("Found PlanningWorkflowState in", p)
        for i,l in enumerate(txt.splitlines(),1):
            if "PlanningWorkflowState" in l or "autonomous_research" in l:
                if i < 80 or "autonomous" in l or "class Planning" in l or "total=False" in l:
                    print(f"{i}:{l}")
print("---")

# workstream_execution_graph cast config
p = root / "archium/workflow/workstream_execution_graph.py"
t = p.read_text(encoding="utf-8")
if "RunnableConfig" not in t:
    # cast config as Any
    if "from typing import" in t:
        if "Any" not in re.search(r"from typing import ([^\n]+)", t).group(1):
            t = re.sub(r"from typing import ([^\n]+)", lambda m: m.group(0) if "Any" in m.group(1) else f"from typing import {m.group(1)}, Any", t, count=1)
    old = """        config = {"configurable": {"thread_id": thread_id}}
        result = self._compiled.invoke(state, config=config)"""
    new = """        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
        result = self._compiled.invoke(state, config=config)  # type: ignore[call-overload]"""
    # Prefer cast without ignore:
    new = """        config: Any = {"configurable": {"thread_id": thread_id}}
        result = self._compiled.invoke(state, config=config)"""
    if old not in t:
        raise SystemExit("workstream invoke block missing")
    # ensure Any imported
    if not re.search(r"from typing import[^\n]*\bAny\b", t):
        if "from typing import" in t:
            t = re.sub(r"(from typing import [^\n]+)", lambda m: m.group(1) if "Any" in m.group(1) else m.group(1) + ", Any", t, count=1)
        else:
            t = t.replace("from __future__ import annotations\n", "from __future__ import annotations\n\nfrom typing import Any\n", 1)
    t = t.replace(old, new)
    p.write_text(t, encoding="utf-8")
    print("workstream_execution_graph")
else:
    print("RunnableConfig already present?")

# Verify key files for as_session_state
for rel in [
    "archium/ui/project_knowledge_profile.py",
    "archium/ui/pages/project_genesis.py",
    "archium/ui/pages/flow/generate.py",
    "archium/ui/workspace_mode_chrome.py",
    "archium/ui/pages/project_mission.py",
]:
    t = (root / rel).read_text(encoding="utf-8")
    print(rel, "as_session_state:" , "as_session_state" in t, "raw st.session_state to helpers?")
    for i,l in enumerate(t.splitlines(),1):
        if "dispatch_next_best_action" in l or "navigate_workflow_entry" in l or "apply_workflow_entry" in l or "sync_mission_step" in l or "as_session_state" in l:
            if "import" in l or "as_session_state" in l or "st.session_state" in l:
                print(f"  {i}:{l.strip()[:140]}")

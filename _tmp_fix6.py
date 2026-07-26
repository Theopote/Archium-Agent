from pathlib import Path

root = Path(r"C:\Users\navib\Desktop\development\Archium-Agent")

# workspace_mode_chrome
p = root / "archium/ui/workspace_mode_chrome.py"
t = p.read_text(encoding="utf-8")
old = """        if entry is not None:
            from archium.ui.context_navigation import navigate_workflow_entry

            navigate_workflow_entry(st.session_state, entry)"""
new = """        if entry is not None:
            from archium.application.context.workflow_navigation import as_session_state
            from archium.ui.context_navigation import navigate_workflow_entry

            navigate_workflow_entry(as_session_state(st.session_state), entry)"""
if old not in t:
    raise SystemExit("workspace block missing")
p.write_text(t.replace(old, new), encoding="utf-8")
print("workspace ok")

# generate.py
p = root / "archium/ui/pages/flow/generate.py"
t = p.read_text(encoding="utf-8")
old = """    from archium.ui.context_navigation import dispatch_next_best_action

    try:"""
new = """    from archium.application.context.workflow_navigation import as_session_state
    from archium.ui.context_navigation import dispatch_next_best_action

    try:"""
if old not in t:
    raise SystemExit("generate import missing")
t = t.replace(old, new, 1)
old = """                dispatch_next_best_action(
                    session,
                    st.session_state,
                    readiness.suggested_action,"""
new = """                dispatch_next_best_action(
                    session,
                    as_session_state(st.session_state),
                    readiness.suggested_action,"""
if old not in t:
    raise SystemExit("generate dispatch missing")
p.write_text(t.replace(old, new), encoding="utf-8")
print("generate ok")

# project_genesis apply + dispatch
p = root / "archium/ui/pages/project_genesis.py"
t = p.read_text(encoding="utf-8")
old = """            from archium.application.context.workflow_navigation import apply_workflow_entry"""
new = """            from archium.application.context.workflow_navigation import (
                apply_workflow_entry,
                as_session_state,
            )"""
if old not in t:
    raise SystemExit("genesis apply import missing")
t = t.replace(old, new, 1)
old = """                    apply_workflow_entry(st.session_state, entry)"""
new = """                    apply_workflow_entry(as_session_state(st.session_state), entry)"""
if old not in t:
    raise SystemExit("genesis apply call missing")
t = t.replace(old, new, 1)
old = """    from archium.ui.context_navigation import dispatch_next_best_action
    from archium.ui.llm_settings import get_ui_effective_settings"""
new = """    from archium.application.context.workflow_navigation import as_session_state
    from archium.ui.context_navigation import dispatch_next_best_action
    from archium.ui.llm_settings import get_ui_effective_settings"""
if old not in t:
    raise SystemExit("genesis dispatch import missing")
t = t.replace(old, new, 1)
old = """        result = dispatch_next_best_action(
            session,
            st.session_state,
            action,"""
new = """        result = dispatch_next_best_action(
            session,
            as_session_state(st.session_state),
            action,"""
if old not in t:
    raise SystemExit("genesis dispatch call missing")
p.write_text(t.replace(old, new, 1), encoding="utf-8")
print("genesis ok")

# project_knowledge_profile
p = root / "archium/ui/project_knowledge_profile.py"
t = p.read_text(encoding="utf-8")
old = """    from archium.ui.context_navigation import (
        dispatch_next_best_action,
        pending_fact_counts,
    )"""
new = """    from archium.application.context.workflow_navigation import as_session_state
    from archium.ui.context_navigation import (
        dispatch_next_best_action,
        pending_fact_counts,
    )"""
if old not in t:
    raise SystemExit("pkp import missing")
t = t.replace(old, new, 1)
old = """                    result = dispatch_next_best_action(
                        session,
                        st.session_state,
                        action.action,"""
new = """                    result = dispatch_next_best_action(
                        session,
                        as_session_state(st.session_state),
                        action.action,"""
if old not in t:
    raise SystemExit("pkp dispatch missing")
p.write_text(t.replace(old, new, 1), encoding="utf-8")
print("pkp ok")

# project_mission
p = root / "archium/ui/pages/project_mission.py"
t = p.read_text(encoding="utf-8")
old = """        from archium.application.context.workflow_navigation import sync_mission_step_from_context

        sync_mission_step_from_context(session, project_id, st.session_state)"""
new = """        from archium.application.context.workflow_navigation import (
            as_session_state,
            sync_mission_step_from_context,
        )

        sync_mission_step_from_context(
            session, project_id, as_session_state(st.session_state)
        )"""
if old not in t:
    raise SystemExit("mission block missing")
p.write_text(t.replace(old, new), encoding="utf-8")
print("mission ok")

import py_compile
for rel in [
    "archium/ui/workspace_mode_chrome.py",
    "archium/ui/pages/flow/generate.py",
    "archium/ui/pages/project_genesis.py",
    "archium/ui/project_knowledge_profile.py",
    "archium/ui/pages/project_mission.py",
]:
    py_compile.compile(str(root / rel), doraise=True)
    print("syntax", rel)

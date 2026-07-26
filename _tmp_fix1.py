from pathlib import Path
import re

root = Path(r"C:\Users\navib\Desktop\development\Archium-Agent")

# --- 1) workflow_navigation.py: SessionStateLike -> MutableMapping ---
wn = root / "archium/application/context/workflow_navigation.py"
text = wn.read_text(encoding="utf-8")
old = '''from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.context.next_action_selector import resolve_workflow_entry
from archium.application.context.project_context_builder import build_project_context
from archium.application.context.types import WorkflowEntryDispatch
from archium.application.fact_ledger_service import FactLedgerService


class SessionStateLike(Protocol):
    """Streamlit session_state-compatible mapping (stubs are not MutableMapping)."""

    def __getitem__(self, key: str, /) -> Any: ...
    def __setitem__(self, key: str, value: Any, /) -> None: ...
    def get(self, key: str, default: Any = None, /) -> Any: ...
'''
new = '''from collections.abc import MutableMapping
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.context.next_action_selector import resolve_workflow_entry
from archium.application.context.project_context_builder import build_project_context
from archium.application.context.types import WorkflowEntryDispatch
from archium.application.fact_ledger_service import FactLedgerService

# Streamlit SessionStateProxy is dict-like at runtime; stubs disagree with Protocol.get.
SessionStateLike = MutableMapping[str, Any]


def as_session_state(state: object) -> SessionStateLike:
    """Narrow Streamlit session_state / dict to a mutable mapping for helpers."""
    return cast(SessionStateLike, state)
'''
if old not in text:
    raise SystemExit("workflow_navigation imports/Protocol block not found")
text = text.replace(old, new)
wn.write_text(text, encoding="utf-8")
print("updated workflow_navigation.py")

# --- 2) context_navigation.py: re-export as_session_state ---
cn = root / "archium/ui/context_navigation.py"
ct = cn.read_text(encoding="utf-8")
ct2 = ct.replace(
    """from archium.application.context.workflow_navigation import (
    SessionStateLike,
    apply_workflow_entry,
)""",
    """from archium.application.context.workflow_navigation import (
    SessionStateLike,
    apply_workflow_entry,
    as_session_state,
)""",
)
if ct2 == ct:
    raise SystemExit("context_navigation import block not found")
cn.write_text(ct2, encoding="utf-8")
print("updated context_navigation.py imports")

# --- 3) Call sites: wrap st.session_state with as_session_state ---
replacements = [
    (
        root / "archium/ui/workspace_mode_chrome.py",
        "navigate_workflow_entry(st.session_state, entry)",
        "from archium.ui.context_navigation import navigate_workflow_entry\n",
    ),
]
# More systematic: patch known call patterns
call_site_patches = [
    (
        root / "archium/ui/workspace_mode_chrome.py",
        "navigate_workflow_entry(st.session_state, entry)",
        "navigate_workflow_entry(as_session_state(st.session_state), entry)",
        "from archium.ui.context_navigation import navigate_workflow_entry",
        "from archium.ui.context_navigation import as_session_state, navigate_workflow_entry",
    ),
    (
        root / "archium/ui/pages/project_genesis.py",
        "apply_workflow_entry(st.session_state, entry)",
        "apply_workflow_entry(as_session_state(st.session_state), entry)",
        "from archium.application.context.workflow_navigation import apply_workflow_entry",
        "from archium.application.context.workflow_navigation import apply_workflow_entry, as_session_state",
    ),
    (
        root / "archium/ui/pages/project_mission.py",
        "sync_mission_step_from_context(session, project_id, st.session_state)",
        "sync_mission_step_from_context(session, project_id, as_session_state(st.session_state))",
        "from archium.application.context.workflow_navigation import sync_mission_step_from_context",
        "from archium.application.context.workflow_navigation import as_session_state, sync_mission_step_from_context",
    ),
]

for path, old_call, new_call, old_imp, new_imp in call_site_patches:
    t = path.read_text(encoding="utf-8")
    if old_call not in t:
        raise SystemExit(f"call not found in {path}: {old_call}")
    t = t.replace(old_call, new_call)
    if old_imp in t:
        t = t.replace(old_imp, new_imp)
    elif "as_session_state" not in t:
        raise SystemExit(f"import not found in {path}")
    path.write_text(t, encoding="utf-8")
    print("patched", path.name)

# dispatch_next_best_action(session, st.session_state, ...) sites
for path in [
    root / "archium/ui/project_knowledge_profile.py",
    root / "archium/ui/pages/project_genesis.py",
    root / "archium/ui/pages/flow/generate.py",
]:
    t = path.read_text(encoding="utf-8")
    # ensure import
    if "as_session_state" not in t:
        if "from archium.ui.context_navigation import dispatch_next_best_action" in t:
            t = t.replace(
                "from archium.ui.context_navigation import dispatch_next_best_action",
                "from archium.ui.context_navigation import as_session_state, dispatch_next_best_action",
            )
        elif "from archium.ui.context_navigation import (" in t:
            # multi-import block — insert as_session_state
            t = t.replace(
                "from archium.ui.context_navigation import (",
                "from archium.ui.context_navigation import (\n    as_session_state,",
                1,
            )
        else:
            # try after dispatch import multiline
            m = re.search(r"from archium\.ui\.context_navigation import \(([^)]*)\)", t, re.S)
            if m:
                inner = m.group(1)
                if "as_session_state" not in inner:
                    t = t[: m.start(1)] + "\n    as_session_state," + inner + t[m.end(1) :]
            else:
                raise SystemExit(f"cannot add as_session_state import in {path}")
    # replace st.session_state argument to dispatch_next_best_action — common pattern is second arg
    t2 = re.sub(
        r"(dispatch_next_best_action\(\s*[^,\n]+,\s*)st\.session_state",
        r"\1as_session_state(st.session_state)",
        t,
    )
    if t2 == t and "as_session_state(st.session_state)" not in t:
        # maybe multiline
        t2 = t.replace("st.session_state,", "as_session_state(st.session_state),", 1)
        # dangerous if first st.session_state isn't the dispatch arg — check nearby
        if "dispatch_next_best_action" not in t:
            raise SystemExit(f"no dispatch in {path}")
    path.write_text(t2, encoding="utf-8")
    print("patched dispatch site", path.name)

print("done phase1")

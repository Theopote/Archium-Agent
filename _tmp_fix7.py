from pathlib import Path
import re

# Fix orchestration index error
p = Path(r"C:\Users\navib\Desktop\development\Archium-Agent\archium\application\orchestration\workflow_orchestration_service.py")
t = p.read_text(encoding="utf-8")
old = """                evidence_refs=[
                    str(item)
                    for item in (reflection["top_risks"] if isinstance(reflection.get("top_risks"), list) else [])[:3]
                    if str(item).strip()
                ],"""
new = """                evidence_refs=[
                    str(item)
                    for item in (
                        reflection.get("top_risks")
                        if isinstance(reflection.get("top_risks"), list)
                        else []
                    )[:3]
                    if str(item).strip()
                ],"""
# Better: bind to local with proper narrowing
# Find a unique anchor near the append
if "evidence_refs=[" not in t or "top_risks" not in t:
    raise SystemExit("block missing")

# Replace using a more robust approach: insert locals before evidence_refs in that call
# Simpler cast:
new = """                evidence_refs=[
                    str(item)
                    for item in cast(list[object], reflection.get("top_risks") or [])[:3]
                    if str(item).strip()
                ],"""
if old not in t:
    # show current
    for i,l in enumerate(t.splitlines(),1):
        if 618 <= i <= 625:
            print(i, l)
    raise SystemExit("old evidence block not exact")

# ensure cast imported
if not re.search(r"from typing import[^\n]*\bcast\b", t) and "from typing import cast" not in t:
    if re.search(r"from typing import ", t):
        t = re.sub(r"(from typing import [^\n]+)", lambda m: m.group(0) if "cast" in m.group(1) else m.group(1).replace("from typing import ", "from typing import cast, ") if False else (m.group(0) if "cast" in m.group(0) else m.group(0).replace("import ", "import cast, ")), t, count=1)
    # cleaner:
    t = p.read_text(encoding="utf-8")
    m = re.search(r"from typing import ([^\n]+)", t)
    if m and "cast" not in m.group(1):
        t = t[:m.start(1)] + "cast, " + t[m.start(1):]
    elif not m:
        t = t.replace("from __future__ import annotations\n", "from __future__ import annotations\n\nfrom typing import cast\n", 1)

if old not in t:
    raise SystemExit("lost old after import edit")
t = t.replace(old, new)
p.write_text(t, encoding="utf-8")
print("orch fixed")

# List all no-untyped-def for potential quick annotate
text = Path(r"C:\Users\navib\Desktop\development\Archium-Agent\.mypy_out.txt").read_bytes().decode("utf-16")
for l in text.splitlines():
    if "no-untyped-def" in l:
        print(l)

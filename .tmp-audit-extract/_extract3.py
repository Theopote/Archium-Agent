# -*- coding: utf-8 -*-
import json
from pathlib import Path

p = Path(
    r"C:\Users\navib\.cursor\projects\c-Users-navib-Desktop-development-Archium-Agent"
    r"\agent-transcripts\8e0fbb4e-2ab2-4115-9c58-b2d3d884671f"
    r"\8e0fbb4e-2ab2-4115-9c58-b2d3d884671f.jsonl"
)
lines = p.read_text(encoding="utf-8").splitlines()
out = Path(__file__).resolve().parent
# Batch 15 conclusion + any open P0 verification summaries
want = [259]
# also find lines mentioning open P0 or 仍开放
for i, line in enumerate(lines, 1):
    if '"role":"assistant"' not in line[:80]:
        continue
    try:
        obj = json.loads(line)
    except Exception:
        continue
    content = obj.get("message", {}).get("content")
    texts = []
    if isinstance(content, list):
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                texts.append(c.get("text") or "")
    text = "\n".join(texts)
    if any(
        k in text
        for k in (
            "Batch 15",
            "仍开放",
            "open P0",
            "P0 仍",
            "对照仓库现状",
            "完成度",
            "问题 14",
            "问题 8",
            "问题 9",
            "问题 10",
            "问题 11",
        )
    ):
        if len(text) > 100:
            want.append(i)

want = sorted(set(want))
print("candidates", want)
for i in want:
    obj = json.loads(lines[i - 1])
    content = obj.get("message", {}).get("content")
    texts = []
    if isinstance(content, list):
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                texts.append(c.get("text") or "")
    text = "\n".join(texts)
    if not text:
        continue
    (out / f"extra-{i:03d}.md").write_text(text, encoding="utf-8")
    print(i, text.splitlines()[0][:100], "len", len(text))

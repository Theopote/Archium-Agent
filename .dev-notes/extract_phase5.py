import json
from pathlib import Path

transcript = Path(
    r"C:\Users\navib\.cursor\projects\c-Users-navib-Desktop-development-Archium-Agent"
    r"\agent-transcripts\6d9609f9-afc1-4c7b-9ee6-d384ef5e807e\6d9609f9-afc1-4c7b-9ee6-d384ef5e807e.jsonl"
)
with transcript.open(encoding="utf-8") as f:
    text = json.loads(f.readline())["message"]["content"][0]["text"]

for pat in [
    "RecoveredPageRegion",
    "SlideRecoveryResult",
    "HybridRenderScene",
    "页面恢复",
    "slide_recovery",
]:
    idx = text.find(pat)
    print(pat, idx)

start = text.find("Phase 5")
end = text.find("## 开发原则")
if end < 0:
    end = text.find("Phase 6")
out = Path(__file__).with_name("phase5-extract.txt")
chunk = text[start:end] if start >= 0 else "NOT FOUND"
out.write_text(chunk, encoding="utf-8")
print(f"Wrote {len(chunk)} chars")

idx = text.find("RecoveredPageRegion")
if idx >= 0:
    extra = Path(__file__).with_name("phase5-models.txt")
    extra.write_text(text[max(0, idx - 800) : idx + 3500], encoding="utf-8")
    print(f"Wrote models extract to {extra}")

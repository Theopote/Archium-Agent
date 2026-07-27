from zipfile import ZipFile
from pathlib import Path
import re
import shutil

root = Path(r"c:\Users\navib\Desktop\development\Archium-Agent")
pptx = root / "data/outputs/presentations/e48d0481-f625-48a7-b4b1-e1ee4163e76d/v1/presentation.pptx"
out = root / "docs/rehearsal/sessions/2026-07-27-playbook-e-1/evidence/pptx-slide1-texts.txt"
with ZipFile(pptx) as z:
    xml = z.read("ppt/slides/slide1.xml").decode("utf-8")
texts = re.findall(r"<a:t[^>]*>([^<]*)</a:t>", xml)
marker = "剧本E"
has = any(marker in t for t in texts)
out.write_text("\n".join(texts) + f"\n\nHAS_JU_BEN_E={has}\n", encoding="utf-8")
print("runs", len(texts), "HAS_JU_BEN_E", has)

src = Path(r"c:\Users\navib\AppData\Local\Temp\cursor\screenshots")
dst = root / "docs/rehearsal/sessions/2026-07-27-playbook-e-1/evidence"
for name in ("E1-selection-properties.png", "E2-after-align-undo-available.png"):
    p = src / name
    if p.exists():
        shutil.copy2(p, dst / name)
        print("copied", name)
    else:
        print("missing", name)

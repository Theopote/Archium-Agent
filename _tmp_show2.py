from pathlib import Path
import re

root = Path(r"C:\Users\navib\Desktop\development\Archium-Agent")

def show(path, start, end):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    print("====", Path(path).name, "====")
    for i in range(start, end+1):
        if 1 <= i <= len(lines):
            print(f"{i}:{lines[i-1]}")

show(root/"archium/ui/workspace_mode_chrome.py", 80, 100)
show(root/"archium/ui/pages/flow/generate.py", 50, 95)
show(root/"archium/ui/pages/project_genesis.py", 70, 110)
show(root/"archium/ui/pages/project_genesis.py", 430, 460)
show(root/"archium/ui/project_knowledge_profile.py", 215, 275)
show(root/"archium/ui/pages/project_mission.py", 730, 745)
show(root/"archium/application/context/workflow_navigation.py", 1, 45)

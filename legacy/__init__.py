"""Legacy / experimental modules (v0.1).

These modules are kept for backward compatibility and are decoupled from the
main v0.2 presentation workflow. Prefer ``archium`` or ``streamlit run app.py``.

Entry point: ``archium-legacy`` → ``legacy.main:main``
"""

from legacy.config import GEMINI_API_KEY, GEMINI_BASE_URL, GEMINI_MODEL, client, get_client
from legacy.file_manager import FileInfo, MoveResult, classify_files_with_ai, move_files, scan_folder
from legacy.main import ExecutionReport, StepResult, execute_plan, main, run_instruction
from legacy.ppt_generator import generate_presentation

__all__ = [
    "ExecutionReport",
    "FileInfo",
    "GEMINI_API_KEY",
    "GEMINI_BASE_URL",
    "GEMINI_MODEL",
    "MoveResult",
    "StepResult",
    "classify_files_with_ai",
    "client",
    "execute_plan",
    "generate_presentation",
    "get_client",
    "main",
    "move_files",
    "run_instruction",
    "scan_folder",
]

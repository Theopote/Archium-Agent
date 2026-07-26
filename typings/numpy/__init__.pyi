# Minimal stub so mypy --python-version 3.11 does not parse site-packages numpy 2.x stubs
from typing import Any

def __getattr__(name: str) -> Any: ...

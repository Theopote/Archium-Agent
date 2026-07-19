#!/usr/bin/env python3
"""Fail CI when critical service modules fall below per-file coverage floors."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COVERAGE_XML = REPO_ROOT / "coverage.xml"

# Floors are intentionally above the global 65% gate — see docs/ci-critical-coverage.md
CRITICAL_MODULE_FLOORS: dict[str, float] = {
    "archium/application/visual/transaction_executor.py": 75.0,
    "archium/application/project_deletion_service.py": 80.0,
    "archium/application/visual/layout_repair_service.py": 80.0,
    "archium/application/visual/visual_edit_service.py": 80.0,
    "archium/application/visual/asset_reference.py": 85.0,
    "archium/application/slide_history_service.py": 80.0,
    "archium/application/visual/visual_history_service.py": 80.0,
    "archium/application/content_adaptation_service.py": 80.0,
}


@dataclass(frozen=True)
class ModuleCoverage:
    filename: str
    line_rate: float
    floor: float

    @property
    def passed(self) -> bool:
        return self.line_rate + 1e-9 >= self.floor


def _normalize_filename(raw: str) -> str:
    return raw.replace("\\", "/").lstrip("./")


def load_module_rates(coverage_xml: Path) -> dict[str, float]:
    tree = ET.parse(coverage_xml)
    rates: dict[str, float] = {}
    for class_node in tree.findall(".//class"):
        filename = class_node.get("filename")
        line_rate = class_node.get("line-rate")
        if not filename or line_rate is None:
            continue
        rates[_normalize_filename(filename)] = float(line_rate) * 100.0
    return rates


def _resolve_rate(rates: dict[str, float], filename: str) -> float | None:
    normalized = _normalize_filename(filename)
    if normalized in rates:
        return rates[normalized]
    suffix = normalized.removeprefix("archium/")
    for key, value in rates.items():
        if _normalize_filename(key).endswith(suffix):
            return value
    return None


def evaluate(coverage_xml: Path = DEFAULT_COVERAGE_XML) -> list[ModuleCoverage]:
    if not coverage_xml.is_file():
        raise FileNotFoundError(f"Coverage report not found: {coverage_xml}")

    rates = load_module_rates(coverage_xml)
    results: list[ModuleCoverage] = []
    for filename, floor in sorted(CRITICAL_MODULE_FLOORS.items()):
        line_rate = _resolve_rate(rates, filename)
        if line_rate is None:
            raise KeyError(f"Critical module missing from coverage.xml: {filename}")
        results.append(ModuleCoverage(filename=filename, line_rate=line_rate, floor=floor))
    return results


def main() -> int:
    coverage_xml = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_COVERAGE_XML
    results = evaluate(coverage_xml)
    failures = [item for item in results if not item.passed]

    print("Critical module coverage gate")
    print(f"Source: {coverage_xml}")
    for item in results:
        status = "OK" if item.passed else "FAIL"
        print(f"  [{status}] {item.line_rate:5.1f}% (floor {item.floor:.0f}%)  {item.filename}")

    if failures:
        print("\nCritical services below floor — global 65% must not mask these gaps.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

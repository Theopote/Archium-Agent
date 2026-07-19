# -*- coding: utf-8 -*-
"""Validation script for composite operation implementation."""

import os
import re
from pathlib import Path


def check_file_exists(path: str, description: str) -> bool:
    full_path = Path(path)
    exists = full_path.exists()
    status = "OK" if exists else "FAIL"
    print(f"[{status}] {description}: {path}")
    return exists


def check_class_defined(path: str, class_name: str) -> bool:
    full_path = Path(path)
    if not full_path.exists():
        print(f"  [FAIL] Class {class_name} - file not found")
        return False

    try:
        content = full_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        print(f"  [FAIL] Class {class_name} - read error: {e}")
        return False

    pattern = rf'class {class_name}\b'
    found = re.search(pattern, content) is not None
    status = "OK" if found else "FAIL"
    print(f"  [{status}] Class {class_name} defined")
    return found


def check_method_defined(path: str, method_name: str) -> bool:
    full_path = Path(path)
    if not full_path.exists():
        return False

    try:
        content = full_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return False

    pattern = rf'def {method_name}\('
    found = re.search(pattern, content) is not None
    status = "OK" if found else "FAIL"
    print(f"    [{status}] Method {method_name}()")
    return found


def main():
    print("=" * 60)
    print("Composite Operation Implementation Validation")
    print("=" * 60)
    print()

    results = []

    print("1. Atomic Operations")
    results.append(check_file_exists(
        "archium/domain/visual/atomic_operation.py",
        "Atomic operation definitions"
    ))
    if results[-1]:
        results.append(check_class_defined(
            "archium/domain/visual/atomic_operation.py",
            "AtomicOperation"
        ))
        results.append(check_class_defined(
            "archium/domain/visual/atomic_operation.py",
            "LockOperation"
        ))
    print()

    print("2. Operation Decomposer")
    results.append(check_file_exists(
        "archium/application/visual/operation_decomposer.py",
        "Operation decomposer"
    ))
    if results[-1]:
        results.append(check_class_defined(
            "archium/application/visual/operation_decomposer.py",
            "OperationDecomposer"
        ))
        results.append(check_method_defined(
            "archium/application/visual/operation_decomposer.py",
            "decompose"
        ))
    print()

    print("3. Transaction Executor")
    results.append(check_file_exists(
        "archium/application/visual/transaction_executor.py",
        "Transaction executor"
    ))
    if results[-1]:
        results.append(check_class_defined(
            "archium/application/visual/transaction_executor.py",
            "TransactionExecutor"
        ))
        results.append(check_method_defined(
            "archium/application/visual/transaction_executor.py",
            "execute_transaction"
        ))
    print()

    print("4. Integration")
    results.append(check_file_exists(
        "archium/application/visual/visual_edit_service.py",
        "Visual edit service"
    ))
    if results[-1]:
        results.append(check_method_defined(
            "archium/application/visual/visual_edit_service.py",
            "_apply_composite_operation"
        ))
    print()

    print("5. Tests")
    results.append(check_file_exists(
        "tests/application/visual/test_composite_operations.py",
        "Composite operation tests"
    ))
    print()

    print("6. Documentation")
    results.append(check_file_exists(
        "docs/analysis/NLP_PARSING_EXECUTION_GAP_ANALYSIS.md",
        "Gap analysis"
    ))
    results.append(check_file_exists(
        "docs/implementation/COMPOSITE_OPERATIONS_IMPLEMENTATION.md",
        "Implementation report"
    ))
    print()

    print("=" * 60)
    print("Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0

    print(f"Checks passed: {passed}/{total} ({percentage:.1f}%)")
    print()

    if passed == total:
        print("SUCCESS: All validation checks passed!")
        return 0
    else:
        print(f"FAILURE: {total - passed} checks failed.")
        return 1


if __name__ == "__main__":
    exit(main())

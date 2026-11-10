"""Zero-dependency test runner (the VM has no pytest; CI installs it).

Usage: python3 tests/run_tests.py   — runs every test_* function.
Also compatible with: python3 -m pytest tests/
"""

import importlib
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(__file__))

MODULES = ["test_hands", "test_fresh", "test_stranger", "test_external", "test_fixes"]


def main():
    passed = failed = 0
    failures = []
    for name in MODULES:
        try:
            mod = importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        for attr in sorted(dir(mod)):
            if attr.startswith("test_"):
                fn = getattr(mod, attr)
                try:
                    fn()
                    passed += 1
                    print(f"PASS {name}.{attr}")
                except Exception:
                    failed += 1
                    failures.append(f"{name}.{attr}")
                    print(f"FAIL {name}.{attr}")
                    traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run all test_*.py scripts sequentially and report their status."""

import glob
import subprocess
import sys
from pathlib import Path


def run_script(script: Path) -> bool:
    """Execute a test script and return True if it passed."""
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    print(output)
    if proc.returncode != 0:
        return False
    if "Result check: PASS" in output:
        return True
    if "Result check: FAIL" in output:
        return False
    # If the script didn't print a result summary, assume failure
    return False


def main() -> int:
    test_scripts = sorted(Path('.').glob('test_*.py'))
    failed = []
    for script in test_scripts:
        print(f"=== Running {script} ===")
        if not run_script(script):
            failed.append(script)
    if failed:
        print("\nThe following tests failed:")
        for script in failed:
            print(f"- {script}")
        return 1
    print("\nAll tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

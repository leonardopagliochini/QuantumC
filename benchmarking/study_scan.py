#!/usr/bin/env python3
"""Scan CC and Ir for a study dataset.

Usage:
  python benchmarking/study_scan.py STUDY_NAME [options]

The script locates:
  benchmarking/<study>/<study>_dataset  (input .c files)
  benchmarking/<study>/<study>_results  (output CSV)

It invokes bench_tools/scan_cc_ir.py under the hood and writes
<study>_cc_ir.csv inside the study results directory.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH_DIR = ROOT / "benchmarking"
SCAN_SCRIPT = BENCH_DIR / "bench_tools" / "scan_cc_ir.py"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("study", help="Study name (folder under benchmarking/)")
    parser.add_argument("--cc", default="gcc", help="C compiler for Callgrind (default: gcc)")
    parser.add_argument("--arch", default=None, help="Optional architecture hint (e.g., x86-64)")
    parser.add_argument("--input-cmd", default=None, help="Optional stdin provided to the binary")
    parser.add_argument(
        "--progress",
        choices=["auto", "plain", "none"],
        default="auto",
        help="Progress display mode (forwarded to scan_cc_ir)",
    )
    parser.add_argument(
        "--show-stages",
        action="store_true",
        help="Show per-file stages (forwarded to scan_cc_ir)",
    )
    args = parser.parse_args()

    study = args.study
    dataset_dir = BENCH_DIR / study / f"{study}_dataset"
    results_dir = BENCH_DIR / study / f"{study}_results"

    if not dataset_dir.exists():
        raise SystemExit(f"Dataset directory not found: {dataset_dir}")
    results_dir.mkdir(parents=True, exist_ok=True)

    out_csv = results_dir / f"{study}_cc_ir.csv"

    cmd = [
        sys.executable,
        str(SCAN_SCRIPT),
        "--corpus", str(dataset_dir),
        "--cc", args.cc,
        "--progress", args.progress,
        "--out", str(out_csv),
    ]
    if args.arch:
        cmd.extend(["--arch", args.arch])
    if args.input_cmd:
        cmd.extend(["--input-cmd", args.input_cmd])
    if args.show_stages:
        cmd.append("--show-stages")

    print(f"[scan] Running: {' '.join(cmd)}")
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    print(f"[scan] CC/Ir CSV written to {out_csv}")


if __name__ == "__main__":
    main()

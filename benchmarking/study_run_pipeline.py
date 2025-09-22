#!/usr/bin/env python3
"""Run the full benchmarking pipeline for a single study.

This helper sequentially invokes the existing study entry points:
- study_generate.py
- study_benchmark.py
- study_analyze.py

The study name is the only required argument. Configuration files with the
standard names (benchmarking/study_*.cfg) are reused automatically.
"""

from __future__ import annotations

import argparse
import pathlib
import shlex
import subprocess
import sys
from typing import Sequence

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH_DIR = ROOT / "benchmarking"
GEN_SCRIPT = BENCH_DIR / "study_generate.py"
BENCH_SCRIPT = BENCH_DIR / "study_benchmark.py"
ANALYZE_SCRIPT = BENCH_DIR / "study_analyze.py"
GEN_CFG_PATH = BENCH_DIR / "study_generate.cfg"
ANALYZE_CFG_PATH = BENCH_DIR / "study_analyze.cfg"

def _sanitise_study(value: str) -> str:
    value = value.strip()
    if not value:
        raise SystemExit("Study name must be a non-empty string.")
    if any(ch in value for ch in "/\\"):
        raise SystemExit("Study name may not contain path separators.")
    if any(ch.isspace() for ch in value):
        raise SystemExit("Study name may not contain whitespace.")
    return value


def _run_step(label: str, args: Sequence[str]) -> None:
    printable = " ".join(shlex.quote(str(arg)) for arg in args)
    print(f"[pipeline] {label}: {printable}")
    subprocess.run(args, check=True, cwd=ROOT)


def _maybe_write_analysis_cfg(study: str) -> None:
    study_dir = BENCH_DIR / study
    if not study_dir.exists() or not ANALYZE_CFG_PATH.exists():
        return
    dest = study_dir / "study_analyze.cfg"
    if dest.exists():
        return
    text = ANALYZE_CFG_PATH.read_text(encoding="utf-8")
    dest.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run generate, benchmark, and analyze sequentially for a study.",
    )
    parser.add_argument("study", help="Study name (created under benchmarking/<study>/)")
    args = parser.parse_args()

    study = _sanitise_study(args.study)

    study_dir = BENCH_DIR / study

    if study_dir.exists():
        raise SystemExit(
            f"Study directory {study_dir} already exists. Remove it or choose a different study name before rerunning."
        )

    if not GEN_CFG_PATH.exists():
        raise SystemExit(f"Default generator config not found: {GEN_CFG_PATH}")

    _run_step(
        "generate",
        [
            sys.executable,
            str(GEN_SCRIPT),
            study,
            "--config",
            str(GEN_CFG_PATH),
        ],
    )

    if not study_dir.exists():
        raise SystemExit(
            f"Generation step did not create benchmarking/{study}/. Study pipeline aborting."
        )

    _maybe_write_analysis_cfg(study)

    _run_step("benchmark", [sys.executable, str(BENCH_SCRIPT), study])
    _run_step("analyze", [sys.executable, str(ANALYZE_SCRIPT), study])


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"[pipeline] step failed with exit code {exc.returncode}", file=sys.stderr)
        sys.exit(exc.returncode)

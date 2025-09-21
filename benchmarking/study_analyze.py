#!/usr/bin/env python3
"""Generate analytical plots for a study.

Usage:
  python benchmarking/study_analyze.py STUDY_NAME

The script loads metrics from
  benchmarking/<study>/<study>_results/<study>_metrics.csv
and configuration from one of:
  benchmarking/<study>/study_analyze.cfg (preferred)
  benchmarking/study_analyze.cfg        (fallback)

It then produces the configured plots/heatmaps/fits inside
  benchmarking/<study>/<study>_plots.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Dict

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore

from bench_tools.analyze_tools import (
    AnalyzeConfig,
    load_analyze_config,
    load_metrics_table,
    run_analysis,
    validate_required_columns,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH_DIR = ROOT / "benchmarking"


def _load_config_dict(cfg_path: pathlib.Path) -> Dict[str, Any]:
    if not cfg_path.exists():
        raise SystemExit(f"Config not found: {cfg_path}")
    if cfg_path.suffix.lower() in {".cfg", ".toml"} and tomllib is not None:
        return tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    text = cfg_path.read_text(encoding="utf-8")
    text = text.strip()
    try:
        return json.loads(text)
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Failed to parse config {cfg_path}: {exc}") from exc


def resolve_config(study: str) -> pathlib.Path:
    study_cfg = BENCH_DIR / study / "study_analyze.cfg"
    if study_cfg.exists():
        return study_cfg
    default_cfg = BENCH_DIR / "study_analyze.cfg"
    if default_cfg.exists():
        return default_cfg
    raise SystemExit("No analysis configuration found.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("study", help="Study name (folder under benchmarking/)")
    args = parser.parse_args()

    study = args.study
    base_dir = BENCH_DIR / study
    results_dir = base_dir / f"{study}_results"
    plots_dir = base_dir / f"{study}_plots"
    metrics_csv = results_dir / f"{study}_metrics.csv"
    if not metrics_csv.exists():
        raise SystemExit(f"Metrics CSV not found: {metrics_csv}")

    cfg_path = resolve_config(study)
    raw_cfg = _load_config_dict(cfg_path)
    table, columns = load_metrics_table(metrics_csv)
    analyze_cfg: AnalyzeConfig = load_analyze_config(raw_cfg)
    validate_required_columns(analyze_cfg, columns)

    if not table:
        raise SystemExit(f"No data rows found in {metrics_csv}")

    generated = run_analysis(table, plots_dir, analyze_cfg)
    if not generated:
        print("[analyze] No plots configured; nothing to do.")


if __name__ == "__main__":
    main()

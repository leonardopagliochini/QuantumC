#!/usr/bin/env python3
"""Benchmark a generated study corpus.

Usage:
  python benchmarking/study_benchmark.py STUDY_NAME [--config path]

The script reuses ``bench_tools.benchmark_runner`` to evaluate the C sources in
``benchmarking/<study>/dataset`` (or the legacy ``<study>_dataset``) and writes
metrics and artefacts into ``benchmarking/<study>/<study>_results`` using the
same measurements collected by ``tools_old/whole_benchmark.py`` (timings,
Callgrind Ir, QASM statistics, plus an ``ir_offset`` column with CC-wise
baselines). The benchmark runner now also emits ``cpu_time_s`` which is the
sum of the reported user and system times. Results are stored in
``<study>_metrics.csv`` inside the study results directory.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
from typing import Any, Dict, Optional

from bench_tools.benchmark_runner import run_study

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CFG = pathlib.Path(__file__).with_suffix(".cfg")

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore


def _load_config(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Config not found: {path}")
    ext = path.suffix.lower()
    if ext in {".cfg", ".toml"} and tomllib is not None:
        return tomllib.loads(path.read_text(encoding="utf-8"))

    # Fallback to JSON with // and # comments stripped
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        lines.append(line)
    return json.loads("\n".join(lines))


def _normalise_string(value: Any) -> str:
    return str(value).strip()


def _resolve_workers(value: Any) -> Optional[int]:
    if value is None:
        return None
    cpu_total = max(1, os.cpu_count() or 1)

    def _clamp(n: int) -> int:
        return max(1, min(cpu_total, n))

    if isinstance(value, (int, float)):
        return _clamp(int(value))

    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"auto", "default"}:
        return None
    if text == "max":
        return cpu_total
    m = re.fullmatch(r"max\s*-\s*(\d+)", text)
    if m:
        offset = int(m.group(1))
        return _clamp(cpu_total - offset)
    try:
        return _clamp(int(float(text)))
    except Exception:
        raise SystemExit(f"Invalid 'workers' value in config: {value!r}")


DEFAULT_METRICS = {
    "cyclomatic": True,
    "ir_instructions": True,
    "ir_offset": True,
    "num_qubits": True,
    "num_gates": True,
    "num_cx": True,
    "num_measure": True,
    "num_u1": True,
    "num_u2": True,
    "num_u3": True,
    "depth": True,
    "user_time_s": True,
    "sys_time_s": True,
    "cpu_time_s": True,
    "max_rss_kb": True,
}


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"", "false", "0", "no", "off"}:
        return False
    raise SystemExit(f"Invalid boolean flag in metrics config: {value!r}")


def _load_metrics(cfg: Dict[str, Any]) -> Dict[str, bool]:
    cfg_metrics = cfg.get("metrics") or {}
    metrics: Dict[str, bool] = {}
    for key, default in DEFAULT_METRICS.items():
        raw_val = cfg_metrics.get(key, default)
        metrics[key] = _to_bool(raw_val)
    if metrics.get("ir_offset", True):
        if not metrics.get("ir_instructions", True):
            metrics["ir_instructions"] = True
        if not metrics.get("cyclomatic", True):
            metrics["cyclomatic"] = True
    if metrics.get("cpu_time_s", True):
        if not metrics.get("user_time_s", True):
            metrics["user_time_s"] = True
        if not metrics.get("sys_time_s", True):
            metrics["sys_time_s"] = True
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("study", help="Study name (folder inside benchmarking/)")
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        default=DEFAULT_CFG,
        help="Path to .cfg/.toml/.json config (default: study_benchmark.cfg)",
    )
    args = parser.parse_args()

    cfg = _load_config(args.config)

    cfg_study = _normalise_string(cfg.get("study", "")) if cfg.get("study") else ""
    if cfg_study and cfg_study != args.study:
        print(
            f"[warn] config study='{cfg_study}' differs from CLI argument '{args.study}'",
            file=sys.stderr,
        )

    bits = int(cfg.get("bits", 16))
    cc = _normalise_string(cfg.get("cc", "gcc")) or "gcc"
    arch_raw = cfg.get("arch")
    arch = _normalise_string(arch_raw) if arch_raw not in (None, "") else None
    input_cmd_raw = cfg.get("input_cmd")
    input_cmd = _normalise_string(input_cmd_raw) if input_cmd_raw not in (None, "") else None

    max_iter = int(cfg.get("max_iter", 30))
    ir_roi_func_raw = cfg.get("ir_roi_func")
    ir_roi_func = _normalise_string(ir_roi_func_raw) if ir_roi_func_raw not in (None, "") else None

    workers_raw = cfg.get("workers")
    workers = _resolve_workers(workers_raw)
    metrics_enabled = _load_metrics(cfg)

    progress = _normalise_string(cfg.get("progress", "plain"))
    if progress not in {"plain", "auto", "none"}:
        progress = "plain"
    show_stages = bool(cfg.get("show_stages", False))

    out_csv = run_study(
        args.study,
        bits=bits,
        cc=cc,
        arch=arch,
        input_cmd=input_cmd,
        max_iter=max_iter,
        progress=progress,
        show_stages=show_stages,
        ir_roi_func=ir_roi_func,
        max_workers=workers,
        metrics_enabled=metrics_enabled,
    )
    print(f"[benchmark] CSV: {out_csv}")


if __name__ == "__main__":
    main()

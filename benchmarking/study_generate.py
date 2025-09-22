#!/usr/bin/env python3
"""
Study generator

Generates pipeline-friendly C programs for a study under benchmarking/ by
targeting explicit Cyclomatic Complexity (CC) and Callgrind instruction count
(Ir) values supplied in a .cfg (TOML) file. For each CC value the script runs
two probe programs (pre_steps = 0 and 1) to measure, with Callgrind, the Ir
baseline and the Ir increase contributed by one straight-line repetition – that
increase is referred to as the "slope" in terminal output. Requested Ir targets
are then matched exactly by searching the baseline + N*slope sequence.

Config schema (TOML):

    study = "demo1"               # directory name under benchmarking/
    cc_values = [1, 2]            # list of CC targets (integers > 0)
    ir_values = [186211, 186213]  # list of desired Ir counts (integers)

For every CC in cc_values, the script measures the baseline Ir and the
per-step slope produced by the straight-line "pre-work" emitted by the
generator (one probe with pre_steps=0 and another with pre_steps=1). Using
those measurements it searches for a number of repetitions whose measured Ir
matches each requested ir_values entry exactly. If any target Ir cannot be hit
with the current slope, the script aborts with an error.

Output layout:

  benchmarking/<study>/
    <study>_dataset/     # generated C sources (one per CC×Ir)
    <study>_results/     # left intact by this step
    <study>_plots/       # left intact by this step

Each generated file is named `ccXX_irYYYYY.c`, where `XX` is the CC value and
`YYYYY` is the requested Ir.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Tuple, Optional

try:
    import tomllib  # Python 3.11+
except Exception as _exc:  # pragma: no cover
    raise SystemExit("tomllib is required (use Python 3.11 or newer)") from _exc


ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH_DIR = ROOT / "benchmarking"

if str(BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(BENCH_DIR))

from bench_tools.gen_cc_ir_programs import generate_c, PREWORK_CORE  # type: ignore


PRE_OPS = 1  # fixed straight-line ops per repetition (addition/mul/etc)
MAX_SEARCH_STEPS = 25  # ± window when nudging pre_steps to reach a target Ir
MAX_EXTRA_OPS = len(PREWORK_CORE)


def _load_config(cfg_path: pathlib.Path) -> dict:
    if cfg_path.suffix.lower() not in {".cfg", ".toml"}:
        raise SystemExit(f"Only TOML .cfg files are supported (got: {cfg_path})")
    try:
        return tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to parse config {cfg_path}: {exc}") from exc


def mkdirs(study: str) -> Tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    base = BENCH_DIR / study
    if base.exists():
        raise SystemExit(f"Study directory already exists: {base}. Choose a different name or remove it first.")

    ds = base / f"{study}_dataset"
    res = base / f"{study}_results"
    plots = base / f"{study}_plots"

    ds.mkdir(parents=True, exist_ok=False)
    res.mkdir(parents=True, exist_ok=False)
    plots.mkdir(parents=True, exist_ok=False)

    return ds, res, plots


def compile_c(c_path: pathlib.Path, out_bin: pathlib.Path) -> None:
    cmd = ["gcc", "-O0", "-g", str(c_path), "-o", str(out_bin)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"Compilation failed for {c_path}\n{proc.stderr}")


def callgrind_ir(bin_path: pathlib.Path) -> int:
    if shutil.which("valgrind") is None:
        raise SystemExit("valgrind (callgrind) not found in PATH")
    has_annot = shutil.which("callgrind_annotate") is not None
    bin_path.chmod(bin_path.stat().st_mode | 0o111)
    with tempfile.TemporaryDirectory() as td:
        tmp_bin = pathlib.Path(td) / bin_path.name
        tmp_bin.write_bytes(bin_path.read_bytes())
        tmp_bin.chmod(tmp_bin.stat().st_mode | 0o111)
        cg_out = pathlib.Path(td) / "callgrind.out"
        env = os.environ.copy()
        env["LANG"] = "C"
        env["LC_ALL"] = "C"
        cmd = [
            "valgrind",
            "--tool=callgrind",
            f"--callgrind-out-file={cg_out}",
            str(tmp_bin),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if not cg_out.exists():
            raise SystemExit(f"Callgrind failed for {bin_path}\n{result.stderr}")
        if has_annot:
            annot = subprocess.run(
                ["callgrind_annotate", str(cg_out)], capture_output=True, text=True, env=env
            )
            if annot.returncode == 0:
                import re

                match = re.search(r"\bIr\s*:\s*([\d,\.]+)", annot.stdout)
                if match:
                    return int(match.group(1).replace(",", "").replace(".", ""))
        raw = cg_out.read_text()
        import re

        events = re.search(r"^events:\s*(.+)$", raw, re.MULTILINE)
        if not events:
            raise SystemExit("Callgrind output missing events header")
        parts = events.group(1).strip().split()
        try:
            idx = parts.index("Ir")
        except ValueError as exc:
            raise SystemExit("Callgrind output missing Ir event") from exc
        summary = re.search(r"^summary:\s*([^\n]+)$", raw, re.MULTILINE)
        if not summary:
            raise SystemExit("Callgrind output missing summary line")
        values = summary.group(1).strip().split()
        try:
            return int(values[idx].replace(",", "").replace(".", ""))
        except (IndexError, ValueError) as exc:
            raise SystemExit("Callgrind summary parse error") from exc


def measure_ir(
    cc_value: int,
    pre_steps: int,
    extra_ops: int,
    cache: Dict[int, Dict[Tuple[int, int], int]],
) -> int:
    if pre_steps < 0:
        raise ValueError("pre_steps must be >= 0")
    extra_ops = max(0, min(extra_ops, MAX_EXTRA_OPS))
    cc_cache = cache.setdefault(cc_value, {})
    key = (pre_steps, extra_ops)
    if key in cc_cache:
        return cc_cache[key]
    src = generate_c(
        cc_value,
        iters=0,
        ops_per_iter=PRE_OPS,
        pre_steps=pre_steps,
        pre_ops=PRE_OPS,
        extra_ops=extra_ops,
    )
    with tempfile.TemporaryDirectory() as td:
        tdir = pathlib.Path(td)
        c_path = tdir / f"cc{cc_value:02d}_pre{pre_steps}_extra{extra_ops}.c"
        bin_path = tdir / f"cc{cc_value:02d}_pre{pre_steps}_extra{extra_ops}"
        c_path.write_text(src)
        compile_c(c_path, bin_path)
        ir = callgrind_ir(bin_path)
    cc_cache[key] = ir
    return ir


def calibrate_cc(cc_value: int, cache: Dict[int, Dict[Tuple[int, int], int]]) -> Tuple[int, int]:
    base_ir = measure_ir(cc_value, 0, 0, cache)
    ir_step = measure_ir(cc_value, 1, 0, cache)
    slope = ir_step - base_ir
    if slope <= 0:
        raise SystemExit(f"Non-positive slope detected for CC={cc_value}: base={base_ir}, step={ir_step}")
    return base_ir, slope


def search_pre_steps(
    cc_value: int,
    target_ir: int,
    base_ir: int,
    slope: int,
    cache: Dict[int, Dict[Tuple[int, int], int]],
    offset: int,
    tol_low: int,
    tol_high: int,
) -> Tuple[int, int, int]:
    approx = (target_ir - base_ir) / slope if slope else 0
    candidates: List[int] = []
    start = int(round(approx))
    offsets: List[int] = [0]
    for d in range(1, MAX_SEARCH_STEPS + 1):
        offsets.extend([d, -d])
    for off in offsets:
        cand = start + off
        if cand < 0:
            continue
        candidates.append(cand)
    tried: Dict[Tuple[int, int], int] = {}
    best: Optional[Tuple[int, int, int]] = None

    for steps in candidates:
        last_ir: Optional[int] = None
        for extra_ops in range(0, MAX_EXTRA_OPS + 1):
            ir = measure_ir(cc_value, steps, extra_ops, cache)
            tried[(steps, extra_ops)] = ir

            err = abs(ir - target_ir)
            if best is None or err < abs(best[2] - target_ir):
                best = (steps, extra_ops, ir)

            if ir <= target_ir:
                if target_ir - ir <= tol_low:
                    return steps, extra_ops, ir
            else:
                if ir - target_ir <= tol_high:
                    return steps, extra_ops, ir
                if last_ir is not None and ir > target_ir + tol_high:
                    break
            last_ir = ir
    def fmt_entry(step: int, extra_ops: int, ir_val: int) -> str:
        return f"{step}+{extra_ops}->{ir_val - base_ir}"

    tried_str = ", ".join(
        fmt_entry(s, extra, ir) for (s, extra), ir in sorted(tried.items())
    )
    extra_msg = (
        f" Closest result: pre_steps={best[0]}, extra_ops={best[1]}, Ir={best[2] - base_ir} (target offset {offset})"
        if best is not None
        else ""
    )
    raise SystemExit(
        f"Unable to match Ir target (baseline {base_ir} + offset {offset}) for CC={cc_value}."
        f" Allowed tolerances -> below: {tol_low}, above: {tol_high}. Tried variants: {tried_str}.{extra_msg}"
    )


def write_program(
    dataset_dir: pathlib.Path,
    cc_value: int,
    target_ir: int,
    base_ir: int,
    pre_steps: int,
    extra_ops: int,
    actual_ir: int,
    offset: int,
) -> None:
    filename = dataset_dir / f"cc{cc_value:02d}_ir{actual_ir}.c"
    src = generate_c(
        cc_value,
        iters=0,
        ops_per_iter=PRE_OPS,
        pre_steps=pre_steps,
        pre_ops=PRE_OPS,
        extra_ops=extra_ops,
    )
    filename.write_text(src)
    target_off = target_ir - base_ir
    actual_off = actual_ir - base_ir
    print(
        f"  -> wrote {filename.name} (offset={offset}, target_offset={target_off}, actual_offset={actual_off}, pre_steps={pre_steps}, extra_ops={extra_ops})"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("study", help="Study name (creates benchmarking/<study>/ directories)")
    parser.add_argument(
        "--config",
        required=False,
        help="Path to .cfg (TOML) config. Defaults to benchmarking/study_generate.cfg",
    )
    args = parser.parse_args()

    cfg_path = pathlib.Path(args.config) if args.config else BENCH_DIR / "study_generate.cfg"
    cfg = _load_config(cfg_path)

    study = args.study
    cfg_study = cfg.get("study")
    if cfg_study and cfg_study != study:
        print(
            f"[warn] ignoring study='{cfg_study}' from {cfg_path.name}; using CLI argument '{study}' instead",
            file=sys.stderr,
        )

    cc_values = cfg.get("cc_values")
    ir_values = cfg.get("ir_values")
    if not isinstance(cc_values, list) or not cc_values:
        raise SystemExit("Config must define non-empty list 'cc_values'")
    if not isinstance(ir_values, list) or not ir_values:
        raise SystemExit("Config must define non-empty list 'ir_values'")

    cc_list = []
    prev_cc: Optional[int] = None
    for cc in cc_values:
        try:
            cc_int = int(cc)
        except Exception as exc:
            raise SystemExit(f"Invalid CC value {cc}: {exc}") from exc
        if cc_int <= 0:
            raise SystemExit(f"CC values must be positive integers (got {cc_int})")
        if prev_cc is not None and cc_int <= prev_cc:
            raise SystemExit("cc_values must be strictly increasing")
        cc_list.append(cc_int)
        prev_cc = cc_int

    ir_offsets: List[int] = []
    prev_offset: Optional[int] = None
    for ir in ir_values:
        try:
            offset = int(ir)
        except Exception as exc:
            raise SystemExit(f"Invalid Ir offset {ir}: {exc}") from exc
        if offset < 0:
            raise SystemExit(f"Ir offsets must be >= 0 (got {offset})")
        if prev_offset is not None and offset <= prev_offset:
            raise SystemExit("ir_values must be strictly increasing")
        ir_offsets.append(offset)
        prev_offset = offset
    if not ir_offsets:
        raise SystemExit("Config must define at least one Ir offset")

    offsets_sorted = sorted(ir_offsets)

    dataset_dir, _, _ = mkdirs(study)

    print(f"[info] study={study} -> dataset directory {dataset_dir}")
    cache: Dict[int, Dict[Tuple[int, int], int]] = {}
    summary: List[Tuple[int, int, int]] = []

    def tolerance_from_diff(diff: int) -> int:
        TOL = 0.10
        if diff <= 0:
            return 0
        tol = int(round(diff * TOL))
        if tol == 0:
            tol = 1
        return tol

    single_offset_mode = len(offsets_sorted) == 1

    for cc_value in cc_list:
        base_ir, slope = calibrate_cc(cc_value, cache)
        summary.append((cc_value, base_ir, slope))
        print(f"[cal] CC={cc_value}: base_ir={base_ir}, slope={slope}")
        for idx, offset in enumerate(offsets_sorted):
            prev_offset = offsets_sorted[idx - 1] if idx > 0 else None
            next_offset = offsets_sorted[idx + 1] if idx + 1 < len(offsets_sorted) else None

            diff_prev = (
                offset - prev_offset
                if prev_offset is not None
                else (next_offset - offset if next_offset is not None else 0)
            )
            diff_next = (
                next_offset - offset
                if next_offset is not None
                else (offset - prev_offset if prev_offset is not None else 0)
            )
            if single_offset_mode:
                tol_low = tol_high = 10
            else:
                tol_low = tolerance_from_diff(diff_prev)
                tol_high = tolerance_from_diff(diff_next)

            target_ir = base_ir + offset
            pre_steps, extra_ops, actual_ir = search_pre_steps(
                cc_value,
                target_ir,
                base_ir,
                slope,
                cache,
                offset,
                tol_low,
                tol_high,
            )
            write_program(dataset_dir, cc_value, target_ir, base_ir, pre_steps, extra_ops, actual_ir, offset)

    print("[summary] slopes per CC:")
    for cc_value, base_ir, slope in summary:
        print(f"  CC {cc_value}: base_ir={base_ir}, slope={slope}")


if __name__ == "__main__":
    main()

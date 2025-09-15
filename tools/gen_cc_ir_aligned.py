#!/usr/bin/env python3
"""
gen_cc_ir_aligned.py — Generate a CC×Ir corpus that is fully pipeline-compatible.

Features
- Emits only one function `main` with local int variables and top-level `if`s.
- No loops, no ROI, no macros, no globals, no inline asm — pipeline-friendly.
- Ir controlled via straight-line pre-work in `main` (each step adds pre_ops
  simple statements such as `a = a + b;`).
- Optional Callgrind calibration (alignment) to make the first Ir per-CC land in
  the same bin across CC rows; the generated code remains macro-free.

Usage examples
  # Simple 10×10 grid (no alignment), CC=1..10, small Ir steps
  python tools/gen_cc_ir_aligned.py gen-grid \
    --out-dir corpus_cc10x10_noloop \
    --cc-min 1 --cc-max 10 \
    --k 10 \
    --pre-base 1 --pre-step 1 --pre-ops 1

  # Same grid but align first Ir across CC rows to a common bin (width=5)
  python tools/gen_cc_ir_aligned.py gen-grid \
    --out-dir corpus_cc10x10_noloop_aligned \
    --cc-min 1 --cc-max 10 \
    --k 10 \
    --pre-ops 1 \
    --align --bin-w 5 \
    --cc gcc --arch x86-64
"""

from __future__ import annotations

import argparse
import math
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple


# ---- Reuse the simplified generator ----
try:
    # tools/gen_cc_ir_programs.py must be importable as a module
    from gen_cc_ir_programs import generate_c  # type: ignore
except Exception as _e:  # pragma: no cover
    raise SystemExit("ERROR: cannot import generate_c from gen_cc_ir_programs.py")


def write_file(out_dir: pathlib.Path, name: str, src: str) -> pathlib.Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / name
    p.write_text(src)
    return p


def compile_c(c_path: pathlib.Path, out_bin: pathlib.Path, cc: str = "gcc", arch: Optional[str] = None) -> None:
    cmd = [cc, "-O0", "-g", str(c_path), "-o", str(out_bin)]
    if arch:
        a = arch.lower()
        if a == "arm":
            cmd.insert(1, "-march=armv7-a")
        elif a in ("x86", "i686"):
            cmd.insert(1, "-march=i686")
        elif a in ("x86-64", "x86_64", "amd64"):
            cmd.insert(1, "-march=x86-64")
    subprocess.run(cmd, check=True)


def callgrind_ir(bin_path: pathlib.Path) -> Optional[int]:
    if shutil.which("valgrind") is None:
        return None
    has_annot = shutil.which("callgrind_annotate") is not None
    try:
        bin_path.chmod(bin_path.stat().st_mode | 0o111)
    except Exception:
        pass
    with tempfile.TemporaryDirectory() as td:
        tmp_bin = pathlib.Path(td) / bin_path.name
        shutil.copy2(bin_path, tmp_bin)
        tmp_bin.chmod(tmp_bin.stat().st_mode | 0o111)
        cg_out = pathlib.Path(td) / "callgrind.out"
        env = os.environ.copy()
        env["LANG"] = "C"; env["LC_ALL"] = "C"
        vg_cmd = ["valgrind", "--tool=callgrind", f"--callgrind-out-file={str(cg_out)}", str(tmp_bin)]
        res = subprocess.run(vg_cmd, capture_output=True, text=True, env=env)
        if not cg_out.exists():
            return None
        if has_annot:
            ann = subprocess.run(["callgrind_annotate", str(cg_out)], capture_output=True, text=True, env=env)
            if ann.returncode == 0:
                m = re.search(r"\bIr\s*:\s*([\d,\.]+)", ann.stdout)
                if m:
                    return int(m.group(1).replace(",", "").replace(".", ""))
        # Fallback raw parse
        raw = cg_out.read_text()
        ev_m = re.search(r"^events:\s*(.+)$", raw, re.MULTILINE)
        if not ev_m:
            return None
        events = ev_m.group(1).strip().split()
        try:
            ir_idx = events.index("Ir")
        except ValueError:
            return None
        sum_m = re.search(r"^summary:\s*([^\n]+)$", raw, re.MULTILINE)
        if not sum_m:
            return None
        nums = re.split(r"\s+", sum_m.group(1).strip())
        def clean(s: str) -> str: return re.sub(r"[,_\.]", "", s)
        if ir_idx < len(nums):
            return int(clean(nums[ir_idx]))
        if len(nums) == 1 and ir_idx == 0:
            return int(clean(nums[0]))
        return None


def calibrated_prebase_for_cc(cc: int, *, pre_ops: int, bin_w: int, cc_compiler: str, arch: Optional[str]) -> Tuple[int, int]:
    """Estimate per-step Ir delta and compute pre_base to land the first point in a common bin.

    Returns (pre_base, ir_min_bin_aligned). This function measures Ir using two
    temporary programs with pre_steps=1 and pre_steps=2.
    """
    # Create two tiny temp files and measure Ir
    with tempfile.TemporaryDirectory() as td:
        tdir = pathlib.Path(td)
        irs: List[int] = []
        for pre_steps in (1, 2):
            src = generate_c(cc, iters=0, ops_per_iter=pre_ops, pre_steps=pre_steps, pre_ops=pre_ops)
            c_path = tdir / f"tmp_cc{cc:02d}_pre{pre_steps}.c"
            bin_path = tdir / f"tmp_cc{cc:02d}_pre{pre_steps}"
            c_path.write_text(src)
            compile_c(c_path, bin_path, cc=cc_compiler, arch=arch)
            ir = callgrind_ir(bin_path)
            if ir is None:
                raise RuntimeError("Callgrind not available or failed during calibration")
            irs.append(ir)
        ir1, ir2 = irs
        slope = max(ir2 - ir1, 1)
        # Choose target as bin-aligned max(ir1) across CC rows; we can't know that here.
        # We return the base pre_base for this CC to reach ceil(ir1/bin_w)*bin_w.
        target = int(math.ceil(ir1 / bin_w) * bin_w)
        extra_steps = max(0, math.ceil((target - ir1) / float(slope)))
        pre_base = 1 + int(extra_steps)
        return pre_base, target


def gen_grid(args: argparse.Namespace) -> None:
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not args.align:
        for cc in range(args.cc_min, args.cc_max + 1):
            for idx in range(args.k):
                pre_steps = args.pre_base + idx * args.pre_step
                src = generate_c(cc, iters=0, ops_per_iter=args.pre_ops, pre_steps=pre_steps, pre_ops=args.pre_ops)
                name = f"cc{cc:02d}_idx{idx:03d}_iters0_ops{args.pre_ops}_pre{pre_steps}x{args.pre_ops}.c"
                write_file(out, name, src)
                if args.progress:
                    print(f"[gen-grid] Wrote: {out/name}")
        return

    # Alignment mode: compute per-CC pre_base so the first Ir lands in a common bin
    # First measure ir1 for each CC (pre_steps=1)
    per_cc_prebase: Dict[int, int] = {}
    per_cc_ir1: Dict[int, int] = {}
    per_cc_slope: Dict[int, int] = {}
    # Measure using temp files
    for cc in range(args.cc_min, args.cc_max + 1):
        with tempfile.TemporaryDirectory() as td:
            tdir = pathlib.Path(td)
            irs = []
            for pre_steps in (1, 2):
                src = generate_c(cc, iters=0, ops_per_iter=args.pre_ops, pre_steps=pre_steps, pre_ops=args.pre_ops)
                c_path = tdir / f"tmp_cc{cc:02d}_pre{pre_steps}.c"
                bin_path = tdir / f"tmp_cc{cc:02d}_pre{pre_steps}"
                c_path.write_text(src)
                compile_c(c_path, bin_path, cc=args.cc, arch=args.arch)
                ir = callgrind_ir(bin_path)
                if ir is None:
                    raise RuntimeError("Callgrind not available or failed during calibration")
                irs.append(ir)
            ir1, ir2 = irs
            slope = max(ir2 - ir1, 1)
            per_cc_ir1[cc] = ir1
            per_cc_slope[cc] = slope

    # Choose common target bin from the maximum of ir1 across CC
    max_ir1 = max(per_cc_ir1.values())
    target = int(math.ceil(max_ir1 / args.bin_w) * args.bin_w)
    # Compute per-CC pre_base to land at target bin
    for cc in range(args.cc_min, args.cc_max + 1):
        ir1 = per_cc_ir1[cc]
        slope = per_cc_slope[cc]
        extra_steps = max(0, math.ceil((target - ir1) / float(slope)))
        per_cc_prebase[cc] = 1 + int(extra_steps)

    # Generate final corpus
    for cc in range(args.cc_min, args.cc_max + 1):
        pre_base = per_cc_prebase[cc]
        for idx in range(args.k):
            pre_steps = pre_base + idx * 1
            src = generate_c(cc, iters=0, ops_per_iter=args.pre_ops, pre_steps=pre_steps, pre_ops=args.pre_ops)
            name = f"cc{cc:02d}_idx{idx:03d}_iters0_ops{args.pre_ops}_pre{pre_steps}x{args.pre_ops}.c"
            write_file(out, name, src)
            if args.progress:
                print(f"[gen-grid] Wrote: {out/name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_grid = sub.add_parser("gen-grid")
    ap_grid.add_argument("--out-dir", type=str, required=True)
    ap_grid.add_argument("--cc-min", type=int, required=True)
    ap_grid.add_argument("--cc-max", type=int, required=True)
    ap_grid.add_argument("--k", type=int, default=10)
    ap_grid.add_argument("--pre-base", type=int, default=1)
    ap_grid.add_argument("--pre-step", type=int, default=1)
    ap_grid.add_argument("--pre-ops", type=int, default=1)
    ap_grid.add_argument("--align", action="store_true", help="Calibrate per-CC pre_base with Callgrind to align first Ir across CC rows")
    ap_grid.add_argument("--bin-w", type=int, default=5, help="Bin width for Ir alignment (used with --align)")
    ap_grid.add_argument("--cc", type=str, default="gcc", help="C compiler for calibration when --align is used")
    ap_grid.add_argument("--arch", type=str, default=None, help="Optional arch hint for calibration compiler (e.g., x86-64)")
    ap_grid.add_argument("--progress", action="store_true", help="Print per-file generation logs")
    ap_grid.set_defaults(func=gen_grid)

    # Bin-driven generation: guarantee B Ir bins per CC, all pipeline-clean.
    def gen_bins(args: argparse.Namespace) -> None:
        out = pathlib.Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)

        # 1) Calibrate per-CC slope/intercept using two points (pre_steps=1,2)
        a_cc: Dict[int, float] = {}
        slope_cc: Dict[int, float] = {}
        for cc in range(args.cc_min, args.cc_max + 1):
            with tempfile.TemporaryDirectory() as td:
                tdir = pathlib.Path(td)
                irs: List[int] = []
                for p in (1, 2):
                    src = generate_c(cc, iters=0, ops_per_iter=args.pre_ops, pre_steps=p, pre_ops=args.pre_ops)
                    c_path = tdir / f"tmp_cc{cc:02d}_p{p}.c"
                    bin_path = tdir / f"tmp_cc{cc:02d}_p{p}"
                    c_path.write_text(src)
                    compile_c(c_path, bin_path, cc=args.cc, arch=args.arch)
                    ir = callgrind_ir(bin_path)
                    if ir is None:
                        raise RuntimeError("Callgrind not available or failed during calibration")
                    irs.append(ir)
                ir1, ir2 = irs
                slope = max(ir2 - ir1, 1)
                a = ir1 - slope * 1.0
                a_cc[cc] = float(a)
                slope_cc[cc] = float(slope)
                if args.progress:
                    print(f"[cal] CC={cc}: ir1={ir1}, ir2={ir2}, slope≈{slope}")

        # 2) Choose common overlapping range across CC for p in [pmin, pmax]
        pmin = int(args.pmin)
        pmax = int(args.pmax)
        def cc_range(cc: int, pmin: int, pmax: int) -> Tuple[float, float]:
            a, m = a_cc[cc], slope_cc[cc]
            return (a + m * pmin, a + m * pmax)
        low = max(cc_range(cc, pmin, pmax)[0] for cc in range(args.cc_min, args.cc_max + 1))
        high = min(cc_range(cc, pmin, pmax)[1] for cc in range(args.cc_min, args.cc_max + 1))
        if high <= low:
            raise SystemExit("ERROR: No overlapping Ir range across CC with given pmin/pmax. Increase --pmax or reduce --pmin.")

        # 3) Define bins across [low, high]
        B = int(args.bins)
        if args.bin_w and args.bin_w > 0:
            W = int(args.bin_w)
            span = W * B
            # center bins within [low, high] span
            start = math.floor(low)
        else:
            span = (high - low)
            W = max(1, int(math.ceil(span / B)))
            start = int(math.floor(low))
        bin_edges = [start + i * W for i in range(B + 1)]
        bin_centers = [be + W / 2.0 for be in bin_edges[:-1]]
        if args.progress:
            print(f"[bins] low≈{low:.1f} high≈{high:.1f} W={W} B={B} start={start}")

        # 4) For each CC and each bin center, find pre_steps whose measured Ir falls in that bin
        plan: List[Tuple[int, int, int]] = []  # (cc, bin_idx, pre_steps)
        for cc in range(args.cc_min, args.cc_max + 1):
            a = a_cc[cc]; m = slope_cc[cc]
            for bi, center in enumerate(bin_centers):
                # Predicted steps (rounded) to hit center
                pred = int(round((center - a) / m))
                pred = max(pmin, min(pmax, pred))
                # Verify and nudge within a small window
                chosen = None
                # Try a small search window around pred
                window = list(range(0, args.verify_window + 1))
                offsets = sorted({off for d in window for off in (d, -d)})
                with tempfile.TemporaryDirectory() as td:
                    tdir = pathlib.Path(td)
                    for off in offsets:
                        p = pred + off
                        if p < pmin or p > pmax:
                            continue
                        src = generate_c(cc, iters=0, ops_per_iter=args.pre_ops, pre_steps=p, pre_ops=args.pre_ops)
                        c_path = tdir / f"t_cc{cc:02d}_b{bi:02d}_p{p}.c"
                        bin_path = tdir / f"t_cc{cc:02d}_b{bi:02d}_p{p}"
                        c_path.write_text(src)
                        compile_c(c_path, bin_path, cc=args.cc, arch=args.arch)
                        ir = callgrind_ir(bin_path)
                        if ir is None:
                            continue
                        lo = bin_edges[bi]
                        hi = bin_edges[bi + 1]
                        if lo <= ir < hi:
                            chosen = p
                            if args.progress:
                                print(f"[pick] CC={cc} bin={bi+1}/{B} p={p} ir={ir} in [{lo},{hi})")
                            break
                if chosen is None:
                    # fallback: just use pred; we'll accept minor drift
                    chosen = pred
                    if args.progress:
                        print(f"[warn] CC={cc} bin={bi+1}: no exact in-bin found, using p={pred}")
                plan.append((cc, bi, chosen))

        # 5) Generate final corpus
        # Sort by cc then bin index for tidy naming
        plan.sort()
        for cc, bi, p in plan:
            src = generate_c(cc, iters=0, ops_per_iter=args.pre_ops, pre_steps=p, pre_ops=args.pre_ops)
            name = f"cc{cc:02d}_bin{bi+1:02d}_iters0_ops{args.pre_ops}_pre{p}x{args.pre_ops}.c"
            write_file(out, name, src)
            if args.progress:
                print(f"[gen] {out/name}")

        # 6) Write a plan CSV for traceability
        plan_csv = out / "bins_plan.csv"
        with plan_csv.open("w", encoding="utf-8") as f:
            f.write("cc,bin_idx,pre_steps\n")
            for cc, bi, p in plan:
                f.write(f"{cc},{bi+1},{p}\n")
        if args.progress:
            print(f"[done] Wrote: {plan_csv}")

    ap_bins = sub.add_parser("gen-bins")
    ap_bins.add_argument("--out-dir", type=str, required=True)
    ap_bins.add_argument("--cc-min", type=int, required=True)
    ap_bins.add_argument("--cc-max", type=int, required=True)
    ap_bins.add_argument("--bins", type=int, required=True, help="Number of Ir bins to generate per CC")
    ap_bins.add_argument("--bin-w", type=int, default=0, help="Fixed bin width (optional). If 0, auto-compute from overlap range")
    ap_bins.add_argument("--pre-ops", type=int, default=1)
    ap_bins.add_argument("--pmin", type=int, default=1)
    ap_bins.add_argument("--pmax", type=int, default=64)
    ap_bins.add_argument("--cc", type=str, default="gcc")
    ap_bins.add_argument("--arch", type=str, default=None)
    ap_bins.add_argument("--verify-window", type=int, default=3, help="Search window (±steps) when nudging into bin")
    ap_bins.add_argument("--progress", action="store_true")
    ap_bins.set_defaults(func=gen_bins)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate C programs using only admissible operations (ints, + - * /, if/for)
with deterministic cyclomatic complexity and controllable instruction count.

Approach
- Cyclomatic complexity (CC): create `m` independent if-statements plus an
  optional for-loop. Lizard counts each `if` and the `for` as decision points.
  Thus: CC ~= 1 + m + (1 if loop is present else 0).
- Instruction count (Ir): controlled by running a for-loop with a selectable
  number of iterations and a fixed arithmetic body. Dynamic Ir grows roughly
  linearly with the iteration count.

CLI
  Generate a single program with given CC and iterations:
    python tools/gen_cc_ir_programs.py gen-one \
      --out-dir corpus_synth --cc 8 --iters 2000 --ops-per-iter 8

  Generate a range of programs with fixed CC and varying iterations:
    python tools/gen_cc_ir_programs.py gen-range \
      --out-dir corpus_synth --cc 8 --base-iters 1500 --step 150 --k 30

You can then scan the folder using:
    conda run -n cotenv python tools/scan_cc_ir.py --corpus corpus_synth \
      --show-stages --progress plain --out tools/results/cc_ir_synth.csv

Notes
- This script does not call valgrind/lizard; it only emits C.
- To approximate a desired Ir, increase/decrease `--iters` (and optionally
  `--ops-per-iter`). For exact targeting, you can calibrate slope externally by
  scanning two samples with different iteration counts and interpolating.
"""

import argparse
import pathlib
from typing import List


TOP_BASE = """"""

def make_top(use_roi: bool) -> str:
    if not use_roi:
        return ""
    # Try to include Callgrind client header if present; otherwise define no-ops
    return (
        "#if defined(__has_include)\n"
        "#  if __has_include(<valgrind/callgrind.h>)\n"
        "#    include <valgrind/callgrind.h>\n"
        "#  else\n"
        "#    define CALLGRIND_START_INSTRUMENTATION\n"
        "#    define CALLGRIND_STOP_INSTRUMENTATION\n"
        "#    define CALLGRIND_ZERO_STATS\n"
        "#  endif\n"
        "#else\n"
        "#  include <valgrind/callgrind.h>\n"
        "#endif\n\n"
    )

MAIN_BEGIN = (
    "int main(){\n"
    "  volatile int sink = 0;\n"
    "  int a = 1, b = 2, c = 3, s = 0;\n"
)

FOOTER = """
  sink = sink + a + b + c + s;
  return sink;
}
""".lstrip()


def make_if_chain(n: int) -> str:
    """Emit n sequential if statements using only integer literals and +, <.

    Each if toggles `s` deterministically; conditions do not depend on loop.
    This contributes `n` decision points to CC. Lizard counts else but not as
    a new decision.
    """
    lines: List[str] = []
    # Use distinct constants to avoid trivial folding by compiler at -O0 it's fine
    for i in range(n):
        k = (i + 3)
        th = k + 1
        lhs = "a" if (i % 2 == 0) else "b"
        lines.append(f"  if (({lhs} + {k}) < {th}) {{ s = s + 1; }} else {{ s = s - 1; }}\n")
    return "".join(lines)


def make_work_loop(iters: int, ops_per_iter: int) -> str:
    """Emit a for-loop that performs pure integer arithmetic per iteration.

    Only uses +, -, *, / and integer variables. No modulo, bitwise, or IO.
    """
    if iters <= 0:
        return ""
    body_ops: List[str] = []
    # A compact body of operations; repeat to scale cost per iter
    core = [
        "a = a + b;",
        "b = b + 1;",
        "s = s + a;",
        "a = a * 3 - 1;",
        "b = b * 2 + 1;",
        "s = s + b;",
        "s = s - a / 3;",
        "s = s + b / 5;",
    ]
    # Choose as many operations as requested (cycle over core)
    seq: List[str] = []
    for i in range(max(1, ops_per_iter)):
        seq.append(core[i % len(core)])
    joined = " ".join(seq)
    body_ops.append(f"    {joined}\n")

    return "".join([
        f"  for (int i = 0; i < {int(iters)}; i = i + 1) {{\n",
        *body_ops,
        "  }\n",
    ])


def make_prework(steps: int, ops_per_iter: int) -> str:
    """Emit straight-line arithmetic repeated `steps` times (no loop)."""
    if steps <= 0:
        return ""
    core = [
        "a = a + b;",
        "b = b + 1;",
        "s = s + a;",
        "a = a * 3 - 1;",
        "b = b * 2 + 1;",
        "s = s + b;",
        "s = s - a / 3;",
        "s = s + b / 5;",
    ]
    seq = []
    for t in range(int(steps)):
        # cycle through ops_per_iter statements
        for i in range(max(1, ops_per_iter)):
            seq.append(core[i % len(core)])
    return "".join(f"  {line}\n" for line in seq)

def make_int_ops(count: int, use_globals: bool = False) -> str:
    """Emit `count` straight-line integer statements that the toolchain lowers.

    We alternate a few additions to variables and to an accumulator to avoid
    being optimized away and to ensure a stable instruction footprint.
    """
    if count <= 0:
        return ""
    lines: List[str] = []
    a = 'ga' if use_globals else 'a'
    b = 'gb' if use_globals else 'b'
    s = 'gs' if use_globals else 's'
    for i in range(int(count)):
        k = (i % 5) + 1
        lines.append(f"  {a} = {a} + {k};\n")
        lines.append(f"  {s} = {s} + {a};\n")
        lines.append(f"  {b} = {b} + 1;\n")
        lines.append(f"  {s} = {s} + {b};\n")
    return "".join(lines)

def make_nops(count: int) -> str:
    """Emit exactly `count` inline NOP instructions (one Ir each on x86)."""
    if count <= 0:
        return ""
    # Use volatile to prevent removal; place as straight-line code to avoid loop overhead.
    return "".join("  asm volatile(\"nop\");\n" for _ in range(int(count)))


def generate_c(cc_target: int, iters: int, ops_per_iter: int,
               pre_steps: int = 0, pre_ops: int = None, nops: int = 0,
               roi: bool = False, roi_region: str = "nops",
               roi_mode: str = "func") -> str:
    """Create a C program aiming for given CC and iteration-controlled Ir.

    CC model: 1 (base) + n_if + (1 if iters>0 else 0) ~= cc_target
    => n_if = max(0, cc_target - 1 - loop_cc)
    """
    include_loop = iters > 0
    loop_cc = 1 if include_loop else 0
    n_if = cc_target - 1 - loop_cc
    if n_if < 0:
        # Can't hit cc_target exactly with a loop; remove loop if needed
        if include_loop:
            include_loop = False
            iters = 0
            loop_cc = 0
            n_if = max(0, cc_target - 1)
        else:
            n_if = 0

    parts: List[str] = [make_top(roi and roi_mode == "macro")]

    # Optional function-based ROI: define roi_block() before main and call it from main
    if roi and roi_mode == "func" and nops > 0 and roi_region == "nops":
        # Global working variables for ROI function
        parts.append("static int ga=1, gb=2, gs=0;\n")
        parts.append("void __attribute__((noinline)) roi_block(void) {\n")
        parts.append(make_int_ops(nops, use_globals=True))
        parts.append("}\n\n")

    # Begin main
    parts.append(MAIN_BEGIN)

    # Optional straight-line pre-work to vary Ir without adding CC
    if pre_steps > 0:
        parts.append(make_prework(pre_steps, pre_ops if pre_ops is not None else ops_per_iter))
    if n_if > 0:
        parts.append(make_if_chain(n_if))
    if include_loop:
        if roi and roi_region == "loop":
            parts.append("  CALLGRIND_ZERO_STATS;\n  CALLGRIND_START_INSTRUMENTATION;\n")
        parts.append(make_work_loop(iters, ops_per_iter))
        if roi and roi_region == "loop":
            parts.append("  CALLGRIND_STOP_INSTRUMENTATION;\n")
    # ROI ops region: use integer ops so toolchain lowers them
    if nops > 0:
        if roi and roi_mode == "func" and roi_region == "nops":
            parts.append("  roi_block();\n")
            # Duplicate ROI ops in main so they are visible to the pipeline
            parts.append(make_int_ops(nops))
        elif roi and roi_mode == "macro" and roi_region == "nops":
            parts.append("  CALLGRIND_ZERO_STATS;\n  CALLGRIND_START_INSTRUMENTATION;\n")
            parts.append(make_int_ops(nops))
            parts.append("  CALLGRIND_STOP_INSTRUMENTATION;\n")
        else:
            parts.append(make_int_ops(nops))
    parts.append(FOOTER)
    return "".join(parts)


def write_file(out_dir: pathlib.Path, name: str, src: str) -> pathlib.Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / name
    p.write_text(src)
    return p


def cmd_gen_one(args: argparse.Namespace) -> None:
    src = generate_c(
        args.cc, args.iters, args.ops_per_iter,
        pre_steps=args.pre_steps, pre_ops=args.pre_ops,
        nops=args.nops,
        roi=args.roi, roi_region=args.roi_region,
    )
    name = f"cc{args.cc:02d}_iters{args.iters}_ops{args.ops_per_iter}_pre{args.pre_steps}x{args.pre_ops}_nops{args.nops}_roi{int(args.roi)}_{args.roi_region}.c"
    path = write_file(pathlib.Path(args.out_dir), name, src)
    print(f"[gen-one] Wrote: {path}")


def cmd_gen_range(args: argparse.Namespace) -> None:
    out_dir = pathlib.Path(args.out_dir)
    for idx in range(args.k):
        iters = args.base_iters + idx * args.step
        pre_steps = args.pre_base + idx * args.pre_step
        src = generate_c(args.cc, iters, args.ops_per_iter,
                         pre_steps=pre_steps, pre_ops=args.pre_ops,
                         nops=args.nops, roi=args.roi, roi_region=args.roi_region)
        name = f"cc{args.cc:02d}_idx{idx:03d}_iters{iters}_ops{args.ops_per_iter}_pre{pre_steps}x{args.pre_ops}_nops{args.nops}_roi{int(args.roi)}_{args.roi_region}.c"
        path = write_file(out_dir, name, src)
        print(f"[gen-range] Wrote: {path}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_common = argparse.ArgumentParser(add_help=False)
    ap_common.add_argument("--out-dir", type=str, default="corpus_synth")
    ap_common.add_argument("--cc", type=int, required=True)
    ap_common.add_argument("--ops-per-iter", type=int, default=8)

    ap_one = sub.add_parser("gen-one", parents=[ap_common])
    ap_one.add_argument("--iters", type=int, default=0)
    ap_one.add_argument("--pre-steps", type=int, default=0, help="Straight-line work repetitions (no loop)")
    ap_one.add_argument("--pre-ops", type=int, default=8, help="Ops per pre-work repetition")
    ap_one.add_argument("--nops", type=int, default=0, help="Exact Ir control: add this many inline NOPs")
    ap_one.add_argument("--roi", action="store_true", help="Enable ROI measurement")
    ap_one.add_argument("--roi-region", choices=["nops", "loop"], default="nops", help="Region to measure with ROI")
    ap_one.add_argument("--roi-mode", choices=["func", "macro"], default="func", help="ROI via function toggle or client macros")
    ap_one.set_defaults(func=cmd_gen_one)

    ap_range = sub.add_parser("gen-range", parents=[ap_common])
    ap_range.add_argument("--base-iters", type=int, default=1000)
    ap_range.add_argument("--step", type=int, default=100)
    ap_range.add_argument("--k", type=int, default=30)
    ap_range.add_argument("--pre-base", type=int, default=0, help="Base pre-work repetitions")
    ap_range.add_argument("--pre-step", type=int, default=0, help="Delta pre-work per index")
    ap_range.add_argument("--pre-ops", type=int, default=8, help="Ops per pre-work repetition")
    ap_range.add_argument("--nops", type=int, default=0, help="Exact Ir control: add this many inline NOPs per file")
    ap_range.add_argument("--roi", action="store_true", help="Enable ROI measurement")
    ap_range.add_argument("--roi-region", choices=["nops", "loop"], default="nops")
    ap_range.add_argument("--roi-mode", choices=["func", "macro"], default="func")
    ap_range.set_defaults(func=cmd_gen_range)

    # Generate a grid over a range of CC values, each with k steps of iterations.
    ap_grid = sub.add_parser("gen-grid")
    ap_grid.add_argument("--out-dir", type=str, default="corpus_synth")
    ap_grid.add_argument("--cc-min", type=int, required=True)
    ap_grid.add_argument("--cc-max", type=int, required=True)
    ap_grid.add_argument("--base-iters", type=int, default=1000)
    ap_grid.add_argument("--step", type=int, default=100)
    ap_grid.add_argument("--k", type=int, default=30)
    ap_grid.add_argument("--ops-per-iter", type=int, default=8)
    ap_grid.add_argument("--no-loop-upto-cc", type=int, default=1, help="For cc <= N, disable loop and use pre-work")
    ap_grid.add_argument("--pre-base", type=int, default=1, help="Base pre-work repetitions for no-loop rows")
    ap_grid.add_argument("--pre-step", type=int, default=1, help="Delta pre-work per index for no-loop rows")
    ap_grid.add_argument("--pre-ops", type=int, default=8, help="Ops per pre-work repetition")
    ap_grid.add_argument("--exact-k", action="store_true", help="Use inline NOPs to achieve Ir = M_cc + k exactly (no loop)")
    ap_grid.add_argument("--roi", action="store_true", help="Enable ROI (recommended for exact-k)")
    ap_grid.add_argument("--roi-region", choices=["nops", "loop"], default="nops")
    ap_grid.add_argument("--roi-mode", choices=["func", "macro"], default="func")
    def _cmd_grid(args):
        out = pathlib.Path(args.out_dir)
        for cc in range(args.cc_min, args.cc_max + 1):
            for idx in range(args.k):
                if args.exact_k:
                    # Exact Ir control via NOPs: disable loop and pre-work, set nops=k
                    iters = 0
                    pre_steps = 0
                    nops = idx + 1
                    src = generate_c(cc, iters, args.ops_per_iter, pre_steps=pre_steps, pre_ops=args.pre_ops, nops=nops, roi=args.roi, roi_region=args.roi_region, roi_mode=args.roi_mode)
                    name = f"cc{cc:02d}_k{idx+1:02d}_iters{iters}_ops{args.ops_per_iter}_pre{pre_steps}x{args.pre_ops}_nops{nops}_roi{int(args.roi)}_{args.roi_region}_{args.roi_mode}.c"
                elif cc <= args.no_loop_upto_cc:
                    iters = 0
                    pre_steps = args.pre_base + idx * args.pre_step
                    src = generate_c(cc, iters, args.ops_per_iter, pre_steps=pre_steps, pre_ops=args.pre_ops)
                    name = f"cc{cc:02d}_idx{idx:03d}_iters{iters}_ops{args.ops_per_iter}_pre{pre_steps}x{args.pre_ops}.c"
                else:
                    iters = args.base_iters + idx * args.step
                    pre_steps = 0
                    src = generate_c(cc, iters, args.ops_per_iter, pre_steps=pre_steps, pre_ops=args.pre_ops)
                    name = f"cc{cc:02d}_idx{idx:03d}_iters{iters}_ops{args.ops_per_iter}_pre{pre_steps}x{args.pre_ops}.c"
                path = write_file(out, name, src)
                print(f"[gen-grid] Wrote: {path}")
    ap_grid.set_defaults(func=_cmd_grid)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

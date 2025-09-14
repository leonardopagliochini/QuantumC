#!/usr/bin/env python3
"""
Generate C programs that are fully compatible with the QuantumC pipeline.

Design (simplified and enforced):
- One function only: `main`.
- Only pipeline-accepted integer operations: +, -, *, /, and top-level `if`s.
- No globals, no helper functions, no ROI, no inline asm, no macros.
- No loops are emitted; instruction count is controlled via straight-line
  repetitions of simple arithmetic in `main` ("pre-work").

Cyclomatic complexity (CC):
- CC ~= 1 + (#top-level ifs). We set `#ifs = cc - 1`.

Instruction count (Ir):
- With `--pre-ops 1` each pre-work step adds one statement such as `a = a + b;`.
  At -O0 this increases Ir by ~3–4, keeping adjacent samples within ≤5.

CLI (simplified common flows):
- Generate a CC×k grid without loops:
    python tools/gen_cc_ir_programs.py gen-grid \
      --out-dir corpus_cc10x10_noloop \
      --cc-min 1 --cc-max 10 \
      --k 10 \
      --ops-per-iter 1 \
      --no-loop-upto-cc 10 \
      --pre-base 1 --pre-step 1 --pre-ops 1

Notes:
- This script emits only C; scanning/measurement is handled by tools/scan_cc_ir.py.
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
    """Disabled in simplified mode: we do not emit loops.

    Kept for API compatibility; always returns an empty string.
    """
    return ""


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

def _int_unit_lines(idx: int, use_globals: bool, ops_per_unit: int) -> list[str]:
    a = 'ga' if use_globals else 'a'
    b = 'gb' if use_globals else 'b'
    s = 'gs' if use_globals else 's'
    k = (idx % 5) + 1
    unit = []
    # Minimal ops that survive -O0 and map to MLIR/quantum ops.
    patterns = [
        f"  {a} = {a} + {k};\n",
        f"  {s} = {s} + {a};\n",
        f"  {b} = {b} + 1;\n",
        f"  {s} = {s} + {b};\n",
    ]
    for i in range(max(1, ops_per_unit)):
        unit.append(patterns[i % len(patterns)])
    return unit


def make_int_ops(count: int, use_globals: bool = False, ops_per_unit: int = 2) -> str:
    """Emit `count` integer-op units. Each unit has `ops_per_unit` statements.

    ops_per_unit controls the effective Ir slope per step. With our gcc -O0
    setup, 1 stmt ~= ~3–4 instructions; 2 stmts ~= ~7–8; 4 stmts ~= ~14–16.
    """
    if count <= 0:
        return ""
    lines: list[str] = []
    for i in range(int(count)):
        lines.extend(_int_unit_lines(i, use_globals=use_globals, ops_per_unit=ops_per_unit))
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
               roi_mode: str = "func",
               roi_unit_ops: int = 2,
               dup_main_roi: bool = True) -> str:
    """Create a C program with only pipeline-accepted ops in `main`.

    Simplified: no loops, no ROI, no globals, no inline asm.
    CC model: CC ~= 1 + n_if, where n_if = max(0, cc_target - 1).
    Ir control: straight-line pre-work repeated `pre_steps` times with `pre_ops`
    statements per step (default `ops_per_iter` if not specified).
    """
    n_if = max(0, cc_target - 1)
    parts: List[str] = []
    # Begin main
    parts.append(MAIN_BEGIN)
    # Straight-line pre-work to vary Ir without adding loop CC
    if pre_steps > 0:
        parts.append(make_prework(pre_steps, pre_ops if pre_ops is not None else ops_per_iter))
    # Top-level if chain to reach CC target
    if n_if > 0:
        parts.append(make_if_chain(n_if))
    # Footer
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
    # ROI/loops are disabled in simplified mode; the flags are ignored if present.
    def _cmd_grid(args):
        out = pathlib.Path(args.out_dir)
        for cc in range(args.cc_min, args.cc_max + 1):
            for idx in range(args.k):
                # Simplified mode: always no loops, Ir via pre-work only
                iters = 0
                pre_steps = args.pre_base + idx * args.pre_step
                src = generate_c(cc, iters, args.ops_per_iter, pre_steps=pre_steps, pre_ops=args.pre_ops)
                name = f"cc{cc:02d}_idx{idx:03d}_iters{iters}_ops{args.ops_per_iter}_pre{pre_steps}x{args.pre_ops}.c"
                path = write_file(out, name, src)
                print(f"[gen-grid] Wrote: {path}")
    ap_grid.set_defaults(func=_cmd_grid)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

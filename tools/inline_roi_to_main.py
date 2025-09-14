#!/usr/bin/env python3
"""
Inline/flatten ROI-based C programs into a single-main form acceptable to the
current toolchain, without modifying the toolchain itself.

What it does (pattern-based, tailored to tools/gen_cc_ir_programs.py output):
  - Removes `static int ga=1, gb=2, gs=0;` globals.
  - Removes the `void __attribute__((noinline)) roi_block(void) { ... }` helper.
  - Optionally inlines its body at the call site in main, rewriting `ga/gb/gs`
    to local `a/b/s` (disabled by default to avoid double-counting, because the
    generator already duplicates ROI ops in main).
  - Removes the `roi_block();` call in main.

This keeps only local `int` arithmetic inside `main`, which the pipeline can
lower to MLIR and QASM. Use the output folder as the corpus for benchmarking.

Usage:
  python tools/inline_roi_to_main.py --in corpus_grid10 --out corpus_grid10_flat

Optional:
  --inline-body  # also insert roi_block body (mapped to a/b/s) at the call site

Limitations:
  - Assumes the generator's structure and naming.
  - Best-effort text rewriting; not a full C parser.
"""

from __future__ import annotations

import argparse
import pathlib
import re
from typing import Tuple


ROI_GLOBAL_RE = re.compile(r"^\s*static\s+int\s+ga\s*=\s*\d+\s*,\s*gb\s*=\s*\d+\s*,\s*gs\s*=\s*\d+\s*;\s*$")
ROI_FUNC_START_RE = re.compile(r"^\s*void\s+__attribute__\(\(noinline\)\)\s+roi_block\s*\(\s*void\s*\)\s*\{\s*$")
ROI_CALL_RE = re.compile(r"^([ \t]*)roi_block\s*\(\s*\)\s*;\s*$")


def _extract_roi_body(lines: list[str], start_idx: int) -> Tuple[list[str], int]:
    """Extract lines inside the roi_block function starting at start_idx.

    Returns (body_lines, end_idx_after_func).
    """
    body: list[str] = []
    depth = 0
    i = start_idx
    # consume the opening line
    if i < len(lines):
        # count opening brace
        if "{" in lines[i]:
            depth += lines[i].count("{")
            depth -= lines[i].count("}")
        i += 1
    # read until matching '}'
    while i < len(lines):
        line = lines[i]
        depth += line.count("{")
        depth -= line.count("}")
        if depth <= 0:
            # we've reached the closing brace line; do not include it
            i += 1
            break
        body.append(line)
        i += 1
    return body, i


TOP_HEADER = (
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


SINK_RE = re.compile(r"^\s*sink\s*=\s*")


def _ensure_header(text: str) -> str:
    # Insert header/defines if not already present. Do not rely on mere usage
    # of macros to decide; check for include or defines explicitly.
    if ("<valgrind/callgrind.h>" in text
            or "define CALLGRIND_START_INSTRUMENTATION" in text
            or "define CALLGRIND_ZERO_STATS" in text):
        return text
    return TOP_HEADER + text


def transform_source(src: str, inline_body: bool = False, instrument: bool = False) -> str:
    lines = src.splitlines()

    # 1) Remove ROI global declaration
    new_lines: list[str] = []
    for line in lines:
        if ROI_GLOBAL_RE.match(line):
            continue
        new_lines.append(line)
    lines = new_lines

    # 2) Remove roi_block function, optionally keep its body for insertion
    roi_body: list[str] | None = None
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if ROI_FUNC_START_RE.match(line):
            body, j = _extract_roi_body(lines, i)
            if inline_body:
                roi_body = body
            i = j
            continue
        out.append(line)
        i += 1
    lines = out

    # 3) Replace the roi_block() call in main, optionally insert body mapped to locals
    out = []
    pending_stop = False
    pending_indent = ""
    for line in lines:
        m = ROI_CALL_RE.match(line)
        if m:
            indent = m.group(1)
            # drop the call; optionally insert transformed body
            if instrument:
                out.append(indent + "CALLGRIND_ZERO_STATS;")
                out.append(indent + "CALLGRIND_START_INSTRUMENTATION;")
                if not inline_body:
                    # we'll stop at the sink assignment or return
                    pending_stop = True
                    pending_indent = indent
            if inline_body and roi_body:
                for b in roi_body:
                    # remap globals -> locals and normalize indentation
                    b2 = b.replace("ga", "a").replace("gb", "b").replace("gs", "s")
                    out.append(indent + b2.strip())
                if instrument:
                    out.append(indent + "CALLGRIND_STOP_INSTRUMENTATION;")
            # else: nothing (call removed)
            continue
        # if we have a pending stop marker, insert before sink assignment
        if pending_stop and (SINK_RE.match(line) or line.strip().startswith("return")):
            out.append(pending_indent + "CALLGRIND_STOP_INSTRUMENTATION;")
            pending_stop = False
        out.append(line)
    new_text = "\n".join(out) + ("\n" if src.endswith("\n") else "")
    if instrument:
        new_text = _ensure_header(new_text)
    return new_text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_dir", type=str, required=True, help="Input corpus directory with .c files")
    ap.add_argument("--out", dest="out_dir", type=str, required=True, help="Output directory for flattened files")
    ap.add_argument("--inline-body", action="store_true", help="Inline roi_block body into main, mapping ga/gb/gs to a/b/s")
    ap.add_argument("--instrument", action="store_true", help="Wrap ROI region in main with CALLGRIND_* macros and add header if available")
    args = ap.parse_args()

    in_dir = pathlib.Path(args.in_dir)
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for c_path in sorted(in_dir.glob("*.c")):
        src = c_path.read_text()
        new_src = transform_source(src, inline_body=args.inline_body, instrument=args.instrument)
        (out_dir / c_path.name).write_text(new_src)
        print(f"[flatten] Wrote: {out_dir / c_path.name}")


if __name__ == "__main__":
    main()

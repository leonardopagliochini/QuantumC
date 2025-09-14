#!/usr/bin/env python3
"""
Normalize the `ir_instructions` column in a CSV by removing a baseline offset.

By default, if a `cyclomatic` column exists, the baseline is computed per
cyclomatic value as the minimum `ir_instructions` within that group so that
each group's smallest value becomes 0 (or 1 with --start-one). If `cyclomatic`
is absent or `--global` is passed, the baseline is the global minimum.

Only the `ir_instructions` column is modified; all other columns are preserved
as-is. The output file name appends `_k` before the extension.

Usage:
  python tools/remove_ir_baseline.py path/to/metrics.csv
  python tools/remove_ir_baseline.py --global --start-one metrics.csv

Options:
  --global       Use a single baseline (global min) for all rows.
  --group COL    Grouping column(s) to compute per-group baseline (default:
                 `cyclomatic` if present). Can be repeated.
  --start-one    Make the minimum become 1 instead of 0.
  --out PATH     Explicit output path (otherwise `<input>_k.csv`).
"""

import argparse
import csv
import os
from collections import defaultdict
from typing import List, Dict, Tuple


def infer_output_path(inp: str) -> str:
    root, ext = os.path.splitext(inp)
    if not ext:
        return inp + "_k"
    return f"{root}_k{ext}"


def to_int(s: str):
    try:
        return int(s)
    except Exception:
        try:
            return int(float(s))
        except Exception:
            return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=str, help="Input CSV path")
    ap.add_argument("--global", dest="use_global", action="store_true", help="Use global min baseline")
    ap.add_argument("--group", dest="groups", action="append", default=None, help="Grouping column (repeatable)")
    ap.add_argument("--start-one", action="store_true", help="Shift so minimum becomes 1 (instead of 0)")
    ap.add_argument("--out", type=str, default=None, help="Output CSV path (default: append _k)")
    args = ap.parse_args()

    with open(args.csv, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows: List[Dict[str, str]] = list(r)
        fieldnames = r.fieldnames or []

    if "ir_instructions" not in fieldnames:
        raise SystemExit("Input CSV lacks 'ir_instructions' column")

    # Determine grouping columns
    groups = args.groups
    if not args.use_global and groups is None:
        # Default grouping: per-cyclomatic if available
        groups = ["cyclomatic"] if "cyclomatic" in fieldnames else []
    if args.use_global:
        groups = []

    # Compute baselines
    baselines: Dict[Tuple, int] = {}
    if not groups:
        # Global min
        min_ir = None
        for row in rows:
            ir = to_int(row.get("ir_instructions", ""))
            if ir is None:
                continue
            min_ir = ir if min_ir is None else min(min_ir, ir)
        baselines[()] = min_ir if min_ir is not None else 0
    else:
        # Per-group min
        mins: Dict[Tuple, int] = {}
        for row in rows:
            key = tuple(row.get(g, "") for g in groups)
            ir = to_int(row.get("ir_instructions", ""))
            if ir is None:
                continue
            if key not in mins:
                mins[key] = ir
            else:
                mins[key] = min(mins[key], ir)
        baselines = mins

    # Produce normalized rows
    out_rows: List[Dict[str, str]] = []
    for row in rows:
        src = row.get("ir_instructions", "")
        ir = to_int(src)
        if ir is None:
            # leave untouched if not numeric
            out_rows.append(row)
            continue
        key = () if not groups else tuple(row.get(g, "") for g in groups)
        base = baselines.get(key, 0)
        k = ir - base + (1 if args.start_one else 0)
        new_row = dict(row)
        new_row["ir_instructions"] = str(k)
        out_rows.append(new_row)

    out_path = args.out or infer_output_path(args.csv)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    print(f"[DONE] Wrote: {out_path}")


if __name__ == "__main__":
    main()


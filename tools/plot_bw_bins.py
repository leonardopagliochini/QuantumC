#!/usr/bin/env python3
"""
Plot a black/white presence heatmap over fixed-size bins.

Black = at least one program exists in that (x,y) bin
White = no program exists in that (x,y) bin

Typical usage (10x10 bins: CC width=1, IR width=5):
  python tools/plot_bw_bins.py \
    --csv tools/results/corpus_grid10_introi_cc_ir.csv \
    --x cyclomatic --y ir_instructions \
    --x-bin-w 1 --y-bin-w 5 \
    --x-min 1 --x-max 10 --y-min 0 --y-max 150 \
    --out tools/results/corpus_grid10_introi_bins5_bw_v2.png

Notes
- Only the specified columns are used; other columns are ignored.
- If min/max are not provided, they are inferred from the data. The max bin
  is extended by one width so that the last value falls within a bin.
"""

import argparse
import csv
import os
from typing import List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=str, required=True)
    ap.add_argument("--x", type=str, default="cyclomatic")
    ap.add_argument("--y", type=str, default="ir_instructions")
    ap.add_argument("--x-bin-w", type=float, required=True)
    ap.add_argument("--y-bin-w", type=float, required=True)
    ap.add_argument("--x-min", type=float, default=None)
    ap.add_argument("--x-max", type=float, default=None)
    ap.add_argument("--y-min", type=float, default=None)
    ap.add_argument("--y-max", type=float, default=None)
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--title", type=str, default=None)
    ap.add_argument("--figsize", type=float, nargs=2, default=(12.0, 8.0))
    return ap.parse_args()


def load_pairs(path: str, xcol: str, ycol: str) -> List[Tuple[float, float]]:
    rows: List[Tuple[float, float]] = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if xcol not in row or ycol not in row:
                continue
            try:
                x = float(row[xcol])
                y = float(row[ycol])
            except Exception:
                continue
            rows.append((x, y))
    return rows


def compute_edges(vmin: float, vmax: float, width: float) -> List[float]:
    if width <= 0:
        raise ValueError("bin width must be positive")
    # Ensure at least one bin
    if vmax <= vmin:
        vmax = vmin + width
    # Extend to include the last value on the rightmost edge
    n = int((vmax - vmin) / width + 0.999999)
    edges = [vmin + i * width for i in range(n + 1)]
    return edges


def bin_index(v: float, edges: List[float]) -> int:
    if v <= edges[0]:
        return 0
    if v >= edges[-1]:
        return len(edges) - 2
    lo, hi = 0, len(edges) - 1
    # binary search
    while lo < hi:
        mid = (lo + hi) // 2
        if v < edges[mid]:
            hi = mid
        else:
            lo = mid + 1
    return max(0, lo - 1)


def main() -> None:
    args = parse_args()
    pairs = load_pairs(args.csv, args.x, args.y)
    if not pairs:
        raise SystemExit("No valid rows found with selected columns")

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    xmin = args.x_min if args.x_min is not None else min(xs)
    xmax = args.x_max if args.x_max is not None else max(xs)
    ymin = args.y_min if args.y_min is not None else min(ys)
    ymax = args.y_max if args.y_max is not None else max(ys)

    x_edges = compute_edges(xmin, xmax, args.x_bin_w)
    y_edges = compute_edges(ymin, ymax, args.y_bin_w)

    W = len(x_edges) - 1
    H = len(y_edges) - 1
    M = [[0 for _ in range(W)] for _ in range(H)]

    for x, y in pairs:
        bx = bin_index(x, x_edges)
        by = bin_index(y, y_edges)
        M[by][bx] = 1  # presence

    # Make a figure
    fig, ax = plt.subplots(figsize=tuple(args.figsize))
    cmap = ListedColormap(["white", "black"])  # 0->white, 1->black
    im = ax.imshow(M, origin="lower", aspect="auto", cmap=cmap, vmin=0, vmax=1)

    # Ticks at bin centers
    def centers(edges: List[float]) -> List[float]:
        return [(edges[i] + edges[i+1]) / 2.0 for i in range(len(edges)-1)]
    x_cent = centers(x_edges)
    y_cent = centers(y_edges)

    # Limit tick count for readability
    def pick_ticks(vals: List[float], max_ticks: int = 20) -> List[int]:
        if len(vals) <= max_ticks:
            return list(range(len(vals)))
        step = max(1, len(vals) // max_ticks)
        return list(range(0, len(vals), step))

    xi = pick_ticks(x_cent, max_ticks=15)
    yi = pick_ticks(y_cent, max_ticks=15)
    ax.set_xticks(xi)
    ax.set_xticklabels([f"{x_cent[i]:.0f}" for i in xi], rotation=45, ha="right")
    ax.set_yticks(yi)
    ax.set_yticklabels([f"{y_cent[i]:.0f}" for i in yi])

    ax.set_xlabel(args.x)
    ax.set_ylabel(args.y)
    if args.title:
        ax.set_title(args.title)
    fig.tight_layout()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=200)
    plt.close(fig)
    print(f"[DONE] Saved: {args.out}")


if __name__ == "__main__":
    main()


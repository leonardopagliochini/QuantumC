#!/usr/bin/env python3
import argparse
import math
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import csv
import matplotlib.pyplot as plt


REQUIRED_COLS = [
    "file",
    "cyclomatic",
    "ir_instructions",
    "num_qubits",
    "num_gates",
    "num_cx",
    "num_measure",
    "num_u1",
    "num_u2",
    "num_u3",
    "depth",
    "wall_time_s",
    "user_time_s",
    "sys_time_s",
    "max_rss_kb",
]


def ensure_outdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def ir_bin_start(v: float, width: int) -> int:
    """Return the left edge (start) of the IR bin of size `width`.

    Binning rule: floor to the nearest lower multiple of `width`.
    Example: width=5 → 132821→132820, 132823→132820, 132825→132825.
    Note: If you prefer a different convention (e.g., treating values that are
    exactly `start+width-1` specially), adjust here.
    """
    if width <= 0:
        raise ValueError("ir_bin_width must be > 0")
    return int((int(v) // width) * width)


def ir_bin_center(start: int, width: int) -> float:
    return start + (width - 1) / 2.0


def validate_columns(df) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"CSV missing required columns: {missing}. Found: {list(df.columns)}"
        )


def read_csv(path: str) -> List[Dict[str, object]]:
    try:
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames or []
            df_rows: List[Dict[str, object]] = []
            for row in reader:
                df_rows.append(row)
    except Exception as e:
        raise RuntimeError(f"Failed to read CSV '{path}': {e}")
    # Validate columns using the header row
    dummy_df = type("Dummy", (), {"columns": set(cols)})
    validate_columns(dummy_df)  # type: ignore[arg-type]
    return df_rows


def agg_heatmap(
    rows: List[Dict[str, object]],
    metric: str,
    ir_width: int,
) -> Tuple[np.ndarray, List[int], List[int]]:
    """Aggregate to a CC×IR-binned grid for a given metric (mean).

    Returns (grid, sorted_ir_bins, sorted_ccs)
    - grid: shape (len(ir_bins), len(ccs)), NaN where no data
    """
    # Collect values per (ir_bin, cc)
    bucket: Dict[Tuple[int, int], List[float]] = {}
    ir_bins_set: set[int] = set()
    ccs_set: set[int] = set()
    for r in rows:
        try:
            cc = int(float(r["cyclomatic"]))
            ir = int(float(r["ir_instructions"]))
            val = float(r[metric])
        except Exception:
            continue
        ir_b = ir_bin_start(ir, ir_width)
        key = (ir_b, cc)
        ir_bins_set.add(ir_b)
        ccs_set.add(cc)
        bucket.setdefault(key, []).append(val)

    ir_bins = sorted(ir_bins_set)
    ccs = sorted(ccs_set)
    if not ir_bins or not ccs:
        return np.empty((0, 0)), ir_bins, ccs

    grid = np.full((len(ir_bins), len(ccs)), np.nan, dtype=float)
    ir_idx = {b: i for i, b in enumerate(ir_bins)}
    cc_idx = {c: j for j, c in enumerate(ccs)}
    for (ir_b, cc), vals in bucket.items():
        i = ir_idx[ir_b]
        j = cc_idx[cc]
        grid[i, j] = float(np.mean(vals))
    return grid, ir_bins, ccs


def save_heatmap(
    grid: np.ndarray,
    ir_bins: List[int],
    ccs: List[int],
    metric: str,
    out_path: str,
    ir_width: int,
    dataset_tag: str,
) -> None:
    if grid.size == 0:
        print(f"[warn] Heatmap for {metric}: no data to plot; skipping {out_path}")
        return

    # Figure size proportional to data
    fig_w = max(6, min(18, len(ccs) * 0.6))
    fig_h = max(6, min(18, len(ir_bins) * 0.15))
    plt.figure(figsize=(fig_w, fig_h))

    # Show heatmap
    im = plt.imshow(grid, aspect="auto", origin="lower", cmap="viridis")

    # Add colorbar
    cbar = plt.colorbar(im)

    # Axis ticks
    plt.xticks(ticks=np.arange(len(ccs)), labels=ccs, rotation=0)
    plt.yticks(ticks=np.arange(len(ir_bins)), labels=ir_bins)

    # Axis labels
    plt.xlabel("Cyclomatic Complexity")
    plt.ylabel("IR instructions")

    # Layout and save
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()



# ---------- Profile fitting utilities ----------

@dataclass
class FitResult:
    name: str
    params: Dict[str, float]
    y_pred: np.ndarray
    r2: float
    aic: float


def _r2_aic(y: np.ndarray, y_pred: np.ndarray, k_params: int) -> Tuple[float, float]:
    eps = 1e-12
    y = np.asarray(y, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2) + eps
    r2 = 1.0 - ss_res / (ss_tot + eps)
    n = max(len(y), 1)
    # AIC for least-squares with Gaussian errors (up to constant): n*ln(RSS/n) + 2k
    aic = n * np.log((ss_res + eps) / max(n, 1)) + 2 * k_params
    return r2, aic


def try_linear(x: np.ndarray, y: np.ndarray) -> Optional[FitResult]:
    if len(x) < 2:
        return None
    b, a = np.polyfit(x, y, 1)  # slope, intercept
    y_pred = a + b * x
    r2, aic = _r2_aic(y, y_pred, k_params=2)
    return FitResult("linear", {"a": float(a), "b": float(b)}, y_pred, r2, aic)


def try_quadratic(x: np.ndarray, y: np.ndarray) -> Optional[FitResult]:
    if len(x) < 3:
        return None
    c, b, a = np.polyfit(x, y, 2)  # ax^2 + bx + c but numpy returns [c2, c1, c0]
    y_pred = a + b * x + c * x * x
    r2, aic = _r2_aic(y, y_pred, k_params=3)
    return FitResult("quadratic", {"a": float(a), "b": float(b), "c": float(c)}, y_pred, r2, aic)


def try_exponential(x: np.ndarray, y: np.ndarray) -> Optional[FitResult]:
    # y = A * exp(B * x_norm), with x_norm = (x - x0) / sx to avoid overflow
    mask = (y > 0)
    if np.count_nonzero(mask) < 2:
        return None
    x2 = x[mask]
    ly = np.log(y[mask])
    # Normalize x to a small range
    x0 = float(np.mean(x2))
    sx = float(np.ptp(x2))
    if not np.isfinite(sx) or sx == 0.0:
        sx = 1.0
    x2n = (x2 - x0) / sx
    try:
        b, a_log = np.polyfit(x2n, ly, 1)
    except Exception:
        return None
    A = math.exp(a_log)
    # Predictions using normalized x to keep exponents moderate
    xn_full = (x - x0) / sx
    with np.errstate(over='ignore', invalid='ignore'):
        y_pred_full = A * np.exp(b * xn_full)
        y_pred_mask = A * np.exp(b * x2n)
    if not (np.all(np.isfinite(y_pred_mask)) and np.all(np.isfinite(y_pred_full))):
        return None
    r2, aic = _r2_aic(y[mask], y_pred_mask, k_params=2)
    return FitResult("exponential", {"A": float(A), "B": float(b), "x0": x0, "sx": sx}, y_pred_full, r2, aic)


def try_power(x: np.ndarray, y: np.ndarray) -> Optional[FitResult]:
    # y = A * (x/x_ref)^B -> log y = log A + B * log(x/x_ref)
    mask = (x > 0) & (y > 0)
    if np.count_nonzero(mask) < 2:
        return None
    x2 = x[mask]
    y2 = y[mask]
    x_ref = float(np.max(x2))
    if not np.isfinite(x_ref) or x_ref <= 0:
        return None
    xr = x2 / x_ref
    # Clamp xr to avoid log(0)
    xr = np.clip(xr, 1e-300, 1.0)
    lx = np.log(xr)
    ly = np.log(y2)
    try:
        B, a_log = np.polyfit(lx, ly, 1)
    except Exception:
        return None
    A = math.exp(a_log)
    # Predictions on original x via ratio to x_ref
    x_full_r = np.clip(x / x_ref, 1e-300, np.inf)
    with np.errstate(over='ignore', invalid='ignore'):
        y_pred_full = A * (x_full_r ** B)
        y_pred_mask = A * ((xr) ** B)
    if not (np.all(np.isfinite(y_pred_mask)) and np.all(np.isfinite(y_pred_full))):
        return None
    r2, aic = _r2_aic(y2, y_pred_mask, k_params=2)
    return FitResult("power", {"A": float(A), "B": float(B), "x_ref": x_ref}, y_pred_full, r2, aic)


def best_fit(x: np.ndarray, y: np.ndarray) -> Optional[FitResult]:
    candidates = [
        try_linear(x, y),
        try_quadratic(x, y),
        try_exponential(x, y),
        try_power(x, y),
    ]
    cands = [c for c in candidates if c is not None]
    if not cands:
        return None
    # Choose by lowest AIC; tie-break by higher R^2 then fewer params
    cands.sort(key=lambda fr: (fr.aic, -fr.r2, len(fr.params)))
    return cands[0]


def plot_profile(
    x: np.ndarray,
    y: np.ndarray,
    xlabel: str,
    ylabel: str,
    title: str,
    out_path_plain: str,
    out_path_fit: str,
    dataset_tag: str,
) -> None:
    # Plain profile
    plt.figure(figsize=(8, 5))
    plt.plot(x, y, marker="o", linestyle="-", label="mean")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    # no title per request
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path_plain)
    plt.close()

    # With fit/study
    fr = best_fit(x, y)
    plt.figure(figsize=(8, 5))
    plt.scatter(x, y, label="mean", color="#1f77b4")
    if fr is not None:
        xs = np.linspace(float(np.min(x)), float(np.max(x)), num=200)
        # Recompute fitted y over dense xs for smooth curve
        if fr.name == "linear":
            a, b = fr.params["a"], fr.params["b"]
            ys = a + b * xs
            model_str = f"y = {a:.3g} + {b:.3g} x"
        elif fr.name == "quadratic":
            a, b, c = fr.params["a"], fr.params["b"], fr.params["c"]
            ys = a + b * xs + c * xs * xs
            model_str = f"y = {a:.3g} + {b:.3g} x + {c:.3g} x^2"
        elif fr.name == "exponential":
            A, B = fr.params["A"], fr.params["B"]
            x0 = fr.params.get("x0", 0.0)
            sx = fr.params.get("sx", 1.0)
            xs_n = (xs - x0) / sx
            ys = A * np.exp(B * xs_n)
            model_str = f"y = {A:.3g} * exp({B:.3g} * (x-{x0:.3g})/{sx:.3g})"
        elif fr.name == "power":
            A, B = fr.params["A"], fr.params["B"]
            x_ref = fr.params.get("x_ref", float(np.max(xs)) if len(xs) else 1.0)
            xr = np.clip(xs / x_ref, 1e-300, np.inf)
            ys = A * (xr ** B)
            model_str = f"y = {A:.3g} * (x/{x_ref:.3g})^{B:.3g}"
        else:
            xs = None
            ys = None
            model_str = ""

        if xs is not None:
            plt.plot(xs, ys, color="#d62728", label=f"fit: {fr.name}")
            txt = f"best: {fr.name}\nR^2={fr.r2:.3f}\nAIC={fr.aic:.2f}\n{model_str}"
            plt.gca().text(
                0.02,
                0.98,
                txt,
                transform=plt.gca().transAxes,
                va="top",
                ha="left",
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#555", alpha=0.8),
            )

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    # no title per request
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path_fit)
    plt.close()


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Generate analysis plots from metrics CSV.")
    p.add_argument("--csv", required=True, help="Path to input CSV with required columns")
    p.add_argument(
        "--outdir",
        default=os.path.join("tools", "results", "plots"),
        help="Output directory for plots (default: tools/results/plots)",
    )
    p.add_argument(
        "--ir-bin-width",
        type=int,
        default=5,
        help="IR bin width for heatmaps and profiles by IR (default: 5)",
    )
    args = p.parse_args(argv)

    csv_path = args.csv
    outdir = args.outdir
    ir_w = int(args.ir_bin_width)
    ensure_outdir(outdir)

    rows = read_csv(csv_path)
    # Pre-augment rows with helper fields
    for r in rows:
        try:
            r["cc"] = int(float(r["cyclomatic"]))
        except Exception:
            r["cc"] = None
        try:
            ir_val = int(float(r["ir_instructions"]))
        except Exception:
            ir_val = None
        r["ir_val"] = ir_val
        r["ir_bin"] = ir_bin_start(ir_val, ir_w) if ir_val is not None else None
        r["ir_center"] = ir_bin_center(r["ir_bin"], ir_w) if r["ir_bin"] is not None else None
        try:
            ut = float(r["user_time_s"]) if r["user_time_s"] != "" else 0.0
        except Exception:
            ut = 0.0
        try:
            st = float(r["sys_time_s"]) if r["sys_time_s"] != "" else 0.0
        except Exception:
            st = 0.0
        r["time_user_sys_s"] = ut + st

    dataset_tag = os.path.splitext(os.path.basename(csv_path))[0]

    # 1) Heatmaps for num_qubits, num_gates, depth
    for metric in ["num_qubits", "num_gates", "depth"]:
        grid, ir_bins, ccs = agg_heatmap(rows, metric, ir_w)
        fname = f"heatmap_{metric}_x-cc_y-ir{ir_w}_{dataset_tag}.pdf"
        save_heatmap(grid, ir_bins, ccs, metric, os.path.join(outdir, fname), ir_w, dataset_tag)

    # 2) Profiles by CC and by IR (plain and with fit) for 3 metrics
    # Profiles by CC: group by CC, take mean of metrics
    # Build per-CC means
    cc_to_vals: Dict[int, Dict[str, List[float]]] = {}
    for r in rows:
        cc = r.get("cc")
        if cc is None:
            continue
        d = cc_to_vals.setdefault(cc, {"num_qubits": [], "num_gates": [], "depth": []})
        try:
            d["num_qubits"].append(float(r["num_qubits"]))
            d["num_gates"].append(float(r["num_gates"]))
            d["depth"].append(float(r["depth"]))
        except Exception:
            continue
    ccs_sorted = sorted(cc_to_vals.keys())
    x_cc = np.array([float(c) for c in ccs_sorted], dtype=float)
    for metric in ["num_qubits", "num_gates", "depth"]:
        y = np.array([np.mean(cc_to_vals[c][metric]) for c in ccs_sorted], dtype=float)
        title = f"Profile of {metric} vs CC"
        out_plain = os.path.join(outdir, f"profile_cc_{metric}_mean_{dataset_tag}.pdf")
        out_fit = os.path.join(outdir, f"profile_cc_{metric}_fit_{dataset_tag}.pdf")
        plot_profile(x_cc, y, "Cyclomatic Complexity", metric, title, out_plain, out_fit, dataset_tag)

    # Profiles by IR bin centers: group by IR bin
    # Build per-IR-bin means
    ir_to_vals: Dict[int, Dict[str, List[float]]] = {}
    for r in rows:
        irb = r.get("ir_bin")
        if irb is None:
            continue
        d = ir_to_vals.setdefault(int(irb), {"num_qubits": [], "num_gates": [], "depth": []})
        try:
            d["num_qubits"].append(float(r["num_qubits"]))
            d["num_gates"].append(float(r["num_gates"]))
            d["depth"].append(float(r["depth"]))
        except Exception:
            continue
    if ir_to_vals:
        ir_bins_sorted = sorted(ir_to_vals.keys())
        x_ir = np.array([ir_bin_center(int(b), ir_w) for b in ir_bins_sorted], dtype=float)
        for metric in ["num_qubits", "num_gates", "depth"]:
            y = np.array([np.mean(ir_to_vals[b][metric]) for b in ir_bins_sorted], dtype=float)
            title = f"Profile of {metric} vs IR"
            out_plain = os.path.join(outdir, f"profile_ir{ir_w}_{metric}_mean_{dataset_tag}.pdf")
            out_fit = os.path.join(outdir, f"profile_ir{ir_w}_{metric}_fit_{dataset_tag}.pdf")
            plot_profile(x_ir, y, "IR instructions", metric, title, out_plain, out_fit, dataset_tag)

    # 3) Diagonal plots: time(user+sys) and max_rss_kb vs normalized product of (CC × IR center)
    # Build pivot tables on the same CC×IR grid (mean aggregation)
    # Aggregated grid for time and memory
    tm_bucket: Dict[Tuple[int, int], List[float]] = {}
    rss_bucket: Dict[Tuple[int, int], List[float]] = {}
    ir_bins_sorted_set: set[int] = set()
    ccs_sorted_set: set[int] = set()
    for r in rows:
        irb = r.get("ir_bin")
        cc = r.get("cc")
        if irb is None or cc is None:
            continue
        key = (int(irb), int(cc))
        ir_bins_sorted_set.add(int(irb))
        ccs_sorted_set.add(int(cc))
        try:
            tm_bucket.setdefault(key, []).append(float(r["time_user_sys_s"]))
        except Exception:
            pass
        try:
            rss_bucket.setdefault(key, []).append(float(r["max_rss_kb"]))
        except Exception:
            pass

    ir_bins_sorted = sorted(ir_bins_sorted_set)
    ccs_sorted = sorted(ccs_sorted_set)
    n_diag = min(len(ir_bins_sorted), len(ccs_sorted))

    xs_prod: List[float] = []
    ys_time: List[float] = []
    ys_rss: List[float] = []
    used_pairs: List[Tuple[int, int]] = []
    for i in range(n_diag):
        ir_b = ir_bins_sorted[i]
        cc_v = ccs_sorted[i]
        # mean values from the aggregated grid
        key = (ir_b, cc_v)
        time_val = float(np.mean(tm_bucket[key])) if key in tm_bucket else float("nan")
        rss_val = float(np.mean(rss_bucket[key])) if key in rss_bucket else float("nan")
        if not (np.isnan(time_val) or np.isnan(rss_val)):
            prod = float(cc_v) * ir_bin_center(int(ir_b), ir_w)
            xs_prod.append(prod)
            ys_time.append(time_val)
            ys_rss.append(rss_val)
            used_pairs.append((cc_v, ir_b))

    if xs_prod:
        xs_prod = np.array(xs_prod, dtype=float)
        # Normalize product by maximum so x in [0,1]
        max_prod = float(np.max(xs_prod))
        if max_prod <= 0:
            x_norm = xs_prod
        else:
            x_norm = xs_prod / max_prod

        # Plot time(user+sys)
        plt.figure(figsize=(8, 5))
        plt.plot(x_norm, ys_time, marker="o", linestyle="-", color="#1f77b4")
        plt.xlabel("Normalized product: CC × IR")
        plt.ylabel("user_time_s + sys_time_s (mean)")
        # no title per request
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, f"diag_normprod_ccxir{ir_w}_time_{dataset_tag}.pdf"))
        plt.close()

        # Plot memory usage
        plt.figure(figsize=(8, 5))
        plt.plot(x_norm, ys_rss, marker="o", linestyle="-", color="#2ca02c")
        plt.xlabel("Normalized product: CC × IR")
        plt.ylabel("max_rss_kb (mean)")
        # no title per request
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, f"diag_normprod_ccxir{ir_w}_maxrss_{dataset_tag}.pdf"))
        plt.close()

    else:
        print("[warn] No diagonal cells with data found; skipping diagonal time/memory plots.")

    print(f"Saved plots to: {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

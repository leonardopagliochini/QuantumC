"""Analysis utilities for benchmarking studies."""

from __future__ import annotations

import csv
import math
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

COEFF_ABS_THRESHOLD = 0.01
COEFF_REL_THRESHOLD = 0.01


@dataclass
class ScatterConfig:
    name: str
    outfile: str
    x: str
    ys: List[str]
    style: str = "scatter"
    title: Optional[str] = None
    xlabel: Optional[str] = None
    ylabel: Optional[str] = None
    palette: Optional[str] = None
    legend: bool = True
    log_x: bool = False
    log_y: bool = False
    alpha: float = 0.8
    marker: str = "o"
    grid: bool = True
    fit: bool = False
    fit_models: List[str] = field(default_factory=lambda: [
        "linear",
        "quadratic",
        "cubic",
        "exp",
        "exp2",
        "exp3",
    ])
    fit_outfile: Optional[str] = None
    fit_title: Optional[str] = None
    fit_summary_csv: Optional[str] = None


@dataclass
class FitConfig:
    name: str
    outfile: str
    x: str
    y: str
    models: List[str] = field(default_factory=lambda: [
        "linear",
        "quadratic",
        "cubic",
        "exp",
        "exp2",
        "exp3",
    ])
    title: Optional[str] = None
    xlabel: Optional[str] = None
    ylabel: Optional[str] = None
    palette: Optional[str] = None
    scatter: bool = True
    log_x: bool = False
    log_y: bool = False
    summary_csv: Optional[str] = None


@dataclass
class HeatmapConfig:
    name: str
    outfile: str
    x: str
    y: str
    value: Optional[str] = None
    agg: str = "mean"
    title: Optional[str] = None
    xlabel: Optional[str] = None
    ylabel: Optional[str] = None
    palette: Optional[str] = None
    x_bins: Optional[int] = None
    y_bins: Optional[int] = None
    x_bin_width: Optional[float] = None
    y_bin_width: Optional[float] = None
    x_min: Optional[float] = None
    x_max: Optional[float] = None
    y_min: Optional[float] = None
    y_max: Optional[float] = None
    log_x: bool = False
    log_y: bool = False
    log_value: bool = False
    annotate: bool = False


@dataclass
class AnalyzeConfig:
    palette: str = "viridis"
    scatter_plots: List[ScatterConfig] = field(default_factory=list)
    heatmaps: List[HeatmapConfig] = field(default_factory=list)


def load_metrics_table(csv_path: pathlib.Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    data: List[Dict[str, Any]] = []
    columns: List[str] = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        for row in reader:
            entry: Dict[str, Any] = {}
            for key in columns:
                value = row.get(key)
                if key == "file":
                    entry[key] = value
                    continue
                if value is None or value == "":
                    entry[key] = None
                    continue
                try:
                    entry[key] = float(value)
                except Exception:
                    entry[key] = value
            data.append(entry)
    return data, columns


def _ensure_positive(values: np.ndarray, label: str) -> np.ndarray:
    positive_mask = values > 0
    if not positive_mask.any():
        raise ValueError(f"All values for {label} are non-positive, cannot apply log/exponential fit")
    return values[positive_mask]


def _extract_pairs(
    data: Sequence[Dict[str, Any]],
    x_key: str,
    y_key: str,
    log_x: bool = False,
    log_y: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    xs: List[float] = []
    ys: List[float] = []
    for row in data:
        x_val = row.get(x_key)
        y_val = row.get(y_key)
        if x_val is None or y_val is None:
            continue
        try:
            x_float = float(x_val)
            y_float = float(y_val)
        except Exception:
            continue
        if log_x and x_float <= 0:
            continue
        if log_y and y_float <= 0:
            continue
        xs.append(x_float)
        ys.append(y_float)
    if not xs:
        raise ValueError(f"No valid numeric rows for ({x_key}, {y_key})")
    x_arr = np.asarray(xs)
    y_arr = np.asarray(ys)
    return x_arr, y_arr


def _apply_axis_scale(ax: plt.Axes, log_x: bool, log_y: bool) -> None:
    if log_x:
        ax.set_xscale("log")
    if log_y:
        ax.set_yscale("log")


def _get_cmap(name: Optional[str], n: int) -> List[str]:
    cmap = plt.get_cmap(name or "viridis", max(n, 1))
    return [cmap(i) for i in range(max(n, 1))]


def plot_scatter(
    data: Sequence[Dict[str, Any]],
    config: ScatterConfig,
    output_dir: pathlib.Path,
    default_palette: str,
) -> Tuple[pathlib.Path, Dict[str, Tuple[np.ndarray, np.ndarray]]]:
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = _get_cmap(config.palette or default_palette, len(config.ys))
    data_sets: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    for idx, y_key in enumerate(config.ys):
        x_vals, y_vals = _extract_pairs(data, config.x, y_key, config.log_x, config.log_y)
        data_sets[y_key] = (x_vals, y_vals)
        order = np.argsort(x_vals)
        color = colors[idx]
        label = y_key
        if config.style == "line":
            ax.plot(x_vals[order], y_vals[order], color=color, label=label, linewidth=2.0)
        else:
            ax.scatter(x_vals, y_vals, color=color, label=label, marker=config.marker, alpha=config.alpha)
    _apply_axis_scale(ax, config.log_x, config.log_y)
    if config.grid:
        ax.grid(True, alpha=0.3, linestyle="--")
    ax.set_xlabel(config.xlabel or config.x)
    if config.ylabel:
        ax.set_ylabel(config.ylabel)
    elif len(config.ys) == 1:
        ax.set_ylabel(config.ys[0])
    else:
        ax.set_ylabel("value")
    if config.title:
        ax.set_title(config.title)
    if config.legend and len(config.ys) > 1:
        ax.legend()
    elif config.legend and len(config.ys) == 1 and config.ylabel is None:
        ax.legend()
    fig.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    outfile = pathlib.Path(config.outfile)
    if outfile.suffix.lower() != ".pdf":
        outfile = outfile.with_suffix(".pdf")
    out_path = output_dir / outfile.name
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return out_path, data_sets


@dataclass
class FitResult:
    name: str
    equation: str
    y_pred: np.ndarray
    r2: float
    model: str
    poly_degree: Optional[int] = None
    requested: str = ""


def _poly_fit(x: np.ndarray, y: np.ndarray, degree: int, label: str) -> FitResult:
    coeffs = np.polyfit(x, y, degree)
    coeffs_filtered = coeffs.copy()
    abs_coeffs = np.abs(coeffs_filtered)
    zero_mask = abs_coeffs < COEFF_ABS_THRESHOLD
    if coeffs_filtered.size > 1:
        max_non_const = float(np.max(abs_coeffs[:-1])) if abs_coeffs[:-1].size else 0.0
        if max_non_const > 0:
            rel_mask = abs_coeffs[:-1] < COEFF_REL_THRESHOLD * max_non_const
            zero_mask[:-1] = np.logical_or(zero_mask[:-1], rel_mask)
    coeffs_filtered[zero_mask] = 0.0
    poly = np.poly1d(coeffs_filtered)
    y_pred = poly(x)
    r2 = _r_squared(y, y_pred)

    abs_coeffs = np.abs(coeffs_filtered)
    max_coeff = float(abs_coeffs.max()) if abs_coeffs.size else 0.0
    tol = max(COEFF_ABS_THRESHOLD, 1e-6 * max(max_coeff, 1.0))
    effective_degree = 0
    terms: List[str] = []
    for power, coeff in enumerate(coeffs_filtered[::-1]):
        if abs(coeff) >= tol:
            effective_degree = max(effective_degree, power)
        terms.append((power, coeff))

    # Build readable equation keeping significant terms only
    pieces: List[str] = []
    for power, coeff in sorted(terms, reverse=True):
        if abs(coeff) < tol:
            continue
        if power == 0:
            pieces.append(f"{coeff:.6g}")
        elif power == 1:
            pieces.append(f"{coeff:+.6g}x")
        else:
            pieces.append(f"{coeff:+.6g}x^{power}")
    equation = "y = " + (" ".join(pieces) if pieces else "0")

    if effective_degree == 0:
        name = "constant"
    elif effective_degree == 1:
        name = "linear"
    else:
        name = f"poly{effective_degree}"

    return FitResult(
        name=name,
        equation=equation,
        y_pred=y_pred,
        r2=r2,
        model="poly",
        poly_degree=effective_degree,
        requested=label,
    )


def _exp_fit(x: np.ndarray, y: np.ndarray, base: float, label: str) -> Optional[FitResult]:
    if (y <= 0).any():
        return None
    ln_y = np.log(y)
    slope, intercept = np.polyfit(x, ln_y, 1)
    # Guard against overflowing the exponential when projecting back to linear space.
    max_log = np.log(np.finfo(np.float64).max)
    min_log = np.log(np.finfo(np.float64).tiny)
    log_pred = intercept + slope * x
    if np.any((log_pred < min_log) | (log_pred > max_log)):
        return None
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        y_pred = np.exp(log_pred)
    if not np.all(np.isfinite(y_pred)):
        return None
    a = math.exp(intercept)
    if base == math.e:
        b = slope
        equation = f"y = {a:.6g} * e^({b:.6g} x)"
        model_name = "exp"
    else:
        log_base = math.log(base)
        b = slope / log_base
        equation = f"y = {a:.6g} * {base:.3g}^({b:.6g} x)"
        model_name = f"exp{int(base)}"
    r2 = _r_squared(y, y_pred)
    return FitResult(
        name=model_name,
        equation=equation,
        y_pred=y_pred,
        r2=r2,
        model="exp",
        poly_degree=None,
        requested=label,
    )


def _r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot == 0:
        return 1.0
    return 1.0 - ss_res / ss_tot


def plot_fit(
    data: Sequence[Dict[str, Any]],
    config: FitConfig,
    output_dir: pathlib.Path,
    default_palette: str,
) -> Tuple[pathlib.Path, List[FitResult]]:
    x_vals, y_vals = _extract_pairs(data, config.x, config.y, config.log_x, config.log_y)
    order = np.argsort(x_vals)
    x_sorted = x_vals[order]
    y_sorted = y_vals[order]

    fit_results: List[FitResult] = []
    linear_result = _poly_fit(x_sorted, y_sorted, 1, "linear")

    for model in config.models:
        model_norm = model.lower()
        try:
            if model_norm == "linear":
                fit_results.append(linear_result)
            elif model_norm == "quadratic":
                fit_results.append(_poly_fit(x_sorted, y_sorted, 2, "quadratic"))
            elif model_norm == "cubic":
                fit_results.append(_poly_fit(x_sorted, y_sorted, 3, "cubic"))
            elif model_norm.startswith("exp"):
                if model_norm == "exp":
                    result = _exp_fit(x_sorted, y_sorted, math.e, "exp")
                else:
                    try:
                        base = float(model_norm[3:])
                    except Exception:
                        base = math.e
                    result = _exp_fit(x_sorted, y_sorted, base, model_norm)
                if result is not None:
                    fit_results.append(result)
        except Exception:
            continue

    if not fit_results:
        raise ValueError("No successful fits were produced for the selected models")

    denom = max(
        float(np.max(np.abs(linear_result.y_pred))),
        float(np.ptp(linear_result.y_pred)),
        1.0,
    )
    for res in fit_results:
        if res is linear_result:
            continue
        if res.poly_degree is not None and res.poly_degree > 1:
            diff = float(np.max(np.abs(res.y_pred - linear_result.y_pred)))
            if diff <= 1e-6 * denom:
                res.name = "linear"
                res.equation = linear_result.equation
                res.y_pred = linear_result.y_pred
                res.r2 = linear_result.r2
                res.model = linear_result.model
                res.poly_degree = linear_result.poly_degree

    if "linear" not in {res.name for res in fit_results}:
        fit_results.append(linear_result)

    all_results = list(fit_results)

    best_by_name: Dict[str, FitResult] = {}
    for result in fit_results:
        existing = best_by_name.get(result.name)
        if existing is None or result.r2 > existing.r2:
            best_by_name[result.name] = result

    def _fit_sort_key(result: FitResult) -> Tuple[float, float]:
        degree = result.poly_degree if result.poly_degree is not None else math.inf
        return (-result.r2, degree)

    fit_results = sorted(best_by_name.values(), key=_fit_sort_key)
    best = fit_results[0]

    fig, ax = plt.subplots(figsize=(10, 6))
    if config.scatter:
        ax.scatter(x_sorted, y_sorted, color=plt.get_cmap(config.palette or default_palette)(0.1), alpha=0.6, label="data")
    ax.plot(x_sorted, best.y_pred, color="red", linewidth=2.0, label=f"best: {best.name} (R^2={best.r2:.4f})")
    _apply_axis_scale(ax, config.log_x, config.log_y)
    ax.set_xlabel(config.xlabel or config.x)
    ax.set_ylabel(config.ylabel or config.y)
    if config.title:
        ax.set_title(config.title)
    ax.legend()
    ax.grid(True, alpha=0.3, linestyle="--")
    fig.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    outfile = pathlib.Path(config.outfile)
    if outfile.suffix.lower() != ".pdf":
        outfile = outfile.with_suffix(".pdf")
    out_path = output_dir / outfile.name
    fig.savefig(out_path, dpi=200)
    plt.close(fig)

    if config.summary_csv:
        summary_path = output_dir / config.summary_csv
    else:
        summary_path = output_dir / f"{pathlib.Path(config.outfile).stem}_fit_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["model", "r2", "equation"])
        for result in all_results:
            model_label = result.requested or result.name
            writer.writerow([model_label, f"{result.r2:.6f}", result.equation])

    return out_path, fit_results


def _compute_edges_from_width(min_val: float, max_val: float, width: float) -> np.ndarray:
    if width <= 0:
        raise ValueError("Bin width must be positive")
    if max_val <= min_val:
        max_val = min_val + width
    n = int(math.ceil((max_val - min_val) / width))
    return np.linspace(min_val, min_val + n * width, n + 1)


def _compute_edges_from_count(min_val: float, max_val: float, count: int) -> np.ndarray:
    if count <= 0:
        raise ValueError("Bin count must be positive")
    if max_val <= min_val:
        max_val = min_val + 1.0
    return np.linspace(min_val, max_val, count + 1)


def _prepare_edges(
    values: np.ndarray,
    *,
    count: Optional[int],
    width: Optional[float],
    vmin: Optional[float],
    vmax: Optional[float],
) -> np.ndarray:
    min_val = float(np.min(values) if vmin is None else vmin)
    max_val = float(np.max(values) if vmax is None else vmax)
    if width is not None:
        return _compute_edges_from_width(min_val, max_val, width)
    if count is not None:
        return _compute_edges_from_count(min_val, max_val, count)
    return _compute_edges_from_count(min_val, max_val, 20)


def plot_heatmap(
    data: Sequence[Dict[str, Any]],
    config: HeatmapConfig,
    output_dir: pathlib.Path,
    default_palette: str,
) -> pathlib.Path:
    records: List[Tuple[float, float, float]] = []
    for row in data:
        xv = row.get(config.x)
        yv = row.get(config.y)
        if xv is None or yv is None:
            continue
        try:
            xv_f = float(xv)
            yv_f = float(yv)
        except Exception:
            continue
        if config.log_x and xv_f <= 0:
            continue
        if config.log_y and yv_f <= 0:
            continue
        if config.value:
            val = row.get(config.value)
            if val is None:
                continue
            try:
                value_f = float(val)
            except Exception:
                continue
        else:
            value_f = 1.0
        records.append((xv_f, yv_f, value_f))

    if not records:
        raise ValueError("No data available for heatmap")

    x_vals = np.asarray([rec[0] for rec in records])
    y_vals = np.asarray([rec[1] for rec in records])
    value_array = np.asarray([rec[2] for rec in records])

    x_edges = _prepare_edges(
        x_vals,
        count=config.x_bins,
        width=config.x_bin_width,
        vmin=config.x_min,
        vmax=config.x_max,
    )
    y_edges = _prepare_edges(
        y_vals,
        count=config.y_bins,
        width=config.y_bin_width,
        vmin=config.y_min,
        vmax=config.y_max,
    )

    agg = config.agg.lower()
    if agg == "count":
        hist, _, _ = np.histogram2d(x_vals, y_vals, bins=[x_edges, y_edges])
    elif agg == "sum":
        hist, _, _ = np.histogram2d(x_vals, y_vals, bins=[x_edges, y_edges], weights=value_array)
    elif agg == "mean":
        sum_hist, _, _ = np.histogram2d(x_vals, y_vals, bins=[x_edges, y_edges], weights=value_array)
        count_hist, _, _ = np.histogram2d(x_vals, y_vals, bins=[x_edges, y_edges])
        with np.errstate(divide="ignore", invalid="ignore"):
            hist = np.divide(sum_hist, count_hist, out=np.zeros_like(sum_hist), where=count_hist != 0)
    elif agg == "max":
        hist = np.full((len(x_edges) - 1, len(y_edges) - 1), np.nan)
        for xv, yv, vv in records:
            bx = np.searchsorted(x_edges, xv, side="right") - 1
            by = np.searchsorted(y_edges, yv, side="right") - 1
            if bx < 0 or by < 0 or bx >= hist.shape[0] or by >= hist.shape[1]:
                continue
            current = hist[bx, by]
            hist[bx, by] = vv if math.isnan(current) else max(current, vv)
        hist = np.nan_to_num(hist, nan=0.0)
    elif agg == "min":
        hist = np.full((len(x_edges) - 1, len(y_edges) - 1), np.nan)
        for xv, yv, vv in records:
            bx = np.searchsorted(x_edges, xv, side="right") - 1
            by = np.searchsorted(y_edges, yv, side="right") - 1
            if bx < 0 or by < 0 or bx >= hist.shape[0] or by >= hist.shape[1]:
                continue
            current = hist[bx, by]
            hist[bx, by] = vv if math.isnan(current) else min(current, vv)
        hist = np.nan_to_num(hist, nan=0.0)
    else:
        raise ValueError(f"Unsupported aggregator '{config.agg}'")

    hist = hist.T
    fig, ax = plt.subplots(figsize=(10, 8))
    extent = [x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]]
    cmap = plt.get_cmap(config.palette or default_palette)
    if config.log_value:
        positive = hist[hist > 0]
        vmin = float(positive.min()) if positive.size else 1e-9
        vmax = float(hist.max()) if hist.size else 1.0
        if vmax <= vmin:
            vmax = vmin * 10
        norm = LogNorm(vmin=max(vmin, 1e-9), vmax=max(vmax, vmin * 10))
        img = ax.imshow(hist, extent=extent, origin="lower", aspect="auto", cmap=cmap, norm=norm)
    else:
        img = ax.imshow(hist, extent=extent, origin="lower", aspect="auto", cmap=cmap)
    ax.set_xlabel(config.xlabel or config.x)
    ax.set_ylabel(config.ylabel or config.y)
    if config.title:
        ax.set_title(config.title)
    _apply_axis_scale(ax, config.log_x, config.log_y)
    cbar = fig.colorbar(img, ax=ax)
    cbar.set_label(config.value if config.value else config.agg)

    if config.annotate:
        x_centers = (x_edges[:-1] + x_edges[1:]) / 2.0
        y_centers = (y_edges[:-1] + y_edges[1:]) / 2.0
        for yi, y_center in enumerate(y_centers):
            for xi, x_center in enumerate(x_centers):
                value = hist[yi, xi]
                ax.text(x_center, y_center, f"{value:.2f}", ha="center", va="center", color="white", fontsize=8)

    fig.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    outfile = pathlib.Path(config.outfile)
    if outfile.suffix.lower() != ".pdf":
        outfile = outfile.with_suffix(".pdf")
    out_path = output_dir / outfile.name
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return out_path


def load_analyze_config(raw_cfg: Dict[str, Any]) -> AnalyzeConfig:
    general = raw_cfg.get("general", {})
    palette = general.get("palette", "viridis")

    def _parse_bool(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off", ""}:
            return False
        raise ValueError(f"Invalid boolean value: {value!r}")

    scatter_cfgs: List[ScatterConfig] = []
    for idx, item in enumerate(raw_cfg.get("plots", []) or []):
        name = item.get("name", f"scatter_{idx+1}")
        outfile = item.get("outfile")
        x_key = item.get("x")
        ys_vals = item.get("ys") or []
        if outfile is None or x_key is None or not ys_vals:
            raise ValueError("Scatter plot entries require 'outfile', 'x', and at least one 'ys'")
        ys_list = list(ys_vals) if isinstance(ys_vals, (list, tuple)) else [ys_vals]
        fit_models_raw = item.get("fit_models")
        if fit_models_raw is None:
            fit_models_list = ScatterConfig.__dataclass_fields__["fit_models"].default_factory()  # type: ignore[attr-defined]
        elif isinstance(fit_models_raw, (list, tuple)):
            fit_models_list = [str(m) for m in fit_models_raw]
        else:
            fit_models_list = [str(fit_models_raw)]

        scatter_cfgs.append(
            ScatterConfig(
                name=name,
                outfile=outfile,
                x=x_key,
                ys=ys_list,
                style=item.get("style", "scatter"),
                title=item.get("title"),
                xlabel=item.get("xlabel"),
                ylabel=item.get("ylabel"),
                palette=item.get("palette"),
                legend=_parse_bool(item.get("legend", True)),
                log_x=_parse_bool(item.get("log_x", False)),
                log_y=_parse_bool(item.get("log_y", False)),
                alpha=float(item.get("alpha", 0.8)),
                marker=item.get("marker", "o"),
                grid=_parse_bool(item.get("grid", True)),
                fit=_parse_bool(item.get("fit", False)),
                fit_models=fit_models_list,
                fit_outfile=item.get("fit_outfile"),
                fit_title=item.get("fit_title"),
                fit_summary_csv=item.get("fit_summary_csv"),
            )
        )

    heatmap_cfgs: List[HeatmapConfig] = []
    for idx, item in enumerate(raw_cfg.get("heatmaps", []) or []):
        name = item.get("name", f"heatmap_{idx+1}")
        outfile = item.get("outfile")
        x_key = item.get("x")
        y_key = item.get("y")
        if outfile is None or x_key is None or y_key is None:
            raise ValueError("Heatmap entries require 'outfile', 'x', and 'y'")
        heatmap_cfgs.append(
            HeatmapConfig(
                name=name,
                outfile=outfile,
                x=x_key,
                y=y_key,
                value=item.get("value"),
                agg=item.get("agg", "mean"),
                title=item.get("title"),
                xlabel=item.get("xlabel"),
                ylabel=item.get("ylabel"),
                palette=item.get("palette"),
                x_bins=item.get("x_bins"),
                y_bins=item.get("y_bins"),
                x_bin_width=item.get("x_bin_width"),
                y_bin_width=item.get("y_bin_width"),
                x_min=item.get("x_min"),
                x_max=item.get("x_max"),
                y_min=item.get("y_min"),
                y_max=item.get("y_max"),
                log_x=_parse_bool(item.get("log_x", False)),
                log_y=_parse_bool(item.get("log_y", False)),
                log_value=_parse_bool(item.get("log_value", False)),
                annotate=_parse_bool(item.get("annotate", False)),
            )
        )

    return AnalyzeConfig(palette=palette, scatter_plots=scatter_cfgs, heatmaps=heatmap_cfgs)


def run_analysis(
    data: Sequence[Dict[str, Any]],
    plots_dir: pathlib.Path,
    config: AnalyzeConfig,
) -> List[pathlib.Path]:
    results: List[pathlib.Path] = []
    for scatter_cfg in config.scatter_plots:
        out_path, data_sets = plot_scatter(data, scatter_cfg, plots_dir, config.palette)
        print(f"[plot] {scatter_cfg.name} -> {out_path}")
        results.append(out_path)
        if scatter_cfg.fit:
            if len(scatter_cfg.ys) != 1:
                raise ValueError(f"Scatter plot '{scatter_cfg.name}' enables fit but defines multiple ys")
            y_key = scatter_cfg.ys[0]
            fit_cfg = FitConfig(
                name=f"{scatter_cfg.name}_fit",
                outfile=scatter_cfg.fit_outfile or f"{pathlib.Path(scatter_cfg.outfile).stem}_fit.pdf",
                x=scatter_cfg.x,
                y=y_key,
                models=scatter_cfg.fit_models,
                title=scatter_cfg.fit_title or scatter_cfg.title,
                xlabel=scatter_cfg.xlabel or scatter_cfg.x,
                ylabel=scatter_cfg.ylabel or y_key,
                palette=scatter_cfg.palette,
                scatter=True,
                log_x=scatter_cfg.log_x,
                log_y=scatter_cfg.log_y,
                summary_csv=scatter_cfg.fit_summary_csv,
            )
            out_fit, fit_results = plot_fit(data, fit_cfg, plots_dir, config.palette)
            best = fit_results[0]
            print(f"[fit] {fit_cfg.name}: best={best.name} R^2={best.r2:.4f} -> {out_fit}")
            results.append(out_fit)
    for heatmap_cfg in config.heatmaps:
        out_path = plot_heatmap(data, heatmap_cfg, plots_dir, config.palette)
        print(f"[heatmap] {heatmap_cfg.name} -> {out_path}")
        results.append(out_path)
    return results


def _collect_required_columns(config: AnalyzeConfig) -> List[str]:
    required: set[str] = set()
    for scatter_cfg in config.scatter_plots:
        required.add(scatter_cfg.x)
        required.update(scatter_cfg.ys)
    for heatmap_cfg in config.heatmaps:
        required.add(heatmap_cfg.x)
        required.add(heatmap_cfg.y)
        if heatmap_cfg.value:
            required.add(heatmap_cfg.value)
    required.discard("file")
    return sorted(required)


def validate_required_columns(config: AnalyzeConfig, available_columns: Sequence[str]) -> None:
    available = set(available_columns)
    required = _collect_required_columns(config)
    missing = [col for col in required if col not in available]
    if missing:
        raise ValueError(
            "Missing columns in metrics CSV: " + ", ".join(sorted(missing))
        )


__all__ = [
    "AnalyzeConfig",
    "ScatterConfig",
    "FitConfig",
    "HeatmapConfig",
    "load_metrics_table",
    "load_analyze_config",
    "run_analysis",
    "validate_required_columns",
]

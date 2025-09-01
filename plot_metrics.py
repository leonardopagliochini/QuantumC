#!/usr/bin/env python3
"""
tools/plot_metrics.py

Legge results/metrics.csv e genera:
1) CC vs Quantum (x = metrica quantistica, y = CC medio) — media su Ir
   -> plots/cc_vs_quantum/<metric>.pdf
2) Ir vs Quantum (x = metrica quantistica, y = Ir medio) — media su CC
   -> plots/ir_vs_quantum/<metric>.pdf
3) Contour (x = CC, y = Ir, colore = metrica quantistica media)
   -> plots/contours/<metric>.pdf
"""

import argparse
import pathlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

QUANTUM_METRICS = [
    "num_qubits", "num_gates",
    "num_cx", "num_measure", "num_u1", "num_u2", "num_u3"
]
REQUIRED_COLS = ["file", "cyclomatic", "ir_instructions"] + QUANTUM_METRICS


def ensure_dirs(base: pathlib.Path):
    (base / "cc_vs_quantum").mkdir(parents=True, exist_ok=True)
    (base / "ir_vs_quantum").mkdir(parents=True, exist_ok=True)
    (base / "contours").mkdir(parents=True, exist_ok=True)


def read_data(csv_path: pathlib.Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    for c in ["cyclomatic", "ir_instructions"] + QUANTUM_METRICS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # rimuovi le righe senza CC
    df = df.dropna(subset=["cyclomatic"])
    return df


def quantile_bins(x: pd.Series, nbins: int):
    """Ritorna (centri, labels) usando quantili; fallback a bins lineari se serve."""
    vals = x.dropna().values
    if len(vals) < 2:
        # niente da bin-are
        return np.array(vals), pd.Series(pd.Categorical([pd.Interval(min(vals), max(vals), closed="both")] * len(x)))
    qs = np.linspace(0, 1, nbins + 1)
    edges = np.unique(np.quantile(vals, qs))
    if len(edges) <= 2:
        edges = np.linspace(x.min(), x.max(), min(nbins, max(2, x.nunique())) + 1)
    labels = pd.cut(x, bins=edges, include_lowest=True)
    centers = np.array([(iv.left + iv.right) / 2.0 for iv in labels.cat.categories], dtype=float)
    return centers, labels


def line_plot_x_quantum_y_stat(df: pd.DataFrame, quantum_col: str, y_col: str,
                               out_path: pathlib.Path, nbins: int,
                               y_label: str, title: str):
    centers, bins = quantile_bins(df[quantum_col], nbins)
    grp = df.groupby(bins, observed=True)[y_col].mean()
    # drop dei bin vuoti:
    mask = ~grp.isna()
    x = centers[:len(grp)][mask]
    y = grp.values[mask]

    if len(x) == 0:
        return

    fig = plt.figure()
    plt.plot(x, y, marker="o")
    plt.xlabel(quantum_col)
    plt.ylabel(y_label)
    plt.title(title)
    plt.tight_layout()
    fig.savefig(out_path, format="pdf")
    plt.close(fig)


def contour_plot(df: pd.DataFrame, quantum_col: str, out_path: pathlib.Path,
                 bins_cc: int, bins_ir: int):
    d = df.dropna(subset=["cyclomatic", "ir_instructions"])
    if d.empty:
        return

    # Edges fissi (lineari) per costruire una griglia MxN completa
    cc_min, cc_max = d["cyclomatic"].min(), d["cyclomatic"].max()
    ir_min, ir_max = d["ir_instructions"].min(), d["ir_instructions"].max()
    if not np.isfinite([cc_min, cc_max, ir_min, ir_max]).all() or cc_min == cc_max or ir_min == ir_max:
        return

    cc_edges = np.linspace(cc_min, cc_max, bins_cc + 1)
    ir_edges = np.linspace(ir_min, ir_max, bins_ir + 1)

    cc_cats = pd.IntervalIndex.from_breaks(cc_edges, closed="left")
    ir_cats = pd.IntervalIndex.from_breaks(ir_edges, closed="left")

    cc_bin = pd.cut(d["cyclomatic"], bins=cc_edges, include_lowest=True, right=False)
    ir_bin = pd.cut(d["ir_instructions"], bins=ir_edges, include_lowest=True, right=False)

    d2 = d.copy()
    d2["cc_bin"] = pd.Categorical(cc_bin, categories=cc_cats)
    d2["ir_bin"] = pd.Categorical(ir_bin, categories=ir_cats)

    pivot = d2.pivot_table(index="cc_bin", columns="ir_bin", values=quantum_col,
                           aggfunc="mean", dropna=False)
    pivot = pivot.reindex(index=cc_cats, columns=ir_cats)

    Z = pivot.values  # shape (bins_cc, bins_ir)
    if Z.size == 0:
        return

    # Griglia edges 2D per pcolormesh (C: MxN, edges: (M+1)x(N+1))
    X, Y = np.meshgrid(cc_edges, ir_edges, indexing="ij")

    fig = plt.figure()
    pcm = plt.pcolormesh(X, Y, Z, shading="auto")
    cbar = plt.colorbar(pcm)
    cbar.set_label(quantum_col)
    plt.xlabel("cyclomatic")
    plt.ylabel("ir_instructions")
    plt.title(f"{quantum_col} (media per bin)")
    plt.tight_layout()
    fig.savefig(out_path, format="pdf")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=str, default="results/metrics.csv")
    ap.add_argument("--out", type=str, default="plots")
    ap.add_argument("--bins1d", type=int, default=25)
    ap.add_argument("--bins_cc", type=int, default=20)
    ap.add_argument("--bins_ir", type=int, default=20)
    args = ap.parse_args()

    csv_path = pathlib.Path(args.csv)
    out_dir = pathlib.Path(args.out)
    ensure_dirs(out_dir)

    df = read_data(csv_path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise SystemExit(f"Mancano colonne nel CSV: {missing}")

    # 1) CC vs Quantum (media marginale su Ir)
    cc_dir = out_dir / "cc_vs_quantum"
    for qm in QUANTUM_METRICS:
        line_plot_x_quantum_y_stat(
            df=df,
            quantum_col=qm,
            y_col="cyclomatic",
            out_path=cc_dir / f"{qm}.pdf",
            nbins=args.bins1d,
            y_label="cyclomatic (media)",
            title=f"cyclomatic vs {qm}  (media su Ir)"
        )

    # 2) Ir vs Quantum (media su CC)
    ir_dir = out_dir / "ir_vs_quantum"
    df_ir = df.dropna(subset=["ir_instructions"])
    if not df_ir.empty:
        for qm in QUANTUM_METRICS:
            line_plot_x_quantum_y_stat(
                df=df_ir,
                quantum_col=qm,
                y_col="ir_instructions",
                out_path=ir_dir / f"{qm}.pdf",
                nbins=args.bins1d,
                y_label="ir_instructions (media)",
                title=f"ir_instructions vs {qm}  (media su cyclomatic)"
            )

    # 3) Contours (CC, Ir) -> colore = qm medio
    cont_dir = out_dir / "contours"
    for qm in QUANTUM_METRICS:
        contour_plot(df, qm, cont_dir / f"{qm}.pdf",
                     bins_cc=args.bins_cc, bins_ir=args.bins_ir)

    # README
    (out_dir / "README.txt").write_text(
        "Contenuto:\n"
        " - cc_vs_quantum/<metric>.pdf : x=metrica Q, y=cyclomatic medio (media su Ir)\n"
        " - ir_vs_quantum/<metric>.pdf : x=metrica Q, y=Ir medio (media su CC)\n"
        " - contours/<metric>.pdf      : x=cyclomatic, y=Ir, colore=metrica Q media\n"
        f"\nGenerati da: {csv_path}\n"
    )
    print(f"[✓] Output salvato in: {out_dir.resolve()}")


if __name__ == "__main__":
    main()

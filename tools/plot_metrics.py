#!/usr/bin/env python3
"""
tools/plot_metrics.py

Legge results/metrics.csv e genera:
1) CC vs Quantum (x = cyclomatic, y = metrica quantistica media)
   -> plots/cc_vs_quantum/<metric>.pdf
2) Ir vs Quantum (x = ir_instructions, y = metrica quantistica media)
   -> plots/ir_vs_quantum/<metric>.pdf
3) Contour (x = cyclomatic, y = ir_instructions, colore = metrica quantistica media)
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


# --- util quantile bins
import numpy as np
import pandas as pd

def quantile_bins(x, nbins: int):
    """
    Restituisce (centers, categories) per binning per quantili.
    Robusto a dati costanti o quasi-costanti:
    - rimuove NaN
    - de-duplica gli edge
    - fallback a un singolo bin se serve
    """
    s = pd.Series(x).dropna()
    if s.empty:
        return np.array([]), pd.IntervalIndex([])

    q = np.linspace(0.0, 1.0, nbins + 1)
    edges = np.quantile(s.to_numpy(), q)
    edges = np.unique(edges)

    if edges.size < 2:
        v = float(s.iloc[0])
        eps = 0.5 if v == 0 else abs(v) * 0.01
        edges = np.array([v - eps, v + eps])

    labels = pd.cut(s, bins=edges, include_lowest=True, duplicates="drop")
    cats = labels.cat.categories

    if len(cats) == 0:
        v = float(s.iloc[0])
        eps = 0.5 if v == 0 else abs(v) * 0.01
        cats = pd.IntervalIndex.from_tuples([(v - eps, v + eps)])

    centers = np.array([iv.mid for iv in cats], dtype=float)
    return centers, cats



def line_plot_x_stat_y_quantum(df: pd.DataFrame, x_col: str, quantum_col: str,
                               out_path: pathlib.Path, nbins: int,
                               x_label: str, title: str):
    """
    Binna lungo x_col e plottiamo la media di quantum_col per bin.
    """
    centers, bins = quantile_bins(df[x_col], nbins)
    if len(centers) == 0:
        return

    labels = pd.cut(df[x_col], bins=bins, include_lowest=True, duplicates="drop")
    grp = df.groupby(labels, observed=False)[quantum_col].mean()

    cats = grp.index.categories
    x_all = np.array([(iv.left + iv.right) / 2.0 for iv in cats], dtype=float)
    y_all = grp.reindex(cats).values

    valid = ~np.isnan(y_all)
    x = x_all[valid]
    y = y_all[valid]

    if len(x) == 0:
        return

    fig = plt.figure()
    plt.plot(x, y, marker="o")
    plt.xlabel(x_label)
    plt.ylabel(f"{quantum_col} (media)")
    plt.title(title)
    plt.tight_layout()
    fig.savefig(out_path, format="pdf")
    plt.close(fig)



def contour_plot(df: pd.DataFrame, quantum_col: str, out_path: pathlib.Path,
                 bins_cc: int, bins_ir: int):
    """
    Heatmap media per bin:
    - Asse X (cyclomatic): bin per OGNI intero da min a max (1,2,3,...)
    - Asse Y (ir_instructions): bin lineari (bins_ir)
    """
    d = df.dropna(subset=["cyclomatic", "ir_instructions"])
    if d.empty:
        return

    # --- Binning X: tutti gli interi tra min e max
    cc_min_val = int(np.floor(d["cyclomatic"].min()))
    cc_max_val = int(np.ceil(d["cyclomatic"].max()))
    if cc_min_val == cc_max_val:
        # se c'è un solo valore, allarghiamo di 1 per avere una cella visibile
        cc_min_val -= 1
        cc_max_val += 1
    # edges centrati sugli interi: [n-0.5, n+0.5, ...]
    cc_edges = np.arange(cc_min_val - 0.5, cc_max_val + 1.5, 1.0)
    cc_cats = pd.IntervalIndex.from_breaks(cc_edges, closed="left")

    # --- Binning Y: lineare come prima
    ir_min, ir_max = d["ir_instructions"].min(), d["ir_instructions"].max()
    if not np.isfinite([ir_min, ir_max]).all() or ir_min == ir_max:
        return
    ir_edges = np.linspace(ir_min, ir_max, bins_ir + 1)
    ir_cats = pd.IntervalIndex.from_breaks(ir_edges, closed="left")

    # Taglio nei bin
    cc_bin = pd.cut(d["cyclomatic"], bins=cc_edges, include_lowest=True, right=False)
    ir_bin = pd.cut(d["ir_instructions"], bins=ir_edges, include_lowest=True, right=False)

    d2 = d.copy()
    d2["cc_bin"] = pd.Categorical(cc_bin, categories=cc_cats)
    d2["ir_bin"] = pd.Categorical(ir_bin, categories=ir_cats)

    pivot = d2.pivot_table(index="cc_bin", columns="ir_bin", values=quantum_col,
                           aggfunc="mean", dropna=False)
    pivot = pivot.reindex(index=cc_cats, columns=ir_cats)

    Z = pivot.values  # shape (n_cc_bins, bins_ir)
    if Z.size == 0:
        return

    # Griglia edges 2D per pcolormesh (edges: (M+1)x(N+1))
    X, Y = np.meshgrid(cc_edges, ir_edges, indexing="ij")

    fig = plt.figure()
    pcm = plt.pcolormesh(X, Y, Z, shading="auto")
    cbar = plt.colorbar(pcm)
    cbar.set_label(quantum_col)
    plt.xlabel("cyclomatic")
    plt.ylabel("ir_instructions")
    plt.title(f"{quantum_col} (media per bin)")

    # --- Ticks X: tutti gli interi (1,2,3,...) dal min al max
    # centro di ciascun bin: n esatto
    xticks = np.arange(cc_min_val, cc_max_val + 1, 1, dtype=int)
    plt.xticks(xticks, [str(n) for n in xticks], rotation=0)

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

    # 1) CC vs Quantum: x=cyclomatic, y=QM (media)
    cc_dir = out_dir / "cc_vs_quantum"
    for qm in QUANTUM_METRICS:
        line_plot_x_stat_y_quantum(
            df=df,
            x_col="cyclomatic",
            quantum_col=qm,
            out_path=cc_dir / f"{qm}.pdf",
            nbins=args.bins1d,
            x_label="cyclomatic",
            title=f"{qm} vs cyclomatic"
        )

    # 2) Ir vs Quantum: x=ir_instructions, y=QM (media)
    ir_dir = out_dir / "ir_vs_quantum"
    df_ir = df.dropna(subset=["ir_instructions"])
    if not df_ir.empty:
        for qm in QUANTUM_METRICS:
            line_plot_x_stat_y_quantum(
                df=df_ir,
                x_col="ir_instructions",
                quantum_col=qm,
                out_path=ir_dir / f"{qm}.pdf",
                nbins=args.bins1d,
                x_label="ir_instructions",
                title=f"{qm} vs ir_instructions"
            )

    # 3) Contours (CC, Ir) -> colore = qm medio
    cont_dir = out_dir / "contours"
    for qm in QUANTUM_METRICS:
        contour_plot(df, qm, cont_dir / f"{qm}.pdf",
                     bins_cc=args.bins_cc, bins_ir=args.bins_ir)

    # README
    (out_dir / "README.txt").write_text(
        "Contenuto:\n"
        " - cc_vs_quantum/<metric>.pdf : x=cyclomatic, y=metrica Q media\n"
        " - ir_vs_quantum/<metric>.pdf : x=ir_instructions, y=metrica Q media\n"
        " - contours/<metric>.pdf      : x=cyclomatic, y=ir_instructions, colore=metrica Q media\n"
        f"\nGenerati da: {csv_path}\n"
    )
    print(f"[✓] Output salvato in: {out_dir.resolve()}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
qasm_metrics.py — Estrae metriche da file OpenQASM e le salva in CSV.

Metriche:
- num_qubits
- num_gates (esclude header/declare/comment/barrier)
- num_cx, num_measure, num_u1, num_u2, num_u3
- depth (stima greedy a layer: earliest-start, barrier forza break)

Uso:
  python qasm_metrics.py --qasm-dir path/to/qasm_folder --out results/metrics.csv
"""

import argparse
import csv
import pathlib
import re
from typing import Dict, List, Optional

# ------------ Regex utili ------------
_QREG_RE     = re.compile(r"qreg\s+\w+\[(\d+)\];")
_CX_RE       = re.compile(r"^\s*cx\s", re.MULTILINE)
_MEASURE_RE  = re.compile(r"^\s*measure\s", re.MULTILINE)
_U1_RE       = re.compile(r"^\s*u1\(", re.MULTILINE)
_U2_RE       = re.compile(r"^\s*u2\(", re.MULTILINE)
_U3_RE       = re.compile(r"^\s*u3\(", re.MULTILINE)

# token qubit generico (q[0], qr[12], nome qualsiasi + indice tra [])
_QBIT_TOK_RE = re.compile(r"([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]")

def _is_comment_or_header(s: str) -> bool:
    return (
        (not s)
        or s.startswith("//")
        or s.startswith("OPENQASM")
        or s.startswith("include")
        or s.startswith("qreg")
        or s.startswith("creg")
    )

# ------------ Depth: scheduler greedy earliest-start ------------
def compute_qasm_depth(qasm_text: str) -> int:
    """
    Greedy earliest-start layering:
      - layer(op) = 1 + max(last_layer[q]) per tutti i qubit coinvolti (default 0).
      - 'barrier': forza un avanzamento di layer sui qubit elencati
        (o globale se senza lista).
      - 'measure' conta come gate sul relativo qubit.
    Ritorna 0 se non ci sono gate.
    """
    last_layer: Dict[str, int] = {}  # chiave "qreg[index]"
    depth = 0

    for raw in qasm_text.splitlines():
        s = raw.strip()
        if _is_comment_or_header(s):
            continue

        # barrier (può essere "barrier;" o "barrier q[0], q[1];")
        if s.startswith("barrier"):
            qubits = [f"{n}[{i}]" for n, i in _QBIT_TOK_RE.findall(s)]
            if not qubits:
                # barrier globale: spinge in avanti tutti i qubit già visti
                if last_layer:
                    bump = max(last_layer.values()) + 1
                    for q in list(last_layer.keys()):
                        last_layer[q] = bump
                    depth = max(depth, bump)
            else:
                cur_max = 0
                for q in qubits:
                    cur_max = max(cur_max, last_layer.get(q, 0))
                new_layer = cur_max + 1
                for q in qubits:
                    last_layer[q] = new_layer
                depth = max(depth, new_layer)
            continue

        # measure q[i] -> c[j];
        if s.startswith("measure"):
            mqs = _QBIT_TOK_RE.findall(s)
            if not mqs:
                continue
            qubits = [f"{n}[{i}]" for n, i in mqs]
            layer = 1 + max((last_layer.get(q, 0) for q in qubits), default=0)
            for q in qubits:
                last_layer[q] = layer
            depth = max(depth, layer)
            continue

        # Gate generico (u1/u2/u3, cx, ccx, ecc.) — qualsiasi riga con token di qubit
        mqs = _QBIT_TOK_RE.findall(s)
        if not mqs:
            continue
        qubits = [f"{n}[{i}]" for n, i in mqs]
        layer = 1 + max((last_layer.get(q, 0) for q in qubits), default=0)
        for q in qubits:
            last_layer[q] = layer
        depth = max(depth, layer)

    return depth

def count_qasm_metrics(qasm_path: pathlib.Path) -> Dict[str, Optional[int]]:
    text = qasm_path.read_text(encoding="utf-8", errors="ignore")

    # qubits = somma delle dimensioni delle qreg dichiarate
    qubits = sum(int(m.group(1)) for m in _QREG_RE.finditer(text))

    num_cx      = len(_CX_RE.findall(text))
    num_measure = len(_MEASURE_RE.findall(text))
    num_u1      = len(_U1_RE.findall(text))
    num_u2      = len(_U2_RE.findall(text))
    num_u3      = len(_U3_RE.findall(text))

    # num_gates: esclude header/decl/comment/barrier
    total = 0
    for line in text.splitlines():
        s = line.strip()
        if _is_comment_or_header(s):
            continue
        if s.startswith("barrier"):
            continue
        if s:  # riga non vuota -> conta come gate
            total += 1

    depth = compute_qasm_depth(text)

    return dict(
        num_qubits=qubits,
        num_gates=total,
        num_cx=num_cx,
        num_measure=num_measure,
        num_u1=num_u1,
        num_u2=num_u2,
        num_u3=num_u3,
        depth=depth,
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qasm-dir", type=str, required=True,
                    help="Cartella contenente i file .qasm")
    ap.add_argument("--out", type=str, required=True,
                    help="Percorso del CSV in output")
    args = ap.parse_args()

    qasm_dir = pathlib.Path(args.qasm_dir)
    if not qasm_dir.is_dir():
        raise SystemExit(f"Errore: {qasm_dir} non è una cartella valida.")

    qasm_files: List[pathlib.Path] = sorted(qasm_dir.glob("*.qasm"))

    rows: List[Dict[str, Optional[int]]] = []
    for qf in qasm_files:
        print(f"[INFO] Processing: {qf}")
        try:
            m = count_qasm_metrics(qf)
            rows.append(dict(file=qf.name, **m))
        except Exception as e:
            # Riga con metriche vuote in caso di errore (facile da filtrare dopo)
            rows.append(dict(
                file=qf.name, num_qubits=None, num_gates=None, num_cx=None,
                num_measure=None, num_u1=None, num_u2=None, num_u3=None, depth=None
            ))

    out_csv = pathlib.Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "file",
            "num_qubits", "num_gates",
            "num_cx", "num_measure", "num_u1", "num_u2", "num_u3",
            "depth",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"[DONE] Written: {out_csv} — {len(rows)} file elaborati")

if __name__ == "__main__":
    main()

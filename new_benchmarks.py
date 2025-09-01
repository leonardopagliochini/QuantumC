#!/usr/bin/env python3
"""
bench_all.py — End-to-end:
- Cyclomatic Complexity (Lizard)
- Instruction Count Ir (Valgrind/Callgrind)
- Circuit metrics from QASM (num_qubits, total_gates, cx, measure, u1,u2,u3)
- Output: tools/results/metrics.csv  (results è allo stesso livello di questo file)

Usage:
  python tools/bench_all.py --corpus corpus_c --bits 16
"""

import argparse
import csv
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List

# === Path setup ===
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent          # <— cartella di questo file
ROOT       = SCRIPT_DIR.parents[0]                            # root del repo (una su)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pipeline  # <-- il file che ci hai fornito

# === results allo stesso livello di questo file ===
RESULTS_DIR = SCRIPT_DIR / "results"
QASM_DIR    = RESULTS_DIR / "qasm"
BIN_DIR     = RESULTS_DIR / "bin"
RESULTS_DIR.mkdir(exist_ok=True)
QASM_DIR.mkdir(parents=True, exist_ok=True)
BIN_DIR.mkdir(parents=True, exist_ok=True)

# ---------- C metrics ----------

def cyclomatic_lizard(c_path: pathlib.Path) -> float:
    """
    Ritorna CC = somma delle CCN delle funzioni nel file.
    - Invoca lizard come modulo Python (evita problemi di PATH).
    - Forza -l c.
    - Se Lizard fallisce o ritorna exit!=0, usa un fallback euristico.
    """
    import shlex

    def run_lizard(args):
        return subprocess.run(
            [sys.executable, "-m", "lizard", *args],
            capture_output=True, text=True
        )

    # 1) Tentativo principale: -l c -j
    res = run_lizard(["-l", "c", "-j", str(c_path)])
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            funcs = data[0].get("functions", [])
            return float(sum(f.get("cyclomatic_complexity", 1) for f in funcs)) if funcs else 1.0
        except Exception:
            pass  # cadrà nel retry/fallback

    # 2) Retry senza -l c (alcuni setup riconoscono .c automaticamente)
    res2 = run_lizard(["-j", str(c_path)])
    if res2.returncode == 0:
        try:
            data = json.loads(res2.stdout)
            funcs = data[0].get("functions", [])
            return float(sum(f.get("cyclomatic_complexity", 1) for f in funcs)) if funcs else 1.0
        except Exception:
            pass

    # 3) Fallback euristico (semplice ma stabile)
    text = c_path.read_text(encoding="utf-8", errors="ignore")
    # conta decision points classici
    tokens = [
        r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b",
        r"&&", r"\|\|", r"\?",
    ]
    cc = 1
    for pat in tokens:
        cc += len(re.findall(pat, text))
    return float(cc)


def compile_c_for_valgrind(c_path: pathlib.Path, out_bin: pathlib.Path, cc="gcc"):
    subprocess.run([cc, "-O0", "-g", str(c_path), "-o", str(out_bin)], check=True)

def callgrind_ir(bin_path: pathlib.Path, run_cmd: str | None = None) -> int | None:
    """
    Esegue Valgrind/Callgrind e restituisce Ir.
    - Copia il binario in /tmp (evita mount 'noexec')
    - NON fallisce su exit code != 0 del programmino
    - Prima prova con callgrind_annotate; se non trova Ir, effettua parsing diretto del file callgrind.out:
        * legge "events:" -> individua indice di "Ir"
        * legge "summary:" -> estrae il valore in quella posizione
    """
    import shlex

    if shutil.which("valgrind") is None:
        print("[!] Valgrind non trovato → Ir = NA")
        return None

    # callgrind_annotate è utile ma non indispensabile (il fallback legge il raw file)
    has_annot = shutil.which("callgrind_annotate") is not None

    # assicura eseguibile
    try:
        bin_path.chmod(bin_path.stat().st_mode | 0o111)
    except Exception:
        pass

    with tempfile.TemporaryDirectory() as td:
        tmp_bin = pathlib.Path(td) / bin_path.name
        shutil.copy2(bin_path, tmp_bin)
        tmp_bin.chmod(tmp_bin.stat().st_mode | 0o111)
        cg_out = pathlib.Path(td) / "callgrind.out"

        # Forza locale "C" per output standardizzato
        env = os.environ.copy()
        env["LANG"] = "C"
        env["LC_ALL"] = "C"

        vg_cmd = [
            "valgrind",
            "--tool=callgrind",
            f"--callgrind-out-file={str(cg_out)}",
            str(tmp_bin)
        ]

        # Nota: non richiediamo returncode==0 (il tuo try.c ritorna 27)
        res = subprocess.run(
            vg_cmd,
            input=run_cmd if run_cmd is not None else None,
            text=True,
            capture_output=True,
            env=env
        )

        if not cg_out.exists():
            print(f"[!] Callgrind non ha prodotto output.\nSTDERR:\n{res.stderr}\nSTDOUT:\n{res.stdout}")
            return None

        # 1) Tentativo: callgrind_annotate
        if has_annot:
            ann = subprocess.run(
                ["callgrind_annotate", str(cg_out)],
                capture_output=True, text=True, env=env
            )
            if ann.returncode == 0:
                m = re.search(r"\bIr\s*:\s*([\d,\.]+)", ann.stdout)
                if m:
                    return int(m.group(1).replace(",", "").replace(".", ""))

        # 2) Fallback robusto: parsing diretto del file callgrind.out
        try:
            raw = cg_out.read_text()
            # Trova eventi (ordine delle colonne)
            # es: "events: Ir"   oppure "events: Ir Dr Dw"
            ev_m = re.search(r"^events:\s*(.+)$", raw, re.MULTILINE)
            if not ev_m:
                print("[!] 'events:' non trovato in callgrind.out → Ir = NA")
                return None
            events = ev_m.group(1).strip().split()
            # indice di Ir
            try:
                ir_idx = events.index("Ir")
            except ValueError:
                print("[!] 'Ir' non presente nella lista eventi → Ir = NA")
                return None

            # Trova summary:
            # es: "summary: 1234567"    (se un solo evento)
            #     "summary: 1234567 98765 4321" (se più eventi; Ir è alla posizione ir_idx)
            sum_m = re.search(r"^summary:\s*([^\n]+)$", raw, re.MULTILINE)
            if not sum_m:
                print("[!] 'summary:' non trovato in callgrind.out → Ir = NA")
                return None
            nums = re.split(r"\s+", sum_m.group(1).strip())
            # ripulisci separatori tipo , . _
            def clean_num(s: str) -> str:
                return re.sub(r"[,_\.]", "", s)
            if ir_idx < len(nums):
                val = clean_num(nums[ir_idx])
                return int(val)
            else:
                # se per qualche motivo summary ha un solo numero e ir_idx=0, prova quello
                if len(nums) == 1 and ir_idx == 0:
                    return int(clean_num(nums[0]))
                print("[!] Indice Ir fuori range nel summary → Ir = NA")
                return None
        except Exception as e:
            print(f"[!] Fallback parsing callgrind.out fallito: {e} → Ir = NA")
            return None

# ---------- QASM parsing ----------

_QREG_RE     = re.compile(r"qreg\s+\w+\[(\d+)\];")
_CX_RE       = re.compile(r"^\s*cx\s", re.MULTILINE)
_MEASURE_RE  = re.compile(r"^\s*measure\s", re.MULTILINE)
_U1_RE       = re.compile(r"^\s*u1\(", re.MULTILINE)
_U2_RE       = re.compile(r"^\s*u2\(", re.MULTILINE)
_U3_RE       = re.compile(r"^\s*u3\(", re.MULTILINE)

def count_qasm_metrics(qasm_path: pathlib.Path) -> Dict[str, int]:
    """
    Conta le metriche richieste direttamente dal testo QASM.
    NB: funziona quando la pipeline esporta QASM 'standard' (export_qasm, non Clifford+T).
    """
    text = qasm_path.read_text()

    # num_qubits = somma di tutte le qreg
    qubits = sum(int(m.group(1)) for m in _QREG_RE.finditer(text))

    # gate counts specifici
    num_cx      = len(_CX_RE.findall(text))
    num_measure = len(_MEASURE_RE.findall(text))
    num_u1      = len(_U1_RE.findall(text))
    num_u2      = len(_U2_RE.findall(text))
    num_u3      = len(_U3_RE.findall(text))

    # total_gates: conta tutte le istruzioni QASM (escludi direttive e dichiarazioni)
    total = 0
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        if s.startswith(("OPENQASM", "include", "qreg", "creg", "barrier")):
            continue
        total += 1

    return dict(
        num_qubits=qubits,
        num_gates=total,
        num_cx=num_cx,
        num_measure=num_measure,
        num_u1=num_u1,
        num_u2=num_u2,
        num_u3=num_u3,
    )

# ---------- Orchestrator ----------

def process_file(c_path: pathlib.Path, bits: int, cc: str, run_cmd: str = None) -> Dict[str, int]:
    # 1) CC
    cc_val = cyclomatic_lizard(c_path)

    # 2) Ir
    binp = BIN_DIR / c_path.stem
    compile_c_for_valgrind(c_path, binp, cc=cc)
    ir_val = callgrind_ir(binp, run_cmd=run_cmd)

    # 3) QASM dalla pipeline (usiamo run=True per avere export_qasm "standard")
    qasm_path = pipeline.compile_c_file(str(c_path), num_bits=bits, run=True, verbose=False, pretty=False)
    qasm_src  = pathlib.Path(qasm_path)
    dest      = QASM_DIR / qasm_src.name
    if qasm_src != dest:
        dest.write_text(qasm_src.read_text())

    qm = count_qasm_metrics(dest)

    return dict(
        cyclomatic=cc_val,
        ir_instructions=ir_val,
        **qm
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=str, required=True, help="Cartella con i .c")
    ap.add_argument("--bits", type=int, default=16, help="num_bits per la pipeline (default: 16)")
    ap.add_argument("--cc", type=str, default="gcc", help="C compiler per Valgrind (default: gcc)")
    ap.add_argument("--input-cmd", type=str, default=None,
                    help="Comando shell per fornire input ai programmi (es: \"echo '42' |\")")
    ap.add_argument("--out", type=str, default=str(RESULTS_DIR / "metrics.csv"))
    args = ap.parse_args()

    corpus = pathlib.Path(args.corpus)
    c_files = sorted(p for p in corpus.glob("*.c"))

    rows: List[Dict] = []
    for c_path in c_files:
        try:
            print(f"[+] {c_path.name}")
            r = process_file(c_path, bits=args.bits, cc=args.cc, run_cmd=args.input_cmd)
            rows.append(dict(file=c_path.name, **r))
        except Exception as e:
            print(f"[!] FAIL {c_path.name}: {e}")

    out_csv = pathlib.Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "file", "cyclomatic", "ir_instructions",
            "num_qubits","num_gates","num_cx","num_measure","num_u1","num_u2","num_u3"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[✓] Written: {out_csv} — {len(rows)} file OK")

if __name__ == "__main__":
    main()

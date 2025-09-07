#!/usr/bin/env python3
"""
bench_all.py — End-to-end:
- Cyclomatic Complexity (Lizard)
- Instruction Count Ir (Valgrind/Callgrind) su architettura target
- Circuit metrics from QASM (num_qubits, total_gates, cx, measure, u1,u2,u3)
- Output: tools/results/metrics.csv  (results è allo stesso livello di questo file)

Usage:
  python tools/bench_all.py --corpus corpus_c --bits 16 --arch x86-64
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
import time
from typing import Dict, List, Optional

# === Path setup ===
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
ROOT       = SCRIPT_DIR.parents[0]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pipeline  # <-- il file pipeline.py

# === results allo stesso livello di questo file ===
RESULTS_DIR = SCRIPT_DIR / "results"
QASM_DIR    = RESULTS_DIR / "qasm"
BIN_DIR     = RESULTS_DIR / "bin"
RESULTS_DIR.mkdir(exist_ok=True)
QASM_DIR.mkdir(parents=True, exist_ok=True)
BIN_DIR.mkdir(parents=True, exist_ok=True)

# --- in alto ---
import traceback

# ---------- Logging helpers ----------
def stamp() -> str:
    return time.strftime("%H:%M:%S")

def log(stage: str, msg: str):
    # Stampa SOLO gli errori (su stderr) e il riepilogo finale se vuoi
    if stage == "ERROR":
        print(f"[{stamp()}] [{stage}] {msg}", file=sys.stderr)
    # opzionale: mostra solo il DONE finale
    elif stage == "DONE":
        print(f"[{stamp()}] [{stage}] {msg}")
    # tutte le altre fasi tacciono
    return

def timed(stage: str):
    class _Ctx:
        def __enter__(self):
            # niente log
            return self
        def __exit__(self, exc_type, exc, tb):
            # niente log
            return False  # non sopprime le eccezioni
    return _Ctx()

# ---------- C metrics ----------

def cyclomatic_lizard(c_path: pathlib.Path) -> float:
    """
    Ritorna CC = somma delle CCN delle funzioni nel file.
    Usa lizard (JSON) o fallback euristico.
    """
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
            pass

    # 2) Retry senza -l c
    res2 = run_lizard(["-j", str(c_path)])
    if res2.returncode == 0:
        try:
            data = json.loads(res2.stdout)
            funcs = data[0].get("functions", [])
            return float(sum(f.get("cyclomatic_complexity", 1) for f in funcs)) if funcs else 1.0
        except Exception:
            pass

    # 3) Fallback euristico
    text = c_path.read_text(encoding="utf-8", errors="ignore")
    tokens = [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b", r"&&", r"\|\|", r"\?"]
    cc = 1
    for pat in tokens:
        cc += len(re.findall(pat, text))
    return float(cc)


def compile_c_for_valgrind(c_path: pathlib.Path, out_bin: pathlib.Path, cc="gcc", arch: Optional[str] = None):
    """
    Compila il sorgente C per un'architettura target (default: host).
    Esempio: --cc arm-linux-gnueabi-gcc --arch arm
    """
    cmd = [cc, "-O0", "-g", str(c_path), "-o", str(out_bin)]
    if arch:
        arch_l = arch.lower()
        if arch_l == "arm":
            cmd.insert(1, "-march=armv7-a")
        elif arch_l in ("x86", "i686"):
            cmd.insert(1, "-march=i686")
        elif arch_l in ("x86-64", "x86_64", "amd64"):
            cmd.insert(1, "-march=x86-64")
        # estendibile qui
    log("BUILD", " ".join(cmd))
    subprocess.run(cmd, check=True)

def callgrind_ir(bin_path: pathlib.Path, run_cmd: Optional[str] = None) -> Optional[int]:
    """
    Esegue Valgrind/Callgrind e restituisce Ir.
    """
    if shutil.which("valgrind") is None:
        log("CALLGRIND", "Valgrind non trovato → Ir = NA")
        return None

    has_annot = shutil.which("callgrind_annotate") is not None

    try:
        bin_path.chmod(bin_path.stat().st_mode | 0o111)
    except Exception:
        pass

    with tempfile.TemporaryDirectory() as td:
        tmp_bin = pathlib.Path(td) / bin_path.name
        shutil.copy2(bin_path, tmp_bin)
        tmp_bin.chmod(tmp_bin.stat().st_mode | 0o111)
        cg_out = pathlib.Path(td) / "callgrind.out"

        env = os.environ.copy()
        env["LANG"] = "C"
        env["LC_ALL"] = "C"

        vg_cmd = [
            "valgrind",
            "--tool=callgrind",
            f"--callgrind-out-file={str(cg_out)}",
            str(tmp_bin)
        ]
        log("CALLGRIND", " ".join(vg_cmd))

        res = subprocess.run(
            vg_cmd,
            input=run_cmd if run_cmd is not None else None,
            text=True,
            capture_output=True,
            env=env
        )

        if not cg_out.exists():
            log("CALLGRIND", f"no output file.\nSTDERR:\n{res.stderr}\nSTDOUT:\n{res.stdout}")
            return None

        if has_annot:
            ann = subprocess.run(
                ["callgrind_annotate", str(cg_out)],
                capture_output=True, text=True, env=env
            )
            if ann.returncode == 0:
                m = re.search(r"\bIr\s*:\s*([\d,\.]+)", ann.stdout)
                if m:
                    return int(m.group(1).replace(",", "").replace(".", ""))

        try:
            raw = cg_out.read_text()
            ev_m = re.search(r"^events:\s*(.+)$", raw, re.MULTILINE)
            if not ev_m:
                return None
            events = ev_m.group(1).strip().split()
            try:
                ir_idx = events.index("Ir")
            except ValueError:
                return None
            sum_m = re.search(r"^summary:\s*([^\n]+)$", raw, re.MULTILINE)
            if not sum_m:
                return None
            nums = re.split(r"\s+", sum_m.group(1).strip())
            def clean_num(s: str) -> str:
                return re.sub(r"[,_\.]", "", s)
            if ir_idx < len(nums):
                return int(clean_num(nums[ir_idx]))
            elif len(nums) == 1 and ir_idx == 0:
                return int(clean_num(nums[0]))
            return None
        except Exception:
            return None

# ---------- QASM parsing ----------

_QREG_RE     = re.compile(r"qreg\s+\w+\[(\d+)\];")
_CX_RE       = re.compile(r"^\s*cx\s", re.MULTILINE)
_MEASURE_RE  = re.compile(r"^\s*measure\s", re.MULTILINE)
_U1_RE       = re.compile(r"^\s*u1\(", re.MULTILINE)
_U2_RE       = re.compile(r"^\s*u2\(", re.MULTILINE)
_U3_RE       = re.compile(r"^\s*u3\(", re.MULTILINE)

def count_qasm_metrics(qasm_path: pathlib.Path) -> Dict[str, int]:
    text = qasm_path.read_text()
    qubits = sum(int(m.group(1)) for m in _QREG_RE.finditer(text))
    num_cx      = len(_CX_RE.findall(text))
    num_measure = len(_MEASURE_RE.findall(text))
    num_u1      = len(_U1_RE.findall(text))
    num_u2      = len(_U2_RE.findall(text))
    num_u3      = len(_U3_RE.findall(text))
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

def process_file(c_path: pathlib.Path, bits: int, cc: str, arch: Optional[str], run_cmd: Optional[str] = None) -> Dict[str, int]:
    log("FILE", c_path.name)

    with timed("CC/LIZARD"):
        cc_val = cyclomatic_lizard(c_path)

    binp = BIN_DIR / c_path.stem
    with timed("BUILD"):
        compile_c_for_valgrind(c_path, binp, cc=cc, arch=arch)

    with timed("CALLGRIND"):
        ir_val = callgrind_ir(binp, run_cmd=run_cmd)

    with timed("PIPELINE→QASM"):
        qasm_path = pipeline.compile_c_file(str(c_path), num_bits=bits, run=True, verbose=False, pretty=False)

    qasm_src  = pathlib.Path(qasm_path)
    dest      = QASM_DIR / qasm_src.name
    if qasm_src != dest:
        dest.write_text(qasm_src.read_text())

    with timed("QASM/PARSE"):
        qm = count_qasm_metrics(dest)


    return dict(cyclomatic=cc_val, ir_instructions=ir_val, **qm)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=str, required=True, help="Cartella con i .c")
    ap.add_argument("--bits", type=int, default=16, help="num_bits per la pipeline (default: 16)")
    ap.add_argument("--cc", type=str, default="gcc", help="C compiler per Valgrind (default: gcc)")
    ap.add_argument("--arch", type=str, default=None, help="Architettura target (es: arm, x86, x86-64)")
    ap.add_argument("--input-cmd", type=str, default=None,
                    help="Input da passare ai programmini (es: \"42\\n\")")
    ap.add_argument("--out", type=str, default=str(RESULTS_DIR / "metrics.csv"))
    args = ap.parse_args()

    corpus = pathlib.Path(args.corpus)
    c_files = sorted(p for p in corpus.glob("*.c"))

    rows: List[Dict] = []
    for idx, c_path in enumerate(c_files, 1):
        try:
            log("PROGRESS", f"{idx}/{len(c_files)} → {c_path.name}")
            r = process_file(c_path, bits=args.bits, cc=args.cc, arch=args.arch, run_cmd=args.input_cmd)
            rows.append(dict(file=c_path.name, **r))
        except KeyboardInterrupt:
            log("ABORT", "interrotto dall'utente")
            break
        except Exception as e:
            log("ERROR", f"{c_path.name}: {e}")

    out_csv = pathlib.Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "file", "cyclomatic", "ir_instructions",
            "num_qubits","num_gates","num_cx","num_measure","num_u1","num_u2","num_u3"
        ])
        writer.writeheader()
        writer.writerows(rows)

    log("DONE", f"Written: {out_csv} — {len(rows)} file OK")

if __name__ == "__main__":
    main()

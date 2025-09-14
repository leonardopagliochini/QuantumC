#!/usr/bin/env python3
"""
scan_cc_ir.py — Estrae solo:
- Complessità ciclomatica (Lizard)
- Numero di istruzioni Ir (Valgrind/Callgrind)

Output: tools/results/cc_ir.csv (di default)

Uso:
  python tools/scan_cc_ir.py --corpus corpus_c
Opzioni utili:
  --cc gcc                  # compilatore C
  --arch x86-64             # arch target (facoltativo)
  --input-cmd "42\\n"       # input su stdin al binario (facoltativo)
  --out tools/results/<corpus>_cc_ir.csv
  --progress auto|plain|none
  --show-stages             # log sintetico per file
"""

import argparse
import csv
import os
import concurrent.futures
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from typing import Dict, List, Optional

# === Path setup ===
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"
BIN_DIR     = RESULTS_DIR / "bin"
RESULTS_DIR.mkdir(exist_ok=True)
BIN_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Helpers ----------
def _run_lizard(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "lizard", *args],
        capture_output=True, text=True
    )

def cyclomatic_lizard(c_path: pathlib.Path) -> float:
    """
    Ritorna la somma delle CCN delle funzioni nel file (fallback euristico se serve).
    """
    # 1) JSON con lingua C
    res = _run_lizard(["-l", "c", "-j", str(c_path)])
    if res.returncode == 0:
        try:
            data = __import__("json").loads(res.stdout)
            funcs = data[0].get("functions", [])
            return float(sum(f.get("cyclomatic_complexity", 1) for f in funcs)) if funcs else 1.0
        except Exception:
            pass
    # 2) JSON senza lingua
    res2 = _run_lizard(["-j", str(c_path)])
    if res2.returncode == 0:
        try:
            data = __import__("json").loads(res2.stdout)
            funcs = data[0].get("functions", [])
            return float(sum(f.get("cyclomatic_complexity", 1) for f in funcs)) if funcs else 1.0
        except Exception:
            pass
    # 3) Fallback euristico
    try:
        text = c_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 1.0
    tokens = [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b", r"&&", r"\|\|", r"\?"]
    cc = 1
    for pat in tokens:
        cc += len(re.findall(pat, text))
    return float(cc)

def compile_c_for_valgrind(c_path: pathlib.Path, out_bin: pathlib.Path, cc="gcc", arch: Optional[str] = None):
    """
    Compila il C in un binario debug (-O0 -g). 'arch' è facoltativo.
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
    subprocess.run(cmd, check=True)

def callgrind_ir(bin_path: pathlib.Path, run_cmd: Optional[str] = None, instr_atstart_no: bool = False, toggle_func: Optional[str] = None) -> Optional[int]:
    """
    Esegue Valgrind/Callgrind e ritorna Ir, oppure None se non disponibile/fallisce.
    """
    if shutil.which("valgrind") is None:
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
        # ROI control: prefer function-based toggle if provided
        if toggle_func:
            vg_cmd.insert(2, f"--toggle-collect={toggle_func}")
            vg_cmd.insert(2, "--collect-atstart=no")
        elif instr_atstart_no:
            vg_cmd.insert(2, "--instr-atstart=no")

        res = subprocess.run(
            vg_cmd,
            input=run_cmd if run_cmd is not None else None,
            text=True,
            capture_output=True,
            env=env
        )
        # Se non ha generato l'output, fallisce
        if not cg_out.exists():
            return None

        # 1) Prova con callgrind_annotate
        if has_annot:
            ann = subprocess.run(
                ["callgrind_annotate", str(cg_out)],
                capture_output=True, text=True, env=env
            )
            if ann.returncode == 0:
                m = re.search(r"\bIr\s*:\s*([\d,\.]+)", ann.stdout)
                if m:
                    return int(m.group(1).replace(",", "").replace(".", ""))

        # 2) Fallback: parse del raw
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

# ---------- Progress minimal ----------
class _PlainProgress:
    def __init__(self, total: int, desc: str = ""):
        self.total = max(int(total), 0)
        self.count = 0
        self.desc  = desc or "Processing"
        self._last_len = 0
        self._start = time.perf_counter()
        self._print()

    def _print(self):
        pct = (self.count / self.total) * 100.0 if self.total > 0 else 0.0
        elapsed = time.perf_counter() - self._start
        rate = self.count / elapsed if elapsed > 0 else 0.0
        rem = (self.total - self.count) / rate if rate > 0 else float("inf")
        bar = f"{self.desc}: {self.count}/{self.total} ({pct:5.1f}%) | elapsed {elapsed:6.1f}s | eta {rem:6.1f}s"
        sys.stdout.write("\r" + " " * self._last_len + "\r")
        sys.stdout.write(bar)
        sys.stdout.flush()
        self._last_len = len(bar)

    def update(self, n: int = 1):
        self.count = min(self.total, self.count + n)
        self._print()

    def write(self, s: str):
        sys.stdout.write("\r" + " " * self._last_len + "\r")
        sys.stdout.write(s.rstrip() + "\n")
        sys.stdout.flush()
        self._print()

    def close(self):
        self._print()
        sys.stdout.write("\n")
        sys.stdout.flush()

class _TqdmProgress:
    def __init__(self, total: int, desc: str = ""):
        from tqdm import tqdm  # type: ignore
        self._tqdm = tqdm(total=total, desc=desc or "Files", unit="file")
    def update(self, n: int = 1): self._tqdm.update(n)
    def write(self, s: str):
        from tqdm import tqdm as _tqdm_cls  # type: ignore
        _tqdm_cls.write(s.rstrip())
    def close(self): self._tqdm.close()

def _make_progress(total: int, mode: str, desc: str = ""):
    if mode == "none":
        return None
    if mode == "plain":
        return _PlainProgress(total, desc=desc)
    if mode == "auto":
        try:
            import importlib
            importlib.import_module("tqdm")
            return _TqdmProgress(total, desc=desc)
        except Exception:
            return _PlainProgress(total, desc=desc)
    return _PlainProgress(total, desc=desc)

# ---------- Main per-file ----------
def process_file(c_path: pathlib.Path, cc_compiler: str, arch: Optional[str],
                 run_cmd: Optional[str], stage_writer=None, roi: bool = False, roi_func: Optional[str] = None) -> Dict[str, Optional[float]]:
    """
    Per ciascun file C:
      - calcola CC (Lizard)
      - compila ed esegue Callgrind per Ir
    """
    # CC
    cc_val: Optional[float] = None
    try:
        if stage_writer: stage_writer(f"{c_path.name}: CC/LIZARD…")
        cc_val = cyclomatic_lizard(c_path)
        if stage_writer: stage_writer(f"{c_path.name}: CC/LIZARD ✓ (CC={cc_val})")
    except Exception:
        if stage_writer: stage_writer(f"{c_path.name}: CC/LIZARD ✗")
        cc_val = None

    # Build
    ir_val: Optional[int] = None
    binp = BIN_DIR / c_path.stem
    try:
        if stage_writer: stage_writer(f"{c_path.name}: BUILD…")
        compile_c_for_valgrind(c_path, binp, cc=cc_compiler, arch=arch)
        if stage_writer: stage_writer(f"{c_path.name}: BUILD ✓")
    except Exception:
        if stage_writer: stage_writer(f"{c_path.name}: BUILD ✗")
        binp = None

    # Callgrind
    if binp is not None:
        try:
            if stage_writer: stage_writer(f"{c_path.name}: CALLGRIND…")
            ir_val = callgrind_ir(binp, run_cmd=run_cmd, instr_atstart_no=roi, toggle_func=roi_func)
            if stage_writer: stage_writer(f"{c_path.name}: CALLGRIND ✓ (Ir={ir_val if ir_val is not None else 'NA'})")
        except Exception:
            if stage_writer: stage_writer(f"{c_path.name}: CALLGRIND ✗")
            ir_val = None

    return dict(cyclomatic=cc_val, ir_instructions=ir_val)

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=str, required=True, help="Cartella con i .c")
    ap.add_argument("--cc", type=str, default="gcc", help="Compilatore C (default: gcc)")
    ap.add_argument("--arch", type=str, default=None, help="Arch target (es: x86-64, arm)")
    ap.add_argument("--input-cmd", type=str, default=None, help='Input su stdin al binario (es: "42\\n")')
    ap.add_argument("--out", type=str, default=None, help="Output CSV (default: tools/results/<corpus>_cc_ir.csv)")
    ap.add_argument("--progress", choices=["auto", "plain", "none"], default="auto")
    ap.add_argument("--show-stages", action="store_true", help="Log sintetico per file")
    ap.add_argument("--roi", action="store_true", help="Usa Callgrind con --instr-atstart=no per misurare solo il ROI")
    ap.add_argument("--roi-func", type=str, default=None, help="Se impostato, usa --toggle-collect=<func> (es. roi_block)")
    args = ap.parse_args()

    corpus = pathlib.Path(args.corpus)
    c_files = sorted(p for p in corpus.glob("*.c"))

    # Determine output CSV path early (for skip logic)
    if args.out is None:
        corpus_name = corpus.name.rstrip(os.sep)
        out_csv = RESULTS_DIR / f"{corpus_name}_cc_ir.csv"
    else:
        out_csv = pathlib.Path(args.out)

    # Load existing entries if present
    existing_rows: List[Dict[str, Optional[float]]] = []
    existing_set: set[str] = set()
    if out_csv.exists():
        try:
            with out_csv.open("r", newline="", encoding="utf-8") as f:
                rd = csv.DictReader(f)
                for row in rd:
                    fn = row.get("file")
                    if fn:
                        existing_set.add(fn)
                        existing_rows.append({
                            "file": fn,
                            "cyclomatic": row.get("cyclomatic"),
                            "ir_instructions": row.get("ir_instructions"),
                        })
        except Exception:
            existing_rows = []
            existing_set = set()

    progress = _make_progress(len(c_files), mode=args.progress, desc="Files")

    def stage_writer(msg: str):
        if not args.show_stages:
            return
        if progress is None:
            print(msg)
        else:
            progress.write(msg)

    rows_new: List[Dict[str, Optional[float]]] = []

    # Build work lists: mark skips up-front, then parallelize the remaining
    to_process: List[pathlib.Path] = []
    try:
        for c_path in c_files:
            if c_path.name in existing_set:
                if progress is not None:
                    progress.write(f"{c_path.name}: SKIP — already in {out_csv.name}")
                else:
                    print(f"{c_path.name}: SKIP — already in {out_csv.name}")
                if progress: progress.update(1)
            else:
                to_process.append(c_path)

        # Parallel processing for remaining files
        if to_process:
            max_workers = max(1, (os.cpu_count() or 2) - 1)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
                future_map = {
                    ex.submit(
                        process_file,
                        c_path,
                        cc_compiler=args.cc,
                        arch=args.arch,
                        run_cmd=args.input_cmd,
                        stage_writer=None,  # avoid interleaved stage logs in parallel
                        roi=args.roi,
                        roi_func=args.roi_func,
                    ): c_path for c_path in to_process
                }
                for fut in concurrent.futures.as_completed(future_map):
                    c_path = future_map[fut]
                    try:
                        r = fut.result()
                        rows_new.append(dict(file=c_path.name, **r))
                        if progress is not None and args.show_stages:
                            progress.write(f"{c_path.name}: DONE (CC={r.get('cyclomatic')}, Ir={r.get('ir_instructions')})")
                    except KeyboardInterrupt:
                        if progress: progress.write("Interrotto dall'utente")
                        raise
                    except Exception:
                        if progress: progress.write(f"{c_path.name}: eccezione non gestita")
                        print(traceback.format_exc(), file=sys.stderr)
                    finally:
                        if progress: progress.update(1)
    finally:
        if progress: progress.close()

    # Combine existing + new rows
    all_rows = list(existing_rows) + rows_new
    # Reorder rows: by cyclomatic (numeric), then by ir_instructions (numeric), then by file name
    def _to_float(v):
        try:
            return float(v)
        except Exception:
            return float("inf")
    def _to_int(v):
        try:
            return int(v)
        except Exception:
            try:
                return int(float(v))
            except Exception:
                return 10**18
    all_rows.sort(key=lambda r: (_to_float(r.get('cyclomatic')), _to_int(r.get('ir_instructions')), r.get('file') or ""))
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "cyclomatic", "ir_instructions"])
        w.writeheader()
        w.writerows(all_rows)

    print(f"[DONE] Written: {out_csv} — {len(all_rows)} files")

if __name__ == "__main__":
    main()

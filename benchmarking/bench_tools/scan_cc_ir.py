#!/usr/bin/env python3
"""
scan_cc_ir.py — misura:
- Complessità ciclomatica (Lizard)
- Numero di istruzioni Ir (Valgrind/Callgrind)

Output predefinito: benchmarking/bench_tools/results/<corpus>_cc_ir.csv

Uso diretto:
  python benchmarking/bench_tools/scan_cc_ir.py --corpus PATH_TO_C_FILES

Tipicamente viene richiamato da benchmarking/study_scan.py che risolve i
percorsi per una determinata study.
"""

import argparse
import concurrent.futures
import csv
import os
import pathlib
import sys
import time
import traceback
from typing import Dict, List, Optional, Tuple

try:
    from .metrics_common import callgrind_ir, compile_c_for_valgrind, cyclomatic_lizard
except ImportError:
    import sys as _sys
    import pathlib as _pathlib

    _sys.path.append(str(_pathlib.Path(__file__).resolve().parent))
    from metrics_common import callgrind_ir, compile_c_for_valgrind, cyclomatic_lizard

# === Path setup ===
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"
BIN_DIR     = RESULTS_DIR / "bin"
RESULTS_DIR.mkdir(exist_ok=True)
BIN_DIR.mkdir(parents=True, exist_ok=True)

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
    # Simplified: ROI is disabled; measurement is whole-program Ir only.
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
                        roi=False,          # always whole-program Ir
                        roi_func=None,
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

    # Compute per-CC baselines and populate ir_offset column
    baseline_map: Dict[str, int] = {}

    def _cc_key(val: Optional[str]) -> Optional[str]:
        if val is None:
            return None
        try:
            return str(int(float(val)))
        except Exception:
            return val

    def _ir_int(val: Optional[str]) -> Optional[int]:
        if val is None:
            return None
        try:
            return int(float(val))
        except Exception:
            try:
                return int(val)
            except Exception:
                return None

    for row in all_rows:
        cc_key = _cc_key(str(row.get("cyclomatic")))
        ir_int = _ir_int(str(row.get("ir_instructions")))
        if cc_key is None or ir_int is None:
            continue
        current = baseline_map.get(cc_key)
        if current is None or ir_int < current:
            baseline_map[cc_key] = ir_int

    for row in all_rows:
        cc_key = _cc_key(str(row.get("cyclomatic")))
        ir_int = _ir_int(str(row.get("ir_instructions")))
        if cc_key is None or ir_int is None:
            row["ir_offset"] = ""
            continue
        base = baseline_map.get(cc_key)
        if base is None:
            row["ir_offset"] = ""
        else:
            row["ir_offset"] = str(ir_int - base)
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
        w = csv.DictWriter(f, fieldnames=["file", "cyclomatic", "ir_instructions", "ir_offset"])
        w.writeheader()
        w.writerows(all_rows)

    print(f"[DONE] Written: {out_csv} — {len(all_rows)} files")

if __name__ == "__main__":
    main()

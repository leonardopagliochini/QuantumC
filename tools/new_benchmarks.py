#!/usr/bin/env python3
"""
new_benchmark.py — End-to-end:
- Cyclomatic Complexity (Lizard)
- Instruction Count Ir (Valgrind/Callgrind) on target arch
- Circuit metrics from QASM (num_qubits, total_gates, cx, measure, u1,u2,u3, depth)
- Output: tools/results/metrics.csv  (results is at the same level as this file)

New metrics:
- wall_time_s        (per-file wall time)
- peak_rss_bytes     (peak RSS of this Python proc + children; requires psutil)

Usage:
  python tools/new_benchmark.py --corpus corpus_c --bits 16 --arch x86-64
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
import traceback
import threading
from typing import Dict, List, Optional, Union

# Optional: psutil for accurate per-file peak memory
try:
    import psutil  # type: ignore
except Exception:  # keep running without hard dep
    psutil = None  # type: ignore

# === Path setup ===
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
ROOT       = SCRIPT_DIR.parents[0]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pipeline  # your pipeline.py

# === results at the same level as this file ===
RESULTS_DIR = SCRIPT_DIR / "results"
QASM_DIR    = RESULTS_DIR / "qasm"
BIN_DIR     = RESULTS_DIR / "bin"
RESULTS_DIR.mkdir(exist_ok=True)
QASM_DIR.mkdir(parents=True, exist_ok=True)
BIN_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Logging helpers ----------
def _stamp() -> str:
    return time.strftime("%H:%M:%S")

def log(stage: str, msg: str, *, err: bool = False):
    """
    Minimal logger:
    - prints only ERROR/DONE by default
    - prints to stderr when err=True or stage == 'ERROR'
    """
    if stage in ("ERROR", "DONE"):
        dest = sys.stderr if err or stage == "ERROR" else sys.stdout
        print(f"[{_stamp()}] [{stage}] {msg}", file=dest, flush=True)

def timed(_stage: str):
    """Quiet timing context (hook for future timing if needed)."""
    class _Ctx:
        def __enter__(self):
            self._t0 = time.perf_counter()
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
    return _Ctx()

# ---------- Optional memory sampler (psutil) ----------
class MemorySampler:
    """
    Samples peak RSS (bytes) of the current process + all its children
    while the context is active. Requires psutil; otherwise does nothing.

    Usage:
        with MemorySampler(interval=0.05) as ms:
            ... work ...
        peak = ms.peak_bytes
    """
    def __init__(self, interval: float = 0.05):
        self.interval = max(0.01, float(interval))
        self._stop = threading.Event()
        self._thr: Optional[threading.Thread] = None
        self.peak_bytes: Optional[int] = None

    def __enter__(self):
        if psutil is None:
            self.peak_bytes = None
            return self
        proc = psutil.Process(os.getpid())

        def sample_loop():
            local_peak = 0
            while not self._stop.is_set():
                try:
                    total = 0
                    # include children recursively
                    procs = [proc] + proc.children(recursive=True)
                    for p in procs:
                        try:
                            mi = p.memory_info()
                            total += getattr(mi, "rss", 0)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    if total > local_peak:
                        local_peak = total
                except Exception:
                    pass
                self._stop.wait(self.interval)
            self.peak_bytes = local_peak

        self._thr = threading.Thread(target=sample_loop, daemon=True)
        self._thr.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._thr is not None:
            self._stop.set()
            self._thr.join(timeout=1.0)
        return False

# ---------- C metrics ----------

def _run_lizard(args: List[str]) -> subprocess.CompletedProcess:
    # Use Python module invocation — avoids relying on a 'lizard' binary in PATH
    return subprocess.run(
        [sys.executable, "-m", "lizard", *args],
        capture_output=True, text=True
    )

def cyclomatic_lizard(c_path: pathlib.Path) -> float:
    """
    Returns CC = sum of CCN of functions in the file.
    Tries lizard JSON modes, falls back to a simple heuristic if needed.
    """
    # 1) Preferred: -l c -j
    res = _run_lizard(["-l", "c", "-j", str(c_path)])
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            funcs = data[0].get("functions", [])
            return float(sum(f.get("cyclomatic_complexity", 1) for f in funcs)) if funcs else 1.0
        except Exception:
            pass

    # 2) Retry without -l c
    res2 = _run_lizard(["-j", str(c_path)])
    if res2.returncode == 0:
        try:
            data = json.loads(res2.stdout)
            funcs = data[0].get("functions", [])
            return float(sum(f.get("cyclomatic_complexity", 1) for f in funcs)) if funcs else 1.0
        except Exception:
            pass

    # 3) Heuristic fallback (language-agnostic)
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
    Compile C source for the target arch (default: host).
    Example: --cc arm-linux-gnueabi-gcc --arch arm
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
        # extend here if needed
    subprocess.run(cmd, check=True)

def callgrind_ir(bin_path: pathlib.Path, run_cmd: Optional[str] = None) -> Optional[int]:
    """
    Run Valgrind/Callgrind and return Ir count, or None if unavailable/failed.
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

        res = subprocess.run(
            vg_cmd,
            input=run_cmd if run_cmd is not None else None,
            text=True,
            capture_output=True,
            env=env
        )

        if not cg_out.exists():
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

        # Fallback parse of raw file
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

# generic qubit token (e.g., q[0], qr[12])
_QBIT_TOK_RE = re.compile(r"([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]")

def _is_comment_or_header(s: str) -> bool:
    return (
        (not s) or s.startswith("//")
        or s.startswith("OPENQASM")
        or s.startswith("include")
        or s.startswith("qreg")
        or s.startswith("creg")
    )

def compute_qasm_depth(qasm_text: str) -> int:
    """Greedy earliest-start layering; barriers cause layer bumps."""
    last_layer: Dict[str, int] = {}
    depth = 0
    for raw in qasm_text.splitlines():
        s = raw.strip()
        if _is_comment_or_header(s):
            continue
        if s.startswith("barrier"):
            qubits = [f"{n}[{i}]" for n, i in _QBIT_TOK_RE.findall(s)]
            if not qubits:
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
        if _is_comment_or_header(s):
            continue
        if s.startswith("barrier"):
            continue
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

# ---------- Orchestrator ----------

def process_file(
    c_path: pathlib.Path,
    bits: int,
    cc: str,
    arch: Optional[str],
    run_cmd: Optional[str] = None,
    stage_writer=None,
    mem_sample_interval: float = 0.05
) -> Dict[str, Optional[Union[int, float]]]:
    """
    Process a single C file. Each stage is isolated so we can continue on partial failures.
    Returns metrics including wall_time_s and peak_rss_bytes (if psutil available).
    """
    t0 = time.perf_counter()
    peak_rss_bytes: Optional[int] = None

    def stage(msg: str):
        if stage_writer is not None:
            stage_writer(f"{c_path.name}: {msg}")

    # Memory sampling for the whole per-file window
    with MemorySampler(interval=mem_sample_interval) as ms:
        # STAGE 1: Cyclomatic complexity
        cc_val: Optional[float] = None
        try:
            stage("CC/LIZARD…")
            with timed("CC/LIZARD"):
                cc_val = cyclomatic_lizard(c_path)
            stage(f"CC/LIZARD ✓  (CC={cc_val})")
        except Exception:
            stage("CC/LIZARD ✗")
            log("ERROR", f"{c_path.name}: cyclomatic analysis failed\n{traceback.format_exc()}", err=True)

        # STAGE 2: Build binary (for Callgrind)
        binp: Optional[pathlib.Path] = BIN_DIR / c_path.stem
        try:
            stage("BUILD…")
            with timed("BUILD"):
                compile_c_for_valgrind(c_path, binp, cc=cc, arch=arch)
            stage("BUILD ✓")
        except Exception:
            stage("BUILD ✗")
            log("ERROR", f"{c_path.name}: build failed\n{traceback.format_exc()}", err=True)
            binp = None  # mark as unavailable

        # STAGE 3: Callgrind IR
        ir_val: Optional[int] = None
        if binp is not None:
            try:
                stage("CALLGRIND…")
                with timed("CALLGRIND"):
                    ir_val = callgrind_ir(binp, run_cmd=run_cmd)
                stage(f"CALLGRIND ✓  (Ir={ir_val if ir_val is not None else 'NA'})")
            except Exception:
                stage("CALLGRIND ✗")
                log("ERROR", f"{c_path.name}: callgrind failed\n{traceback.format_exc()}", err=True)

        # STAGE 4: Pipeline → QASM
        qasm_dest: Optional[pathlib.Path] = None
        try:
            stage("PIPELINE→QASM…")
            with timed("PIPELINE→QASM"):
                qasm_path = pipeline.compile_c_file(str(c_path), num_bits=bits, run=True, verbose=False, pretty=False)
            qasm_src  = pathlib.Path(qasm_path)
            qasm_dest = QASM_DIR / qasm_src.name
            if qasm_src != qasm_dest:
                qasm_dest.write_text(qasm_src.read_text())
            else:
                if not qasm_dest.exists():
                    qasm_dest.write_text(qasm_src.read_text())
            stage("PIPELINE→QASM ✓")
        except Exception:
            stage("PIPELINE→QASM ✗")
            log("ERROR", f"{c_path.name}: pipeline → QASM failed\n{traceback.format_exc()}", err=True)
            qasm_dest = None

        # STAGE 5: Parse QASM metrics
        qm: Dict[str, Optional[int]] = dict(
            num_qubits=None, num_gates=None, num_cx=None, num_measure=None, num_u1=None, num_u2=None, num_u3=None, depth=None
        )
        if qasm_dest is not None and qasm_dest.exists():
            try:
                stage("QASM/PARSE…")
                with timed("QASM/PARSE"):
                    qm = count_qasm_metrics(qasm_dest)
                stage("QASM/PARSE ✓")
            except Exception:
                stage("QASM/PARSE ✗")
                log("ERROR", f"{c_path.name}: QASM parse failed\n{traceback.format_exc()}", err=True)

        # end sampling window
        peak_rss_bytes = ms.peak_bytes

    wall_time_s = time.perf_counter() - t0

    return dict(
        cyclomatic=cc_val if 'cc_val' in locals() and cc_val is not None else None,
        ir_instructions=locals().get('ir_val', None),
        **locals().get('qm', {}),
        wall_time_s=round(wall_time_s, 6),
        peak_rss_bytes=peak_rss_bytes
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=str, required=True, help="Folder with .c files")
    ap.add_argument("--bits", type=int, default=16, help="num_bits for the pipeline (default: 16)")
    ap.add_argument("--cc", type=str, default="gcc", help="C compiler for Valgrind (default: gcc)")
    ap.add_argument("--arch", type=str, default=None, help="Target architecture (e.g., arm, x86, x86-64)")
    ap.add_argument("--input-cmd", type=str, default=None,
                    help='Input to pass to the binaries (e.g., "42\\n")')
    ap.add_argument("--out", type=str, default=str(RESULTS_DIR / "metrics.csv"))
    ap.add_argument("--progress", choices=["auto", "plain", "none"], default="auto",
                    help="Show a progress bar (auto=use tqdm if available).")
    ap.add_argument("--show-stages", action="store_true",
                    help="Print per-file stage updates (compact).")
    ap.add_argument("--mem-sample-interval", type=float, default=0.05,
                    help="Sampling interval in seconds for peak RSS (requires psutil).")
    args = ap.parse_args()

    corpus = pathlib.Path(args.corpus)
    c_files = sorted(p for p in corpus.glob("*.c"))

    # --- progress setup (same as before) ---
    # lightweight inline progress to avoid taking too much space
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
        def update(self, n: int = 1):
            self._tqdm.update(n)
        def write(self, s: str):
            from tqdm import tqdm as _tqdm_cls  # type: ignore
            _tqdm_cls.write(s.rstrip())
        def close(self):
            self._tqdm.close()

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

    progress = _make_progress(len(c_files), mode=args.progress, desc="Files")

    def stage_writer(msg: str):
        if not args.show_stages:
            return
        if progress is None:
            print(msg)
        else:
            progress.write(msg)

    rows: List[Dict[str, Union[str, int, float, None]]] = []
    try:
        for c_path in c_files:
            try:
                result = process_file(
                    c_path, bits=args.bits, cc=args.cc, arch=args.arch,
                    run_cmd=args.input_cmd, stage_writer=stage_writer if args.show_stages else None,
                    mem_sample_interval=args.mem_sample_interval
                )
                rows.append(dict(file=c_path.name, **result))
            except KeyboardInterrupt:
                if progress is not None:
                    progress.write("Interrupted by user")
                log("ERROR", "interrupted by user", err=True)
                break
            except Exception:
                if progress is not None:
                    progress.write(f"{c_path.name}: unhandled exception")
                log("ERROR", f"{c_path.name}: unhandled exception\n{traceback.format_exc()}", err=True)
            finally:
                if progress is not None:
                    progress.update(1)
    finally:
        if progress is not None:
            progress.close()

    out_csv = pathlib.Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "file", "cyclomatic", "ir_instructions",
            "num_qubits","num_gates","num_cx","num_measure","num_u1","num_u2","num_u3","depth",
            "wall_time_s","peak_rss_bytes"
        ])
        writer.writeheader()
        writer.writerows(rows)

    log("DONE", f"Written: {out_csv} — {len(rows)} file OK")

if __name__ == "__main__":
    main()

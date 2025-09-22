"""Study benchmarking runner based on whole_benchmark logic.

Processes a corpus of C sources by collecting Callgrind metrics, pipeline
outputs, and QASM statistics into the per-study results directory.
Supports parallel execution and appends rows incrementally like the original
``whole_benchmark`` tool before rewriting the final sorted CSV.
"""

from __future__ import annotations

import concurrent.futures
import csv
import importlib
import json
import os
import pathlib
import subprocess
import sys
import textwrap
import time
import traceback
from typing import Dict, List, Optional, Tuple, Union

from .metrics_common import (
    callgrind_ir,
    compile_c_for_valgrind,
    count_qasm_metrics,
    cyclomatic_lizard,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BENCH_DIR = pathlib.Path(__file__).resolve().parents[1]
METRIC_COLUMNS = [
    "cyclomatic",
    "ir_instructions",
    "ir_offset",
    "num_qubits",
    "num_gates",
    "num_cx",
    "num_measure",
    "num_u1",
    "num_u2",
    "num_u3",
    "depth",
    "user_time_s",
    "sys_time_s",
    "cpu_time_s",
    "max_rss_kb",
]

_PIPELINE_AVAILABLE: Optional[bool] = None


def ensure_pipeline_available() -> None:
    """Fail early with a helpful hint when the pipeline module is missing."""
    global _PIPELINE_AVAILABLE
    if _PIPELINE_AVAILABLE is None:
        try:
            importlib.import_module("pipeline")
            _PIPELINE_AVAILABLE = True
        except ModuleNotFoundError:
            _PIPELINE_AVAILABLE = False
    if not _PIPELINE_AVAILABLE:
        raise RuntimeError(
            "pipeline module not found. Activate the 'cotenv' conda environment or install project dependencies."
        )


class StageWriter:
    """Collect per-stage messages to replay in the main thread."""

    def __init__(self, enabled: bool, prefix: str = "    - ") -> None:
        self.enabled = enabled
        self.prefix = prefix
        self.messages: List[str] = []

    def __call__(self, message: str) -> None:
        if self.enabled:
            self.messages.append(f"{self.prefix}{message}")


class _PlainProgress:
    def __init__(self, total: int, desc: str = ""):
        self.total = max(int(total), 0)
        self.count = 0
        self.desc = desc or "Processing"
        self._last_len = 0
        self._start = time.perf_counter()
        self._print()

    def _print(self) -> None:
        pct = (self.count / self.total) * 100.0 if self.total > 0 else 0.0
        elapsed = time.perf_counter() - self._start
        rate = self.count / elapsed if elapsed > 0 else 0.0
        rem = (self.total - self.count) / rate if rate > 0 else float("inf")
        bar = f"{self.desc}: {self.count}/{self.total} ({pct:5.1f}%) | elapsed {elapsed:6.1f}s | eta {rem:6.1f}s"
        sys.stdout.write("\r" + " " * self._last_len + "\r")
        sys.stdout.write(bar)
        sys.stdout.flush()
        self._last_len = len(bar)

    def update(self, n: int = 1) -> None:
        self.count = min(self.total, self.count + n)
        self._print()

    def write(self, text: str) -> None:
        sys.stdout.write("\r" + " " * self._last_len + "\r")
        sys.stdout.write(text.rstrip() + "\n")
        sys.stdout.flush()
        self._print()

    def close(self) -> None:
        self._print()
        sys.stdout.write("\n")
        sys.stdout.flush()


class _TqdmProgress:
    def __init__(self, total: int, desc: str = ""):
        from tqdm import tqdm  # type: ignore

        self._tqdm = tqdm(total=total, desc=desc or "Files", unit="file")

    def update(self, n: int = 1) -> None:
        self._tqdm.update(n)

    def write(self, text: str) -> None:
        from tqdm import tqdm as _tqdm_cls  # type: ignore

        _tqdm_cls.write(text.rstrip())

    def close(self) -> None:
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


def resolve_study_dirs(
    study: str,
) -> Tuple[pathlib.Path, pathlib.Path, pathlib.Path, pathlib.Path]:
    base = BENCH_DIR / study
    dataset_dir = base / "dataset"
    legacy_dataset_dir = base / f"{study}_dataset"
    if not dataset_dir.exists():
        dataset_dir = legacy_dataset_dir
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found for study '{study}': {dataset_dir}")

    results_dir = base / f"{study}_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    qasm_dir = results_dir / "qasm"
    bin_dir = results_dir / "bin"
    qasm_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    return dataset_dir, results_dir, qasm_dir, bin_dir


def run_toolchain_subprocess(
    c_path: pathlib.Path,
    *,
    bits: int,
    max_iter: int,
) -> Tuple[Optional[str], Dict[str, Optional[Union[int, float, str]]]]:
    """Run pipeline.compile_c_file in a child process capturing timing info."""
    code = textwrap.dedent(
        f"""
        import json
        from pipeline import compile_c_file
        q = compile_c_file({json.dumps(str(c_path))}, num_bits={int(bits)}, run=True, max_iter={int(max_iter)}, verbose=False, pretty=False)
        print(json.dumps({{"qasm": q}}))
        """
    )
    cmd = ["/usr/bin/time", "-v", sys.executable, "-c", code]
    env = os.environ.copy()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), env=env)
    except FileNotFoundError:
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(ROOT), env=env)

    meta: Dict[str, Optional[Union[int, float, str]]] = {
        "returncode": proc.returncode,
        "stderr": proc.stderr,
        "stdout": proc.stdout,
        "user_time_s": None,
        "sys_time_s": None,
        "cpu_time_s": None,
        "max_rss_kb": None,
    }

    qasm_path: Optional[str] = None
    try:
        stripped = proc.stdout.strip()
        if stripped:
            line = stripped.splitlines()[-1]
            js = json.loads(line)
            qasm_path = js.get("qasm")
    except Exception:
        pass

    for line in proc.stderr.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if key.startswith("User time (seconds)"):
            try:
                meta["user_time_s"] = float(val)
            except Exception:
                pass
        elif key.startswith("System time (seconds)"):
            try:
                meta["sys_time_s"] = float(val)
            except Exception:
                pass
        elif key.startswith("Maximum resident set size"):
            try:
                meta["max_rss_kb"] = int(val)
            except Exception:
                pass

    user_time = meta.get("user_time_s")
    sys_time = meta.get("sys_time_s")
    if isinstance(user_time, (int, float)) and isinstance(sys_time, (int, float)):
        meta["cpu_time_s"] = float(user_time) + float(sys_time)
    else:
        meta["cpu_time_s"] = None

    return qasm_path, meta


def _copy_qasm(qasm_src: pathlib.Path, dest_dir: pathlib.Path) -> Optional[pathlib.Path]:
    try:
        dest = dest_dir / qasm_src.name
        dest.write_text(qasm_src.read_text(encoding="utf-8", errors="ignore"))
        return dest
    except Exception:
        return None


def process_file(
    c_path: pathlib.Path,
    *,
    bits: int,
    cc: str,
    arch: Optional[str],
    input_cmd: Optional[str],
    max_iter: int,
    ir_roi_func: Optional[str],
    qasm_out_dir: pathlib.Path,
    bin_out_dir: pathlib.Path,
    show_stages: bool,
    metrics_enabled: Dict[str, bool],
) -> Dict[str, Union[str, int, float, None]]:
    stage_writer = StageWriter(show_stages)
    errors: List[str] = []
    warnings: List[str] = []
    compile_stderr: Optional[str] = None
    pipeline_stderr: Optional[str] = None

    qasm_metric_keys = [
        "num_qubits",
        "num_gates",
        "num_cx",
        "num_measure",
        "num_u1",
        "num_u2",
        "num_u3",
        "depth",
    ]

    needs_cyclomatic = metrics_enabled.get("cyclomatic", True)
    needs_ir = metrics_enabled.get("ir_instructions", True) or metrics_enabled.get("ir_offset", True)
    required_qasm_keys = [key for key in qasm_metric_keys if metrics_enabled.get(key, True)]
    needs_qasm_metrics = bool(required_qasm_keys)
    needs_user_time = metrics_enabled.get("user_time_s", True)
    needs_sys_time = metrics_enabled.get("sys_time_s", True)
    needs_cpu_time = metrics_enabled.get("cpu_time_s", True)
    needs_rss = metrics_enabled.get("max_rss_kb", True)
    needs_timing = needs_user_time or needs_sys_time or needs_cpu_time or needs_rss
    needs_pipeline = needs_qasm_metrics or needs_timing

    cyclomatic: Optional[float] = None
    if needs_cyclomatic:
        stage_writer(f"{c_path.name}: cyclomatic complexity")
        try:
            cyclomatic = cyclomatic_lizard(c_path)
            stage_writer(f"{c_path.name}: cyclomatic complexity ok")
        except Exception as exc:
            cyclomatic = None
            warnings.append(f"cc_failed:{type(exc).__name__}")
            stage_writer(f"{c_path.name}: cyclomatic complexity failed")
    elif show_stages:
        stage_writer(f"{c_path.name}: cyclomatic skipped")

    ir_instructions: Optional[int] = None
    bin_path: Optional[pathlib.Path] = None
    if needs_ir:
        stage_writer(f"{c_path.name}: compile")
        bin_path = bin_out_dir / c_path.stem
        try:
            compile_c_for_valgrind(c_path, bin_path, cc=cc, arch=arch)
            stage_writer(f"{c_path.name}: compile ok")
        except subprocess.CalledProcessError as exc:
            errors.append(f"compile_failed rc={exc.returncode}")
            compile_stderr = exc.stderr or exc.output or ""
            bin_path = None
            stage_writer(f"{c_path.name}: compile failed")
        except Exception as exc:
            errors.append(f"compile_exc:{type(exc).__name__}")
            bin_path = None
            stage_writer(f"{c_path.name}: compile exception")

        if bin_path is not None:
            stage_writer(f"{c_path.name}: callgrind")
            try:
                ir_instructions = callgrind_ir(
                    bin_path,
                    run_cmd=input_cmd,
                    toggle_func=ir_roi_func,
                )
                if ir_instructions is None:
                    warnings.append("ir_missing")
                stage_writer(f"{c_path.name}: callgrind ok")
            except Exception as exc:
                warnings.append(f"ir_failed:{type(exc).__name__}")
                ir_instructions = None
                stage_writer(f"{c_path.name}: callgrind failed")
    elif show_stages:
        stage_writer(f"{c_path.name}: compile skipped")
        stage_writer(f"{c_path.name}: callgrind skipped")

    qasm_metrics: Dict[str, Optional[int]] = {key: None for key in qasm_metric_keys}
    qasm_dest: Optional[pathlib.Path] = None
    user_time_s: Optional[float] = None
    sys_time_s: Optional[float] = None
    cpu_time_s: Optional[float] = None
    max_rss_kb: Optional[int] = None

    if needs_pipeline:
        stage_writer(f"{c_path.name}: pipeline")
        pipeline_issue = False
        try:
            qasm_path, meta = run_toolchain_subprocess(c_path, bits=bits, max_iter=max_iter)
            pipeline_stderr = meta.get("stderr") if isinstance(meta.get("stderr"), str) else None

            if needs_user_time or needs_cpu_time:
                user_val = meta.get("user_time_s")
                user_time_s = float(user_val) if isinstance(user_val, (int, float)) else None
            if needs_sys_time or needs_cpu_time:
                sys_val = meta.get("sys_time_s")
                sys_time_s = float(sys_val) if isinstance(sys_val, (int, float)) else None
            if needs_cpu_time:
                cpu_val = meta.get("cpu_time_s")
                if isinstance(cpu_val, (int, float)):
                    cpu_time_s = float(cpu_val)
                elif user_time_s is not None and sys_time_s is not None:
                    cpu_time_s = user_time_s + sys_time_s
            if needs_rss:
                max_rss_kb = meta.get("max_rss_kb")  # type: ignore[assignment]

            if isinstance(meta.get("returncode"), int) and int(meta["returncode"]) != 0:
                errors.append("pipeline_failed")
                pipeline_issue = True

            if needs_qasm_metrics:
                if qasm_path:
                    qasm_src = pathlib.Path(qasm_path)
                    if qasm_src.exists():
                        qasm_dest = _copy_qasm(qasm_src, qasm_out_dir)
                        if qasm_dest and qasm_dest.exists():
                            qasm_counts = count_qasm_metrics(qasm_dest)
                            for key in required_qasm_keys:
                                qasm_metrics[key] = qasm_counts.get(key)
                        else:
                            errors.append("qasm_copy_failed")
                            pipeline_issue = True
                    else:
                        errors.append("qasm_missing")
                        pipeline_issue = True
                else:
                    errors.append("qasm_path_none")
                    pipeline_issue = True

            stage_writer(f"{c_path.name}: pipeline {'ok' if not pipeline_issue else 'issues'}")
        except Exception as exc:
            errors.append(f"pipeline_exc:{type(exc).__name__}")
            stage_writer(f"{c_path.name}: pipeline exception")
    elif show_stages:
        stage_writer(f"{c_path.name}: pipeline skipped")

    missing_required = False
    if needs_cyclomatic and cyclomatic is None:
        missing_required = True
    if needs_ir and ir_instructions is None:
        missing_required = True
    for key in required_qasm_keys:
        if qasm_metrics.get(key) is None:
            missing_required = True
            break
    if needs_user_time and user_time_s is None:
        missing_required = True
    if needs_sys_time and sys_time_s is None:
        missing_required = True
    if needs_cpu_time and cpu_time_s is None:
        missing_required = True
    if needs_rss and max_rss_kb is None:
        missing_required = True

    if errors:
        status = "error"
    elif missing_required:
        status = "partial"
    else:
        status = "ok"

    result: Dict[str, Union[str, int, float, None, List[str]]] = {
        "file": c_path.name,
        "status": status,
        "error": "; ".join(errors) if errors else None,
        "warnings": "; ".join(warnings) if warnings else None,
        "compile_stderr": compile_stderr,
        "pipeline_stderr": pipeline_stderr,
        "cyclomatic": cyclomatic if needs_cyclomatic else None,
        "ir_instructions": ir_instructions if needs_ir else None,
        "num_qubits": qasm_metrics.get("num_qubits") if metrics_enabled.get("num_qubits", True) else None,
        "num_gates": qasm_metrics.get("num_gates") if metrics_enabled.get("num_gates", True) else None,
        "num_cx": qasm_metrics.get("num_cx") if metrics_enabled.get("num_cx", True) else None,
        "num_measure": qasm_metrics.get("num_measure") if metrics_enabled.get("num_measure", True) else None,
        "num_u1": qasm_metrics.get("num_u1") if metrics_enabled.get("num_u1", True) else None,
        "num_u2": qasm_metrics.get("num_u2") if metrics_enabled.get("num_u2", True) else None,
        "num_u3": qasm_metrics.get("num_u3") if metrics_enabled.get("num_u3", True) else None,
        "depth": qasm_metrics.get("depth") if metrics_enabled.get("depth", True) else None,
        "user_time_s": user_time_s if needs_user_time else None,
        "sys_time_s": sys_time_s if needs_sys_time else None,
        "cpu_time_s": cpu_time_s if needs_cpu_time else None,
        "max_rss_kb": max_rss_kb if needs_rss else None,
        "qasm_path": str(qasm_dest) if qasm_dest else None,
        "ir_offset": None,
        "stage_messages": stage_writer.messages,
    }
    return result


def _sort_rows(rows: List[Dict[str, Union[str, int, float, None]]]) -> List[Dict[str, Union[str, int, float, None]]]:
    def _to_float(v: Union[str, int, float, None]) -> float:
        try:
            return float(v) if v is not None else float("inf")
        except Exception:
            return float("inf")

    def _to_int(v: Union[str, int, float, None]) -> int:
        try:
            if v is None:
                raise ValueError
            if isinstance(v, int):
                return v
            if isinstance(v, float):
                return int(v)
            return int(float(v))
        except Exception:
            return 10**18

    rows.sort(key=lambda r: (_to_float(r.get("cyclomatic")), _to_int(r.get("ir_instructions")), str(r.get("file") or "")))
    return rows


def run_study(
    study: str,
    *,
    bits: int,
    cc: str,
    arch: Optional[str],
    input_cmd: Optional[str],
    max_iter: int,
    progress: str,
    show_stages: bool,
    ir_roi_func: Optional[str] = None,
    max_workers: Optional[int] = None,
    metrics_enabled: Optional[Dict[str, bool]] = None,
    batch_size: Optional[int] = None,
    batch_pause_s: float = 0.0,
) -> pathlib.Path:
    ensure_pipeline_available()

    dataset_dir, results_dir, qasm_dir, bin_dir = resolve_study_dirs(study)
    c_files = sorted(dataset_dir.glob("*.c"))
    if not c_files:
        raise FileNotFoundError(f"No .c files found in {dataset_dir}")

    metrics_enabled = metrics_enabled or {}
    active_metrics = [column for column in METRIC_COLUMNS if metrics_enabled.get(column, True)]
    fieldnames = ["file", *active_metrics]

    out_csv = results_dir / f"{study}_metrics.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Union[str, int, float, None]]] = []
    existing_valid: set[str] = set()

    if out_csv.exists():
        try:
            with out_csv.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fn = row.get("file")
                    if not fn:
                        continue
                    entry: Dict[str, Union[str, int, float, None]] = {"file": fn}
                    missing = False
                    for field in active_metrics:
                        value = row.get(field)
                        if value is None or value == "":
                            entry[field] = None
                            missing = True
                            continue
                        try:
                            entry[field] = float(value)
                        except Exception:
                            entry[field] = None
                            missing = True
                    if not missing:
                        rows.append(entry)
                        existing_valid.add(fn)
        except Exception:
            rows = []
            existing_valid = set()
    else:
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

    progress_obj = _make_progress(len(c_files), progress, desc="Files")

    to_process: List[pathlib.Path] = []
    skipped_n = 0
    for c_path in c_files:
        if c_path.name in existing_valid:
            skipped_n += 1
            if progress != "none":
                message = f"[skip] {c_path.name} already present"
                if progress_obj is not None:
                    progress_obj.write(message)
                else:
                    print(message)
            if progress_obj is not None:
                progress_obj.update(1)
        else:
            to_process.append(c_path)

    ok_n = partial_n = err_n = 0

    worker_count = max(1, max_workers) if max_workers is not None else max(1, (os.cpu_count() or 2) - 1)
    t0 = time.perf_counter()

    effective_batch_size: Optional[int]
    if batch_size is None or batch_size <= 0:
        effective_batch_size = None
    else:
        effective_batch_size = batch_size

    def _finalise_rows() -> None:
        if "ir_offset" in active_metrics:
            baseline_map: Dict[str, int] = {}

            def _cc_key(val: Union[str, int, float, None]) -> Optional[str]:
                if val is None:
                    return None
                try:
                    return str(int(float(val)))
                except Exception:
                    return None

            def _ir_int(val: Union[str, int, float, None]) -> Optional[int]:
                if val is None:
                    return None
                try:
                    if isinstance(val, (int, float)):
                        return int(val)
                    return int(float(val))
                except Exception:
                    try:
                        return int(str(val))
                    except Exception:
                        return None

            for row in rows:
                cc_key = _cc_key(row.get("cyclomatic"))
                ir_val = _ir_int(row.get("ir_instructions"))
                if cc_key is None or ir_val is None:
                    continue
                current = baseline_map.get(cc_key)
                if current is None or ir_val < current:
                    baseline_map[cc_key] = ir_val

            for row in rows:
                cc_key = _cc_key(row.get("cyclomatic"))
                ir_val = _ir_int(row.get("ir_instructions"))
                if cc_key is None or ir_val is None:
                    row["ir_offset"] = ""
                    continue
                base = baseline_map.get(cc_key)
                row["ir_offset"] = float(ir_val - base) if base is not None else ""

        _sort_rows(rows)
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fieldnames})

    def _emit(message: str) -> None:
        if progress == "none":
            return
        if progress_obj is not None:
            progress_obj.write(message)
        else:
            print(message)

    def _process_batch(batch: List[pathlib.Path]) -> None:
        nonlocal ok_n, partial_n, err_n
        if not batch:
            return
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(
                    process_file,
                    c_path,
                    bits=bits,
                    cc=cc,
                    arch=arch,
                    input_cmd=input_cmd,
                    max_iter=max_iter,
                    ir_roi_func=ir_roi_func,
                    qasm_out_dir=qasm_dir,
                    bin_out_dir=bin_dir,
                    show_stages=show_stages,
                    metrics_enabled=metrics_enabled,
                ): c_path
                for c_path in batch
            }

            for future in concurrent.futures.as_completed(future_map):
                c_path = future_map[future]
                try:
                    res = future.result()
                except Exception as exc:
                    traceback.print_exc()
                    res = {
                        "file": c_path.name,
                        "status": "error",
                        "error": f"worker_exc:{type(exc).__name__}",
                        "stage_messages": [],
                    }

                stage_messages = res.pop("stage_messages", []) or []
                if show_stages:
                    for msg in stage_messages:
                        _emit(msg)

                status = str(res.get("status") or "error").lower()
                if status == "ok":
                    ok_n += 1
                    _emit(f"[ok] {c_path.name}")
                elif status == "partial":
                    partial_n += 1
                    _emit(f"[partial] {c_path.name}")
                else:
                    err_n += 1
                    msg = res.get("error") or ""
                    _emit(f"[err] {c_path.name} {msg}")
                    if show_stages:
                        comp = (res.get("compile_stderr") or "").strip()
                        pipe = (res.get("pipeline_stderr") or "").strip()
                        if comp:
                            _emit(f"--- {c_path.name}: compiler stderr ---")
                            for line in comp.splitlines():
                                _emit(line)
                        if pipe:
                            _emit(f"--- {c_path.name}: pipeline stderr ---")
                            for line in pipe.splitlines():
                                _emit(line)

                row_data: Dict[str, Union[str, int, float, None]] = {"file": res.get("file")}
                for field in active_metrics:
                    row_data[field] = res.get(field)
                rows.append(row_data)
                existing_valid.add(c_path.name)

                with out_csv.open("a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writerow({field: row_data.get(field, "") for field in fieldnames})

                if progress_obj is not None:
                    progress_obj.update(1)

    if to_process:
        index = 0
        batch_counter = 0
        total_to_process = len(to_process)
        should_announce_batches = (
            (effective_batch_size is not None and total_to_process > effective_batch_size)
            or batch_pause_s > 0
        )
        while index < total_to_process:
            if effective_batch_size is None:
                current_batch = to_process[index:]
            else:
                current_batch = to_process[index : index + effective_batch_size]
            batch_counter += 1
            if should_announce_batches:
                _emit(f"[batch] starting batch {batch_counter} ({len(current_batch)} files)")
            _process_batch(current_batch)
            index += len(current_batch)
            _finalise_rows()
            if index < total_to_process and batch_pause_s > 0:
                _emit(f"[batch] sleeping for {batch_pause_s:.1f}s before next batch")
                time.sleep(batch_pause_s)

    if progress_obj is not None:
        progress_obj.close()

    if not to_process:
        # Ensure offsets and ordering are refreshed even when nothing new ran.
        _finalise_rows()

    dt = time.perf_counter() - t0
    print(
        f"[done] Written: {out_csv} — {len(rows)} files in {dt:.2f}s (ok={ok_n}, partial={partial_n}, err={err_n}, skip={skipped_n})"
    )
    return out_csv

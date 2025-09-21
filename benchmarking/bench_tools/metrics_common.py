"""Common helpers shared by benchmarking tools.

This module centralises the logic to compute cyclomatic complexity via
``lizard`` and to compile/measure binaries with Callgrind so that both
``scan_cc_ir`` and the benchmarking runner can reuse it without keeping
copies in multiple places.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

__all__ = [
    "cyclomatic_lizard",
    "compile_c_for_valgrind",
    "callgrind_ir",
    "count_qasm_metrics",
]


def _run_lizard(args: List[str]) -> subprocess.CompletedProcess:
    """Invoke ``lizard`` with the provided argument list."""
    return subprocess.run(
        [sys.executable, "-m", "lizard", *args],
        capture_output=True,
        text=True,
    )


def cyclomatic_lizard(c_path: pathlib.Path) -> float:
    """Return the cumulative cyclomatic complexity for ``c_path``.

    The function prefers Lizard's JSON output (with and without the explicit
    ``-l c`` language hint) and falls back to a lightweight heuristic if Lizard
    is unavailable or fails.
    """
    # Attempt JSON output with explicit C language detection.
    res = _run_lizard(["-l", "c", "-j", str(c_path)])
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            funcs = data[0].get("functions", [])
            return float(sum(f.get("cyclomatic_complexity", 1) for f in funcs)) if funcs else 1.0
        except Exception:
            pass

    # Retry without forcing the language.
    res = _run_lizard(["-j", str(c_path)])
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            funcs = data[0].get("functions", [])
            return float(sum(f.get("cyclomatic_complexity", 1) for f in funcs)) if funcs else 1.0
        except Exception:
            pass

    # Last resort: simple regex-based heuristic.
    try:
        text = c_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 1.0
    tokens = [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b", r"&&", r"\|\|", r"\?"]
    cc = 1
    for pat in tokens:
        cc += len(re.findall(pat, text))
    return float(cc)


def compile_c_for_valgrind(
    c_path: pathlib.Path,
    out_bin: pathlib.Path,
    cc: str = "gcc",
    arch: Optional[str] = None,
) -> None:
    """Compile ``c_path`` into ``out_bin`` with debug info for Callgrind."""
    cmd = [cc, "-O0", "-g", str(c_path), "-o", str(out_bin)]
    if arch:
        arch_l = arch.lower()
        if arch_l == "arm":
            cmd.insert(1, "-march=armv7-a")
        elif arch_l in {"x86", "i686"}:
            cmd.insert(1, "-march=i686")
        elif arch_l in {"x86-64", "x86_64", "amd64"}:
            cmd.insert(1, "-march=x86-64")
    subprocess.run(cmd, check=True)


def callgrind_ir(
    bin_path: pathlib.Path,
    run_cmd: Optional[str] = None,
    instr_atstart_no: bool = False,
    toggle_func: Optional[str] = None,
) -> Optional[int]:
    """Return the Ir counter measured by Callgrind for ``bin_path``.

    When Callgrind (or ``valgrind``) is unavailable the function returns
    ``None`` so callers can decide how to handle the missing metric.
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

        cmd = [
            "valgrind",
            "--tool=callgrind",
            f"--callgrind-out-file={str(cg_out)}",
            str(tmp_bin),
        ]
        if toggle_func:
            cmd.insert(2, f"--toggle-collect={toggle_func}")
            cmd.insert(2, "--collect-atstart=no")
        elif instr_atstart_no:
            cmd.insert(2, "--instr-atstart=no")

        subprocess.run(
            cmd,
            input=run_cmd if run_cmd is not None else None,
            text=True,
            capture_output=True,
            env=env,
        )
        if not cg_out.exists():
            return None

        if has_annot:
            ann = subprocess.run(
                ["callgrind_annotate", str(cg_out)],
                capture_output=True,
                text=True,
                env=env,
            )
            if ann.returncode == 0:
                match = re.search(r"\bIr\s*:\s*([\d,\.]+)", ann.stdout)
                if match:
                    return int(match.group(1).replace(",", "").replace(".", ""))

        try:
            raw = cg_out.read_text()
        except Exception:
            return None

        events = re.search(r"^events:\s*(.+)$", raw, re.MULTILINE)
        if not events:
            return None
        tokens = events.group(1).strip().split()
        try:
            ir_idx = tokens.index("Ir")
        except ValueError:
            return None
        summary = re.search(r"^summary:\s*([^\n]+)$", raw, re.MULTILINE)
        if not summary:
            return None
        numbers = re.split(r"\s+", summary.group(1).strip())

        def _clean(value: str) -> str:
            return re.sub(r"[,_\.]", "", value)

        if ir_idx < len(numbers):
            return int(_clean(numbers[ir_idx]))
        if len(numbers) == 1 and ir_idx == 0:
            return int(_clean(numbers[0]))
        return None


def _is_comment_or_header(line: str) -> bool:
    return (
        (not line)
        or line.startswith("//")
        or line.startswith("OPENQASM")
        or line.startswith("include")
        or line.startswith("qreg")
        or line.startswith("creg")
    )


_QREG_RE = re.compile(r"qreg\s+\w+\[(\d+)\];")
_CX_RE = re.compile(r"^\s*cx\s", re.MULTILINE)
_MEASURE_RE = re.compile(r"^\s*measure\s", re.MULTILINE)
_U1_RE = re.compile(r"^\s*u1\(", re.MULTILINE)
_U2_RE = re.compile(r"^\s*u2\(", re.MULTILINE)
_U3_RE = re.compile(r"^\s*u3\(", re.MULTILINE)
_QBIT_TOK_RE = re.compile(r"([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]")


def _compute_qasm_depth(qasm_text: str) -> int:
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
    """Compute simple gate counts and depth from a QASM file."""
    text = qasm_path.read_text(encoding="utf-8", errors="ignore")
    qubits = sum(int(m.group(1)) for m in _QREG_RE.finditer(text))
    total = 0
    for raw in text.splitlines():
        s = raw.strip()
        if _is_comment_or_header(s) or s.startswith("barrier"):
            continue
        if s:
            total += 1
    depth = _compute_qasm_depth(text)
    return dict(
        num_qubits=qubits,
        num_gates=total,
        num_cx=len(_CX_RE.findall(text)),
        num_measure=len(_MEASURE_RE.findall(text)),
        num_u1=len(_U1_RE.findall(text)),
        num_u2=len(_U2_RE.findall(text)),
        num_u3=len(_U3_RE.findall(text)),
        depth=depth,
    )

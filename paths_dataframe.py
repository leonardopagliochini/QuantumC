"""Utilities for building a DataFrame visualizing register paths."""

from __future__ import annotations

from typing import Dict, Set
import pandas as pd
from xdsl.ir import Operation
from xdsl.dialects.builtin import ModuleOp
from quantum_dialect import (
    QuantumInitOp,
    QAddiOp,
    QSubiOp,
    QMuliOp,
    QDivSOp,
    QAddiImmOp,
    QSubiImmOp,
    QMuliImmOp,
    QDivSImmOp,
)


_OP_SYMBOL = {
    QAddiOp: "+",
    QSubiOp: "-",
    QMuliOp: "*",
    QDivSOp: "/",
    QAddiImmOp: "+",
    QSubiImmOp: "-",
    QMuliImmOp: "*",
    QDivSImmOp: "/",
}


def build_paths_dataframe(module: ModuleOp) -> pd.DataFrame:
    """Return a DataFrame mapping register paths to operation expressions."""
    func = next(iter(module.ops))
    block = func.body.blocks[0]
    ops = list(block.ops)

    # Discover all register ids and paths present in the block
    reg_paths: Dict[int, Set[int]] = {}
    for op in ops:
        rid_attr = op.properties.get("reg_id")
        rpath_attr = op.properties.get("reg_path")
        if rid_attr is None or rpath_attr is None:
            continue
        rid = int(rid_attr.data)
        path = int(rpath_attr.value.data)
        reg_paths.setdefault(rid, set()).add(path)

    columns = [
        f"r{rid}_p{path}"
        for rid in sorted(reg_paths)
        for path in sorted(reg_paths[rid])
    ]
    # Extra column describing the operation performed at each timestep.
    columns.append("operation")
    df = pd.DataFrame("", index=range(len(ops)), columns=columns)

    # Map SSAValue -> name like "%0", "%1", ...
    value_names: Dict[object, str] = {}
    counter = 0
    for op in ops:
        for res in op.results:
            value_names[res] = f"%{counter}"
            counter += 1

    for step, op in enumerate(ops):
        out = value_names.get(op.results[0]) if op.results else ""
        expr = ""

        if isinstance(op, QuantumInitOp):
            expr = f"{out} = {int(op.value.value.data)}"
        elif type(op) in _OP_SYMBOL:
            sym = _OP_SYMBOL[type(op)]
            lhs = value_names.get(op.operands[0], "")
            if isinstance(op, (QAddiImmOp, QSubiImmOp, QMuliImmOp, QDivSImmOp)):
                rhs = str(int(op.imm.value.data))
            else:
                rhs = value_names.get(op.operands[1], "")
            expr = f"{out} = {lhs} {sym} {rhs}"

        # Record the expression in the new 'operation' column
        if expr:
            df.loc[step, "operation"] = expr

        rid_attr = op.properties.get("reg_id")
        rpath_attr = op.properties.get("reg_path")
        if rid_attr is None or rpath_attr is None or not expr:
            continue

        rid = int(rid_attr.data)
        path = int(rpath_attr.value.data)
        col = f"r{rid}_p{path}"

        df.loc[step, col] = expr

    return df

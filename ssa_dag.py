# Utilities to build and rewrite an SSA DAG of quantum operations

from __future__ import annotations

from typing import Dict, Tuple, List

import networkx as nx
from xdsl.ir import Operation, Block, Region
from xdsl.dialects.builtin import ModuleOp
from xdsl.dialects.func import FuncOp, ReturnOp

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


def _get_attr_int(op: Operation, name: str) -> int | None:
    attr = op.properties.get(name)
    if attr is None:
        return None
    return int(getattr(attr, "value", attr).data)


# -----------------------------------------------------------------------------
# DAG Construction and Visualization
# -----------------------------------------------------------------------------

def build_dag(module: ModuleOp) -> nx.DiGraph:
    """Return a NetworkX DAG representing operation dependencies."""
    g = nx.DiGraph()
    func = next(iter(module.ops))
    ops = list(func.body.blocks[0].ops)

    # Assign SSA names deterministically like %0, %1, ...
    value_names: Dict[object, str] = {}
    counter = 0
    for op in ops:
        for res in op.results:
            value_names[res] = f"%{counter}"
            counter += 1

    for idx, op in enumerate(ops):
        out = value_names.get(op.results[0]) if op.results else f"%{idx}"
        label = ""
        if isinstance(op, QuantumInitOp):
            label = f"{out} = {int(op.value.value.data)}"
        elif type(op) in _OP_SYMBOL:
            sym = _OP_SYMBOL[type(op)]
            lhs = value_names.get(op.operands[0], "")
            if isinstance(op, (QAddiImmOp, QSubiImmOp, QMuliImmOp, QDivSImmOp)):
                rhs = str(int(op.imm.value.data))
            else:
                rhs = value_names.get(op.operands[1], "")
            label = f"{out} = {lhs} {sym} {rhs}"
        elif isinstance(op, ReturnOp):
            arg = value_names.get(op.operands[0], "") if op.operands else ""
            label = f"return {arg}"
        else:
            label = op.name

        node_name = str(idx)
        g.add_node(node_name, label=label, index=idx)
        for operand in op.operands:
            if operand.owner is not None:
                src = str(ops.index(operand.owner))
                g.add_edge(src, node_name)

    return g


def visualize_dag(g: nx.DiGraph, path: str) -> None:
    """Plot ``g`` to the given file path using GraphViz layout."""
    import matplotlib.pyplot as plt
    from networkx.drawing.nx_agraph import graphviz_layout

    pos = graphviz_layout(g, prog="dot")
    labels = nx.get_node_attributes(g, "label")
    plt.figure(figsize=(12, 6))
    nx.draw_networkx_nodes(g, pos, node_size=1500, node_color="lightblue")
    nx.draw_networkx_edges(
        g,
        pos,
        arrows=True,
        arrowsize=20,
        arrowstyle="->",
        connectionstyle="arc3,rad=0.1",
    )
    nx.draw_networkx_labels(
        g,
        pos,
        labels=labels,
        font_size=8,
        bbox=dict(facecolor="white", edgecolor="none", pad=0.3),
    )
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

def save_dag_dot(g: nx.DiGraph, path: str) -> None:
    """Write ``g`` to ``path`` in GraphViz DOT format."""
    from networkx.drawing.nx_agraph import write_dot

    write_dot(g, path)

# -----------------------------------------------------------------------------
# Quantum Constraint Enforcement
# -----------------------------------------------------------------------------



def _compute_next_overwrite(ops: List[Operation]) -> Dict[Tuple[int, int], int]:
    per_reg: Dict[int, List[Tuple[int, int]]] = {}
    for idx, op in enumerate(ops):
        rid = _get_attr_int(op, "reg_id")
        ver = _get_attr_int(op, "reg_version")
        if rid is None or ver is None:
            continue
        per_reg.setdefault(rid, []).append((idx, ver))

    next_ow: Dict[Tuple[int, int], int] = {}
    for rid, lst in per_reg.items():
        for i, (idx, ver) in enumerate(lst):
            nxt = lst[i + 1][0] if i + 1 < len(lst) else int(1e9)
            next_ow[(rid, ver)] = nxt
    return next_ow


def _create_like(
    op: Operation, operands: List[Operation | None], new_rid: int | None = None
) -> Operation:
    rid = _get_attr_int(op, "reg_id") if new_rid is None else new_rid
    ver = _get_attr_int(op, "reg_version")
    comment = op.attributes.get("c_comment")

    if isinstance(op, QuantumInitOp):
        new_op = QuantumInitOp(int(op.value.value.data), str(rid), ver, 0)
    elif isinstance(op, (QAddiOp, QSubiOp, QMuliOp, QDivSOp)):
        new_op = type(op)(operands[0].results[0], operands[1].results[0], str(rid), ver, 0)
    elif isinstance(op, (QAddiImmOp, QSubiImmOp, QMuliImmOp, QDivSImmOp)):
        imm = int(op.imm.value.data)
        new_op = type(op)(operands[0].results[0], imm, str(rid), ver, 0)
    elif isinstance(op, ReturnOp):
        if operands:
            new_op = ReturnOp(operands[0].results[0])
        else:
            new_op = ReturnOp()
    else:
        raise NotImplementedError(op.name)

    if comment is not None:
        new_op.attributes["c_comment"] = comment
    return new_op


def enforce_constraints(module: ModuleOp) -> ModuleOp:
    """Return a new module with quantum constraints enforced."""
    func = next(iter(module.ops))
    orig_ops = list(func.body.blocks[0].ops)

    next_overwrite = _compute_next_overwrite(orig_ops)
    existing_ids = [i for i in (_get_attr_int(op, "reg_id") for op in orig_ops) if i is not None]
    next_reg = max(existing_ids, default=-1) + 1

    def alloc_reg() -> int:
        nonlocal next_reg
        r = next_reg
        next_reg += 1
        return r

    new_block = Block()
    new_ops_map: Dict[Operation, Operation] = {}

    def clone_rec(op: Operation) -> Operation:
        operands = [clone_rec(o.owner) for o in op.operands]
        rid = _get_attr_int(op, "reg_id")
        ver = _get_attr_int(op, "reg_version")
        new_rid = alloc_reg() if rid is not None else None
        new_op = _create_like(op, operands, new_rid)
        new_block.add_op(new_op)
        return new_op

    for idx, op in enumerate(orig_ops):
        operands: List[Operation] = []
        orig_inputs = [o.owner for o in op.operands]
        for inp in orig_inputs:
            if inp is None:
                continue
            rid = _get_attr_int(inp, "reg_id")
            ver = _get_attr_int(inp, "reg_version")
            if rid is not None and ver is not None and idx >= next_overwrite.get((rid, ver), int(1e9)):
                operands.append(clone_rec(inp))
            else:
                operands.append(new_ops_map[inp])

        # Constraint 2: same register on both operands
        if len(operands) == 2:
            r0 = _get_attr_int(orig_inputs[0], "reg_id")
            v0 = _get_attr_int(orig_inputs[0], "reg_version")
            r1 = _get_attr_int(orig_inputs[1], "reg_id")
            v1 = _get_attr_int(orig_inputs[1], "reg_version")
            if r0 is not None and r1 is not None and v0 is not None and v1 is not None:
                if r0 == r1 and v0 == v1:
                    operands[1] = clone_rec(orig_inputs[1])

        rid = _get_attr_int(op, "reg_id")
        new_op = _create_like(op, operands, rid)
        new_block.add_op(new_op)
        new_ops_map[op] = new_op

    new_func = FuncOp(func.sym_name.data, func.function_type, Region([new_block]))
    return ModuleOp([new_func])

"""Construct a dependency DAG from MLIR operations."""

from __future__ import annotations

from typing import Dict

from xdsl.ir import Operation, SSAValue
from xdsl.dialects.builtin import ModuleOp

import networkx as nx
from graphviz import Digraph


class IRDependencyDAG:
    """Build a DAG capturing SSA dependencies between operations."""

    def __init__(self, module: ModuleOp) -> None:
        self.module = module
        self.graph = nx.MultiDiGraph()
        self.node_labels: Dict[str, str] = {}
        self.node_ops: Dict[str, Operation] = {}
        self.node_results: Dict[str, list[SSAValue]] = {}
        self.value_names: Dict[SSAValue, str] = {}

    def _format_op(self, op: Operation, names: Dict[SSAValue, str]) -> str:
        """Return a textual representation of ``op`` using SSA names."""
        res_names = [names[r] for r in op.results]
        prefix = ", ".join(res_names)
        if prefix:
            prefix += " = "

        def name(val: SSAValue) -> str:
            return names.get(val, str(val))

        op_map = {
            "arith.addi": "+",
            "arith.subi": "-",
            "arith.muli": "*",
            "arith.divsi": "/",
            "iarith.addi_imm": "+",
            "iarith.subi_imm": "-",
            "iarith.muli_imm": "*",
            "iarith.divsi_imm": "/",
        }

        if op.name == "arith.constant":
            return f"{prefix}constant {op.value}"
        if op.name in op_map and len(op.operands) == 2:
            lhs, rhs = op.operands
            sym = op_map[op.name]
            return f"{prefix}{name(lhs)} {sym} {name(rhs)}"
        if op.name in {
            "iarith.addi_imm",
            "iarith.subi_imm",
            "iarith.muli_imm",
            "iarith.divsi_imm",
        }:
            lhs = op.operands[0]
            sym = op_map[op.name]
            imm = op.imm.value.data
            return f"{prefix}{name(lhs)} {sym} {imm}"
        if op.name == "func.return":
            if op.operands:
                return f"{prefix}return {name(op.operands[0])}"
            return f"{prefix}return"
        return prefix + op.name

    # ------------------------------------------------------------------
    def build(self) -> None:
        """Populate ``self.graph`` with dependency edges."""
        value_to_node: Dict[SSAValue, str] = {}
        value_names: Dict[SSAValue, str] = {}
        name_counter = 0
        ops: list[Operation] = [
            op
            for op in self.module.walk()
            if op.name not in {"builtin.module", "func.func"}
        ]

        for op in ops:
            for res in op.results:
                value_names[res] = f"%{name_counter}"
                name_counter += 1

        self.value_names = value_names

        # Create nodes and map results to their defining node.
        for idx, op in enumerate(ops):
            node_id = f"op{idx}"
            label = self._format_op(op, value_names)
            comment = op.attributes.get("c_comment")
            if comment:
                label += "\n" + str(comment)
            self.graph.add_node(node_id)
            self.node_labels[node_id] = label
            self.node_ops[node_id] = op
            self.node_results[node_id] = list(op.results)
            for res in op.results:
                value_to_node[res] = node_id

        # Add edges based on operand producers.
        for idx, op in enumerate(ops):
            node_id = f"op{idx}"
            for operand in op.operands:
                src = value_to_node.get(operand)
                if src is not None:
                    self.graph.add_edge(src, node_id)

    # ------------------------------------------------------------------
    def export(self, prefix: str) -> None:
        """Write the DAG to ``prefix`` in PNG and XDOT formats."""
        dot = Digraph()
        for node, label in self.node_labels.items():
            dot.node(node, label)
        for src, dst, _ in self.graph.edges(keys=True):
            dot.edge(src, dst)

        dot.format = "png"
        dot.render(prefix, cleanup=True)
        dot.format = "xdot"
        dot.render(prefix, cleanup=False)

    # ------------------------------------------------------------------
    def duplicate_double_consumes(self) -> 'IRDependencyDAG':
        """Return a DAG where duplicated operands are produced by cloned nodes."""

        new = IRDependencyDAG(self.module)
        new.graph = self.graph.copy()
        new.node_labels = dict(self.node_labels)
        new.node_ops = dict(self.node_ops)
        new.node_results = dict(self.node_results)
        new.value_names = dict(self.value_names)

        processed: set[tuple[str, str]] = set()
        immediate_ops = {
            "iarith.addi_imm",
            "iarith.subi_imm",
            "iarith.muli_imm",
            "iarith.divsi_imm",
        }

        for src, dst in list(self.graph.edges()):
            if (src, dst) in processed:
                continue
            processed.add((src, dst))
            count = self.graph.number_of_edges(src, dst)
            if count <= 1:
                continue
            consumer = self.node_ops.get(dst)
            if consumer is None or consumer.name in immediate_ops:
                continue

            # Only handle the first two edges
            preds = list(self.graph.predecessors(src))
            result_names = self.node_results.get(src, [])
            if not result_names:
                continue
            res = result_names[0]
            res_name = self.value_names.get(res, "")
            suffixes = ["'", '"']
            for i, suf in enumerate(suffixes):
                dup = f"{src}_dup{i}"
                label_parts = new.node_labels[src].split("=", 1)
                if len(label_parts) == 2:
                    label_tail = label_parts[1]
                    new.node_labels[dup] = f"{res_name}{suf} =" + label_tail
                else:
                    new.node_labels[dup] = new.node_labels[src] + suf
                new.node_ops[dup] = self.node_ops[src]
                new.node_results[dup] = self.node_results[src]
                new.graph.add_node(dup)
                for p in preds:
                    for _ in range(self.graph.number_of_edges(p, src)):
                        new.graph.add_edge(p, dup)

            # remove original edges and connect duplicates to dst
            new.graph.remove_edges_from([(src, dst)] * count)
            new.graph.add_edge(f"{src}_dup0", dst)
            new.graph.add_edge(f"{src}_dup1", dst)

        return new

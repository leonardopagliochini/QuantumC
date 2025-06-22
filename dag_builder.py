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
        self.graph = nx.DiGraph()
        self.node_labels: Dict[str, str] = {}

    # ------------------------------------------------------------------
    def build(self) -> None:
        """Populate ``self.graph`` with dependency edges."""
        value_to_node: Dict[SSAValue, str] = {}
        ops: list[Operation] = [
            op
            for op in self.module.walk()
            if op.name not in {"builtin.module", "func.func"}
        ]

        # Create nodes and map results to their defining node.
        for idx, op in enumerate(ops):
            node_id = f"op{idx}"
            label = op.name
            comment = op.attributes.get("c_comment")
            if comment:
                label += "\n" + str(comment)
            self.graph.add_node(node_id)
            self.node_labels[node_id] = label
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
        for src, dst in self.graph.edges():
            dot.edge(src, dst)

        dot.format = "png"
        dot.render(prefix, cleanup=True)
        dot.format = "xdot"
        dot.render(prefix, cleanup=False)

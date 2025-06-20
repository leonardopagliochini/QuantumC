"""Simplistic translator from classical MLIR to the quantum dialect.

This new version drops all the register bookkeeping logic that tried to
avoid value duplication and enforce reversibility.  The translator now
performs a straightforward one-to-one mapping from classical arithmetic
operations to their quantum counterparts defined in ``quantum_dialect``.
"""

from __future__ import annotations

from typing import Dict

from xdsl.dialects.builtin import ModuleOp, i32
from xdsl.dialects.func import FuncOp, ReturnOp
from xdsl.dialects.arith import ConstantOp, AddiOp, SubiOp, MuliOp, DivSIOp
from xdsl.ir import Block, Region, SSAValue

from dialect_ops import AddiImmOp, SubiImmOp, MuliImmOp, DivSImmOp
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


class QuantumTranslator:
    """Convert classical arithmetic MLIR ops to the quantum dialect."""

    def __init__(self, module: ModuleOp) -> None:
        self.module = module
        self.q_module: ModuleOp | None = None

    # ------------------------------------------------------------------
    def translate(self) -> ModuleOp:
        """Translate ``self.module`` into a new module using quantum ops."""
        self.q_module = ModuleOp([])
        for func in self.module.ops:
            q_func = self.translate_func(func)
            self.q_module.body.blocks[0].add_op(q_func)
        return self.q_module

    # ------------------------------------------------------------------
    def translate_func(self, func: FuncOp) -> FuncOp:
        """Translate a single function."""
        block = func.body.blocks[0]
        q_block = Block()
        value_map: Dict[SSAValue, SSAValue] = {}

        for op in block.ops:
            if isinstance(op, ConstantOp):
                q_op = QuantumInitOp(op.value.value.data)
                q_block.add_op(q_op)
                value_map[op.results[0]] = q_op.results[0]

            elif isinstance(op, (AddiOp, SubiOp, MuliOp, DivSIOp)):
                lhs = value_map[op.operands[0]]
                rhs = value_map[op.operands[1]]
                q_cls = {
                    AddiOp: QAddiOp,
                    SubiOp: QSubiOp,
                    MuliOp: QMuliOp,
                    DivSIOp: QDivSOp,
                }[type(op)]
                q_op = q_cls(lhs, rhs)
                q_block.add_op(q_op)
                value_map[op.results[0]] = q_op.results[0]

            elif isinstance(op, (AddiImmOp, SubiImmOp, MuliImmOp, DivSImmOp)):
                lhs = value_map[op.operands[0]]
                imm = int(op.imm.value.data)
                q_cls = {
                    AddiImmOp: QAddiImmOp,
                    SubiImmOp: QSubiImmOp,
                    MuliImmOp: QMuliImmOp,
                    DivSImmOp: QDivSImmOp,
                }[type(op)]
                q_op = q_cls(lhs, imm)
                q_block.add_op(q_op)
                value_map[op.results[0]] = q_op.results[0]

            elif isinstance(op, ReturnOp):
                if op.operands:
                    ret_val = value_map[op.operands[0]]
                    q_op = ReturnOp(ret_val)
                else:
                    q_op = ReturnOp([])
                q_block.add_op(q_op)

            else:
                raise NotImplementedError(f"Unsupported op {op.name}")

        func_type = ([i32] * len(func.function_type.inputs.data), [i32])
        return FuncOp(func.sym_name.data, func_type, Region([q_block]))

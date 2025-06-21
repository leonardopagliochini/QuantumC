"""Translate classical MLIR modules into the custom quantum dialect."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from xdsl.dialects.builtin import ModuleOp, i32
from xdsl.dialects.func import FuncOp, ReturnOp
from xdsl.dialects.arith import ConstantOp, AddiOp, SubiOp, MuliOp, DivSIOp
from xdsl.ir import Block, Region, SSAValue, Operation

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


@dataclass
class ValueInfo:
    """Track the register and version representing a classical SSA value."""

    reg: int
    version: int
    qvalue: SSAValue


class QuantumTranslator:
    """Translate standard MLIR to the custom quantum dialect."""

    def __init__(self, module: ModuleOp) -> None:
        """Store the input module and initialize translation state."""
        # MLIR module produced by ``mlir_generator``
        self.module = module
        # Resulting module written in the quantum dialect
        self.q_module: ModuleOp | None = None

        # Counter used to allocate new registers as integers
        self.next_reg = 0
        # Map register id -> latest version used so far
        self.reg_version: Dict[int, int] = {}

        # Map each classical SSA value to the register/value tracking info
        self.val_info: Dict[SSAValue, ValueInfo] = {}

        # Remaining number of uses for each SSA value
        self.use_count: Dict[SSAValue, int] = {}

    # ------------------------------------------------------------------
    def translate(self) -> ModuleOp:
        """Convert the entire module to the quantum dialect."""
        # Compute how many times each SSA value is used.  This information
        # guides register allocation below.
        self.compute_use_counts()
        # Create an empty module that will hold the translated functions.
        self.q_module = ModuleOp([])
        # Translate each function separately.
        for func in self.module.ops:
            q_func = self.translate_func(func)
            self.q_module.body.blocks[0].add_op(q_func)
        return self.q_module

    # ------------------------------------------------------------------
    def compute_use_counts(self) -> None:
        """Record how many uses each SSA value has in the input module."""
        for func in self.module.ops:
            block = func.body.blocks[0]
            # Every result value can be referenced multiple times downstream.
            for op in block.ops:
                for res in op.results:
                    self.use_count[res] = len(res.uses)

    # ------------------------------------------------------------------
    def allocate_reg(self) -> int:
        """Allocate a fresh register identifier."""
        r = self.next_reg
        self.next_reg += 1
        # Newly created register starts at version 0.
        self.reg_version[r] = 0
        return r

    # ------------------------------------------------------------------
    def translate_func(self, func: FuncOp) -> FuncOp:
        """Translate a single function to the quantum dialect."""
        # Retrieve the function body to examine its operations.
        block = func.body.blocks[0]
        # New block that will contain the converted operations.
        self.current_block = Block()

        # Track remaining uses so we know when a register can be overwritten.
        remaining = dict(self.use_count)

        # Iterate over operations in the original block in order.
        for op in block.ops:
            if isinstance(op, ConstantOp):
                reg = self.allocate_reg()
                q_op = QuantumInitOp(op.value.value.data, str(reg), 0)
                self.current_block.add_op(q_op)
                self.val_info[op.results[0]] = ValueInfo(reg, 0, q_op.results[0])

            elif isinstance(op, (AddiOp, SubiOp, MuliOp, DivSIOp)):
                lhs, rhs = op.operands
                remaining[lhs] -= 1
                remaining[rhs] -= 1

                lhs_info = self.val_info[lhs]
                rhs_info = self.val_info[rhs]
                q_lhs = lhs_info.qvalue
                q_rhs = rhs_info.qvalue

                opcode = {
                    AddiOp: "add",
                    SubiOp: "sub",
                    MuliOp: "mul",
                    DivSIOp: "div",
                }[type(op)]

                commutative = opcode in {"add", "mul"}
                target_reg = None
                first = q_lhs
                second = q_rhs

                if commutative:
                    if remaining[lhs] == 0:
                        target_reg = lhs_info.reg
                    elif remaining[rhs] == 0:
                        target_reg = rhs_info.reg
                        first, second = q_rhs, q_lhs
                else:
                    if remaining[lhs] == 0:
                        target_reg = lhs_info.reg

                if target_reg is None:
                    target_reg = self.allocate_reg()
                    version = 0
                else:
                    version = self.reg_version[target_reg] + 1

                q_op = self.create_binary_op(opcode, first, second, target_reg, version)
                self.current_block.add_op(q_op)
                self.reg_version[target_reg] = version
                self.val_info[op.results[0]] = ValueInfo(target_reg, version, q_op.results[0])

            elif op.name in (
                "iarith.addi_imm",
                "iarith.subi_imm",
                "iarith.muli_imm",
                "iarith.divsi_imm",
            ):
                (lhs,) = op.operands
                remaining[lhs] -= 1
                imm = int(op.imm.value.data)

                lhs_info = self.val_info[lhs]
                q_lhs = lhs_info.qvalue

                opcode = {
                    "iarith.addi_imm": "add",
                    "iarith.subi_imm": "sub",
                    "iarith.muli_imm": "mul",
                    "iarith.divsi_imm": "div",
                }[op.name]

                if remaining[lhs] == 0:
                    target_reg = lhs_info.reg
                    version = self.reg_version[target_reg] + 1
                else:
                    target_reg = self.allocate_reg()
                    version = 0

                q_op = self.create_binary_imm_op(opcode, q_lhs, imm, target_reg, version)
                self.current_block.add_op(q_op)
                self.reg_version[target_reg] = version
                self.val_info[op.results[0]] = ValueInfo(target_reg, version, q_op.results[0])

            elif isinstance(op, ReturnOp):
                if op.operands:
                    info = self.val_info[op.operands[0]]
                    ret = ReturnOp(info.qvalue)
                else:
                    ret = ReturnOp([])
                self.current_block.add_op(ret)

            else:
                raise NotImplementedError(f"Unsupported op {op.name}")

        func_type = ([i32] * len(func.function_type.inputs.data), [i32])
        return FuncOp(func.sym_name.data, func_type, Region([self.current_block]))

    # ------------------------------------------------------------------
    def create_binary_op(self, opcode: str, lhs: SSAValue, rhs: SSAValue, reg: int, version: int) -> Operation:
        """Helper building the correct binary quantum op."""
        if opcode == "add":
            return QAddiOp(lhs, rhs, str(reg), version)
        if opcode == "sub":
            return QSubiOp(lhs, rhs, str(reg), version)
        if opcode == "mul":
            return QMuliOp(lhs, rhs, str(reg), version)
        if opcode == "div":
            return QDivSOp(lhs, rhs, str(reg), version)
        raise NotImplementedError(opcode)

    def create_binary_imm_op(self, opcode: str, lhs: SSAValue, imm: int, reg: int, version: int) -> Operation:
        """Helper for binary operations with a constant immediate operand."""
        if opcode == "add":
            return QAddiImmOp(lhs, imm, str(reg), version)
        if opcode == "sub":
            return QSubiImmOp(lhs, imm, str(reg), version)
        if opcode == "mul":
            return QMuliImmOp(lhs, imm, str(reg), version)
        if opcode == "div":
            return QDivSImmOp(lhs, imm, str(reg), version)
        raise NotImplementedError(opcode)

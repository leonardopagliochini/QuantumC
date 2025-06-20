from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Any
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
    reg: int
    version: int
    expr: Any

class QuantumTranslator:
    """Translate standard MLIR to quantum-friendly dialect."""

    def __init__(self, module: ModuleOp):
        self.module = module
        self.q_module: ModuleOp | None = None
        self.next_reg = 0
        self.val_info: Dict[SSAValue, ValueInfo] = {}
        self.reg_version: Dict[int, int] = {}
        self.reg_ssa: Dict[int, SSAValue] = {}
        self.use_count: Dict[SSAValue, int] = {}
        self.cost_cache: Dict[SSAValue, int] = {}

    # ------------------------------------------------------------------
    def translate(self) -> ModuleOp:
        self.compute_use_counts()
        self.q_module = ModuleOp([])
        for func in self.module.ops:
            q_func = self.translate_func(func)
            self.q_module.body.blocks[0].add_op(q_func)
        return self.q_module

    # ------------------------------------------------------------------
    def compute_use_counts(self):
        for func in self.module.ops:
            block = func.body.blocks[0]
            for op in block.ops:
                for res in op.results:
                    self.use_count[res] = len(res.uses)

    # ------------------------------------------------------------------
    def compute_cost(self, val: SSAValue) -> int:
        if val in self.cost_cache:
            return self.cost_cache[val]
        op = val.owner
        if isinstance(op, ConstantOp):
            cost = 1
        elif isinstance(op, (AddiOp, SubiOp, MuliOp, DivSIOp)):
            cost = 1 + self.compute_cost(op.operands[0]) + self.compute_cost(op.operands[1])
        elif op.name in (
            "mydialect.addi_imm",
            "mydialect.subi_imm",
            "mydialect.muli_imm",
            "mydialect.divsi_imm",
        ):
            cost = 1 + self.compute_cost(op.operands[0])
        else:
            cost = 1
        self.cost_cache[val] = cost
        return cost

    # ------------------------------------------------------------------
    def remaining_uses(self, val: SSAValue) -> int:
        return self.use_count.get(val, 0)

    # ------------------------------------------------------------------
    def allocate_reg(self) -> int:
        r = self.next_reg
        self.next_reg += 1
        self.reg_version[r] = 0
        return r

    # ------------------------------------------------------------------
    def emit_value(self, val: SSAValue) -> SSAValue:
        info = self.val_info[val]
        reg = info.reg
        if self.reg_version[reg] != info.version:
            self.recompute(val)
        return self.reg_ssa[reg]

    # ------------------------------------------------------------------
    def recompute(self, val: SSAValue):
        info = self.val_info[val]
        expr = info.expr
        if expr[0] == "const":
            value = expr[1]
            reg = info.reg
            version = self.reg_version[reg] + 1
            op = QuantumInitOp(value)
            self.current_block.add_op(op)
            op.results[0].name_hint = f"q{reg}_{version}"
            self.reg_version[reg] = version
            self.reg_ssa[reg] = op.results[0]
            info.version = version
        elif expr[0] == "binary":
            opcode, lhs, rhs, target = expr[1]
            q_lhs = self.emit_value(lhs)
            q_rhs = self.emit_value(rhs)
            if target is rhs:
                first = q_rhs
                second = q_lhs
                reg = self.val_info[rhs].reg
            else:
                first = q_lhs
                second = q_rhs
                reg = self.val_info[lhs].reg
            op = self.create_binary_op(opcode, first, second)
            self.current_block.add_op(op)
            version = self.reg_version[reg] + 1
            op.results[0].name_hint = f"q{reg}_{version}"
            self.reg_version[reg] = version
            self.reg_ssa[reg] = op.results[0]
            info.version = version
        elif expr[0] == "binaryimm":
            opcode, lhs, imm = expr[1]
            q_lhs = self.emit_value(lhs)
            reg = self.val_info[lhs].reg
            op = self.create_binary_imm_op(opcode, q_lhs, imm)
            self.current_block.add_op(op)
            version = self.reg_version[reg] + 1
            op.results[0].name_hint = f"q{reg}_{version}"
            self.reg_version[reg] = version
            self.reg_ssa[reg] = op.results[0]
            info.version = version
        else:
            raise NotImplementedError

    # ------------------------------------------------------------------
    def create_binary_op(self, opcode: str, lhs: SSAValue, rhs: SSAValue) -> Operation:
        if opcode == "add":
            return QAddiOp(lhs, rhs)
        if opcode == "sub":
            return QSubiOp(lhs, rhs)
        if opcode == "mul":
            return QMuliOp(lhs, rhs)
        if opcode == "div":
            return QDivSOp(lhs, rhs)
        raise NotImplementedError(opcode)

    def create_binary_imm_op(self, opcode: str, lhs: SSAValue, imm: int) -> Operation:
        if opcode == "add":
            return QAddiImmOp(lhs, imm)
        if opcode == "sub":
            return QSubiImmOp(lhs, imm)
        if opcode == "mul":
            return QMuliImmOp(lhs, imm)
        if opcode == "div":
            return QDivSImmOp(lhs, imm)
        raise NotImplementedError(opcode)

    # ------------------------------------------------------------------
    def translate_func(self, func: FuncOp) -> FuncOp:
        block = func.body.blocks[0]
        self.current_block = Block()
        self.cost_cache.clear()
        for op in block.ops:
            for res in op.results:
                self.compute_cost(res)
        # Use counts we already computed; create copy to update during traversal
        remaining = {val: len(val.uses) for val in self.use_count}
        for op in block.ops:
            if isinstance(op, ConstantOp):
                reg = self.allocate_reg()
                init_op = QuantumInitOp(op.value.value.data)
                self.current_block.add_op(init_op)
                init_op.results[0].name_hint = f"q{reg}_0"
                self.val_info[op.results[0]] = ValueInfo(reg, 0, ("const", op.value.value.data))
                self.reg_ssa[reg] = init_op.results[0]
            elif isinstance(op, (AddiOp, SubiOp, MuliOp, DivSIOp)):
                lhs, rhs = op.operands
                left_count = remaining[lhs] - 1
                right_count = remaining[rhs] - 1
                remaining[lhs] -= 1
                remaining[rhs] -= 1
                q_lhs = self.emit_value(lhs)
                q_rhs = self.emit_value(rhs)
                opcode = {
                    AddiOp: "add",
                    SubiOp: "sub",
                    MuliOp: "mul",
                    DivSIOp: "div",
                }[type(op)]
                comm = opcode in ("add", "mul")
                if comm:
                    if left_count > 0 and right_count == 0:
                        first, second, target = q_rhs, q_lhs, rhs
                    elif right_count > 0 and left_count == 0:
                        first, second, target = q_lhs, q_rhs, lhs
                    else:
                        if self.compute_cost(lhs) <= self.compute_cost(rhs):
                            first, second, target = q_lhs, q_rhs, lhs
                        else:
                            first, second, target = q_rhs, q_lhs, rhs
                else:
                    first, second, target = q_lhs, q_rhs, lhs
                new_op = self.create_binary_op(opcode, first, second)
                self.current_block.add_op(new_op)
                reg = self.val_info[target].reg
                version = self.reg_version[reg] + 1
                new_op.results[0].name_hint = f"q{reg}_{version}"
                self.reg_version[reg] = version
                self.reg_ssa[reg] = new_op.results[0]
                self.val_info[op.results[0]] = ValueInfo(reg, version, ("binary", (opcode, lhs, rhs, target)))
            elif op.name in ("mydialect.addi_imm", "mydialect.subi_imm", "mydialect.muli_imm", "mydialect.divsi_imm"):
                (lhs,) = op.operands
                imm = int(op.imm.value.data)
                remaining[lhs] -= 1
                q_lhs = self.emit_value(lhs)
                opcode = {
                    "mydialect.addi_imm": "add",
                    "mydialect.subi_imm": "sub",
                    "mydialect.muli_imm": "mul",
                    "mydialect.divsi_imm": "div",
                }[op.name]
                new_op = self.create_binary_imm_op(opcode, q_lhs, imm)
                self.current_block.add_op(new_op)
                reg = self.val_info[lhs].reg
                version = self.reg_version[reg] + 1
                new_op.results[0].name_hint = f"q{reg}_{version}"
                self.reg_version[reg] = version
                self.reg_ssa[reg] = new_op.results[0]
                self.val_info[op.results[0]] = ValueInfo(reg, version, ("binaryimm", (opcode, lhs, imm)))
            elif isinstance(op, ReturnOp):
                if op.operands:
                    q_val = self.emit_value(op.operands[0])
                    ret = ReturnOp(q_val)
                else:
                    ret = ReturnOp([])
                self.current_block.add_op(ret)
            else:
                raise NotImplementedError(f"Unsupported op {op.name}")
        func_type = ([i32] * len(func.function_type.inputs.data), [i32])
        return FuncOp(func.sym_name.data, func_type, Region([self.current_block]))

"""Translate standard arithmetic MLIR operations to a quantum dialect.

This module provides ``QuantumTranslator`` which walks over a module
containing standard arithmetic operations and produces an equivalent
module using the custom quantum dialect defined in ``quantum_dialect``.
Operations are translated so that results are written to fresh quantum
registers.  Registers are never copied; if a value gets overwritten the
translator can recompute it from the stored expression description.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Any

# xdsl imports used to manipulate MLIR operations and types
from xdsl.dialects.builtin import ModuleOp, i32
from xdsl.dialects.func import FuncOp, ReturnOp
from xdsl.dialects.arith import ConstantOp, AddiOp, SubiOp, MuliOp, DivSIOp
from xdsl.ir import Block, Region, SSAValue, Operation

# Quantum dialect operations that mirror the arithmetic ops but operate on
# quantum registers instead of plain integers.
from .quantum_dialect import (
    QuantumInitOp,
    QAddiOp, QSubiOp, QMuliOp, QDivSOp,
    QAddiImmOp, QSubiImmOp, QMuliImmOp, QDivSImmOp,
    CQAddiOp, CQSubiOp, CQMuliOp, CQDivSOp,
    QAndOp, QCmpiOp, QNotOp, QuantumCInitOp,
    CQAddiImmOp, CQSubiImmOp, CQMuliImmOp, CQDivSImmOp,
)


@dataclass
class ValueInfo:
    """Metadata about how a value is produced and stored.

    ``reg``        Identifier of the quantum register holding the value.
    ``version``    Version number for the value stored in the register.
    ``expr``       Description of how to recompute the value if overwritten.
    """
    reg: int
    version: int
    expr: Any


class QuantumTranslator:
    """Translate standard MLIR to quantum-friendly dialect."""

    def __init__(self, module: ModuleOp):
        self.module = module
        self.q_module: ModuleOp | None = None

        # next free quantum register id
        self.next_reg = 0

        # active controls (stack of SSAValue booleans)
        self.control_stack: list[SSAValue] = []

        # bookkeeping
        self.val_info: Dict[SSAValue, ValueInfo] = {}
        self.reg_version: Dict[int, int] = {}
        self.reg_ssa: Dict[int, SSAValue] = {}
        self.use_count: Dict[SSAValue, int] = {}
        self.cost_cache: Dict[SSAValue, int] = {}

        # will be set in translate_func
        self.current_block: Block | None = None

    # ------------------ helpers ------------------

    def _count_uses(self, value: SSAValue) -> int:
        """
        Robustly count uses of a Value across versions:
        - prefer value.num_uses if present
        - otherwise count the iterable value.uses (IRUses often lacks __len__)
        """
        n = getattr(value, "num_uses", None)
        if isinstance(n, int):
            return n
        uses_iter = getattr(value, "uses", None)
        if uses_iter is None:
            return 0
        try:
            return sum(1 for _ in uses_iter)
        except Exception:
            return 0

    def emit_controlled_init(self, ctrl: SSAValue, value: int) -> SSAValue:
        """Emit a controlled initialization to `value`, returning the new register."""
        reg = self.allocate_reg()
        init_op = QuantumCInitOp(ctrl, value)
        self.current_block.add_op(init_op)
        init_op.results[0].name_hint = f"q{reg}_0"
        self.reg_version[reg] = 0
        self.reg_ssa[reg] = init_op.results[0]
        return init_op.results[0]

    def get_current_control(self) -> SSAValue | None:
        """Combine active control conditions using QAndOp if needed."""
        if not self.control_stack:
            return None
        if len(self.control_stack) == 1:
            return self.control_stack[0]

        ctrl = self.control_stack[0]
        for cond in self.control_stack[1:]:
            new_reg = self.allocate_reg()
            and_op = QAndOp(ctrl, cond)
            self.current_block.add_op(and_op)
            and_op.results[0].name_hint = f"q{new_reg}_0"
            self.reg_version[new_reg] = 0
            self.reg_ssa[new_reg] = and_op.results[0]
            ctrl = and_op.results[0]
        return ctrl

    def combine_controls(self, controls: list[SSAValue]) -> SSAValue:
        """Return the conjunction (AND) of multiple control bits."""
        if not controls:
            raise ValueError("No control signals provided")
        if len(controls) == 1:
            return controls[0]
        current = controls[0]
        for ctrl in controls[1:]:
            reg = self.allocate_reg()
            and_op = QAndOp(current, ctrl)
            self.current_block.add_op(and_op)
            and_op.results[0].name_hint = f"q{reg}_0"
            self.reg_version[reg] = 0
            self.reg_ssa[reg] = and_op.results[0]
            current = and_op.results[0]
        return current

    def create_controlled_op(self, opcode: str, lhs: SSAValue, rhs: SSAValue, ctrl: SSAValue) -> Operation:
        """Emit a controlled quantum operation."""
        if opcode == "add":
            return CQAddiOp(lhs, rhs, ctrl)
        if opcode == "sub":
            return CQSubiOp(lhs, rhs, ctrl)
        if opcode == "mul":
            return CQMuliOp(lhs, rhs, ctrl)
        if opcode == "div":
            return CQDivSOp(lhs, rhs, ctrl)
        raise NotImplementedError(f"Unknown opcode for controlled op: {opcode}")

    # ------------------ core translation ------------------

    def translate(self) -> ModuleOp:
        """Translate the entire module to the quantum dialect."""
        # Build module-wide use counts (robust to IRUses)
        self.compute_use_counts()

        # Create new output module
        self.q_module = ModuleOp([])

        # Translate each function and append
        for func in self.module.ops:
            q_func = self.translate_func(func)
            self.q_module.body.blocks[0].add_op(q_func)

        return self.q_module

    def compute_use_counts(self):
        """
        Build a map SSAValue -> number of uses (version-robust, works when .uses has no __len__).
        """
        self.use_count = {}

        # Walk all ops in all functions (be conservative and comprehensive)
        for maybe_func in getattr(self.module, "ops", []):
            # If it is a FuncOp, walk inside its body
            if isinstance(maybe_func, FuncOp):
                for blk in maybe_func.body.blocks:
                    for op in blk.ops:
                        results = getattr(op, "results", []) or []
                        for res in results:
                            self.use_count[res] = self._count_uses(res)
            else:
                # Non-func top-level ops (if any)
                results = getattr(maybe_func, "results", []) or []
                for res in results:
                    self.use_count[res] = self._count_uses(res)

    def compute_cost(self, val: SSAValue) -> int:
        """Recursively estimate the cost of recomputing ``val``."""
        if val in self.cost_cache:
            return self.cost_cache[val]

        op = val.owner

        if isinstance(op, ConstantOp):
            cost = 1
        elif isinstance(op, (AddiOp, SubiOp, MuliOp, DivSIOp)):
            cost = 1 + self.compute_cost(op.operands[0]) + self.compute_cost(op.operands[1])
        elif op.name in ("iarith.addi_imm", "iarith.subi_imm", "iarith.muli_imm", "iarith.divsi_imm"):
            cost = 1 + self.compute_cost(op.operands[0])
        else:
            cost = 1

        self.cost_cache[val] = cost
        return cost

    def remaining_uses(self, val: SSAValue) -> int:
        """Return how many times ``val`` is still used (0 if unknown)."""
        return self.use_count.get(val, 0)

    def allocate_reg(self) -> int:
        """Allocate a new quantum register identifier."""
        r = self.next_reg
        self.next_reg += 1
        self.reg_version[r] = 0
        return r

    def emit_value(self, val: SSAValue) -> SSAValue:
        """Ensure ``val`` is materialized and return its SSA value."""
        info = self.val_info[val]
        reg = info.reg
        if self.reg_version.get(reg, 0) != info.version:
            self.recompute(val)
            reg = info.reg
        return self.reg_ssa[reg]

    def recompute(self, val: SSAValue):
        """Recompute ``val`` based on the expression stored in ``val_info``."""
        info = self.val_info[val]
        expr = info.expr

        if expr[0] == "const":
            value = expr[1]
            reg = self.allocate_reg()
            op = QuantumInitOp(value)
            self.current_block.add_op(op)
            op.results[0].name_hint = f"q{reg}_0"
            self.reg_version[reg] = 0
            self.reg_ssa[reg] = op.results[0]
            info.version = 0
            info.reg = reg

        elif expr[0] == "binary":
            opcode, lhs, rhs = expr[1]
            q_lhs = self.emit_value(lhs)
            q_rhs = self.emit_value(rhs)
            if q_lhs is q_rhs:
                q_rhs = self.duplicate_value(rhs)
            reg = self.allocate_reg()
            op = self.create_binary_op(opcode, q_lhs, q_rhs)
            self.current_block.add_op(op)
            op.results[0].name_hint = f"q{reg}_0"
            self.reg_version[reg] = 0
            self.reg_ssa[reg] = op.results[0]
            info.version = 0
            info.reg = reg

        elif expr[0] == "binaryimm":
            opcode, lhs, imm = expr[1]
            q_lhs = self.emit_value(lhs)
            reg = self.allocate_reg()
            op = self.create_binary_imm_op(opcode, q_lhs, imm)
            self.current_block.add_op(op)
            op.results[0].name_hint = f"q{reg}_0"
            self.reg_version[reg] = 0
            self.reg_ssa[reg] = op.results[0]
            info.version = 0
            info.reg = reg

        else:
            raise NotImplementedError

    def duplicate_value(self, val: SSAValue) -> SSAValue:
        """Return a fresh register that is a copy of ``val`` using addi_imm 0."""
        q_val = self.emit_value(val)
        reg = self.allocate_reg()
        op = QAddiImmOp(q_val, 0)
        self.current_block.add_op(op)
        op.results[0].name_hint = f"q{reg}_0"
        self.reg_version[reg] = 0
        self.reg_ssa[reg] = op.results[0]
        return op.results[0]

    def create_binary_op(self, opcode: str, lhs: SSAValue, rhs: SSAValue) -> Operation:
        ctrl = self.get_current_control()
        if ctrl is None:
            if opcode == "add": return QAddiOp(lhs, rhs)
            if opcode == "sub": return QSubiOp(lhs, rhs)
            if opcode == "mul": return QMuliOp(lhs, rhs)
            if opcode == "div": return QDivSOp(lhs, rhs)
        else:
            if opcode == "add": return CQAddiOp(lhs, rhs, ctrl)
            if opcode == "sub": return CQSubiOp(lhs, rhs, ctrl)
            if opcode == "mul": return CQMuliOp(lhs, rhs, ctrl)
            if opcode == "div": return CQDivSOp(lhs, rhs, ctrl)
        raise NotImplementedError(opcode)

    def create_binary_imm_op(self, opcode: str, lhs: SSAValue, imm: int) -> Operation:
        """Emit an immediate binary op for ``opcode``."""
        ctrl = self.get_current_control()
        if ctrl is None:
            if opcode == "add": return QAddiImmOp(lhs, imm)
            if opcode == "sub": return QSubiImmOp(lhs, imm)
            if opcode == "mul": return QMuliImmOp(lhs, imm)
            if opcode == "div": return QDivSImmOp(lhs, imm)
        else:
            if opcode == "add": return CQAddiImmOp(lhs, imm, ctrl)
            if opcode == "sub": return CQSubiImmOp(lhs, imm, ctrl)
            if opcode == "mul": return CQMuliImmOp(lhs, imm, ctrl)
            if opcode == "div": return CQDivSImmOp(lhs, imm, ctrl)
        raise NotImplementedError(f"Unknown opcode for immediate binary op: {opcode}")

    # ------------------ per-op translation (used in cond blocks) ------------------

    def translate_op(self, op: Operation):
        if isinstance(op, ConstantOp):
            value = op.value.value.data
            ctrl = self.get_current_control()
            init_op = QuantumCInitOp(ctrl, value) if ctrl is not None else QuantumInitOp(value)
            reg = self.allocate_reg()
            self.current_block.add_op(init_op)
            init_op.results[0].name_hint = f"q{reg}_0"
            self.val_info[op.results[0]] = ValueInfo(reg, 0, ("const", value))
            self.reg_ssa[reg] = init_op.results[0]
            self.reg_version[reg] = 0

        elif isinstance(op, (AddiOp, SubiOp, MuliOp, DivSIOp)):
            lhs, rhs = op.operands
            q_lhs = self.emit_value(lhs)
            q_rhs = self.emit_value(rhs)
            if q_lhs is q_rhs:
                q_rhs = self.duplicate_value(rhs)
            opcode = {AddiOp: "add", SubiOp: "sub", MuliOp: "mul", DivSIOp: "div"}[type(op)]
            reg = self.allocate_reg()
            new_op = self.create_binary_op(opcode, q_lhs, q_rhs)
            self.current_block.add_op(new_op)
            new_op.results[0].name_hint = f"q{reg}_0"
            self.reg_ssa[reg] = new_op.results[0]
            self.val_info[op.results[0]] = ValueInfo(reg, 0, ("binary", (opcode, lhs, rhs)))

        elif op.name == "arith.cmpi":
            lhs, rhs = op.operands
            predicate = int(op.predicate.value.data)
            q_lhs = self.emit_value(lhs)
            q_rhs = self.emit_value(rhs)
            cmp_op = QCmpiOp(q_lhs, q_rhs, predicate)
            self.current_block.add_op(cmp_op)
            reg = self.allocate_reg()
            cmp_op.results[0].name_hint = f"q{reg}_0"
            self.reg_ssa[reg] = cmp_op.results[0]
            self.reg_version[reg] = 0
            self.val_info[op.results[0]] = ValueInfo(reg, 0, ("cmpi", lhs, rhs, predicate))

        elif op.name == "cf.cond_br":
            cond_val = self.emit_value(op.operands[0])
            true_block = op.successors[0]
            false_block = op.successors[1]

            # THEN branch
            self.control_stack.append(cond_val)
            for inner_op in true_block.ops:
                self.translate_op(inner_op)
            self.control_stack.pop()

            # ELSE branch with NOT(cond)
            not_op = QNotOp(cond_val)
            self.current_block.add_op(not_op)
            not_reg = self.allocate_reg()
            not_op.results[0].name_hint = f"q{not_reg}_0"
            self.reg_version[not_reg] = 0
            self.reg_ssa[not_reg] = not_op.results[0]

            self.control_stack.append(not_op.results[0])
            for inner_op in false_block.ops:
                self.translate_op(inner_op)
            self.control_stack.pop()

        elif isinstance(op, ReturnOp):
            if op.operands:
                q_val = self.emit_value(op.operands[0])
                ret = ReturnOp(q_val)
            else:
                ret = ReturnOp([])
            self.current_block.add_op(ret)

        elif op.name in ("iarith.addi_imm", "iarith.subi_imm", "iarith.muli_imm", "iarith.divsi_imm"):
            (lhs,) = op.operands
            imm = int(op.imm.value.data)
            q_lhs = self.emit_value(lhs)
            opcode = {
                "iarith.addi_imm": "add",
                "iarith.subi_imm": "sub",
                "iarith.muli_imm": "mul",
                "iarith.divsi_imm": "div",
            }[op.name]
            reg = self.allocate_reg()
            new_op = self.create_binary_imm_op(opcode, q_lhs, imm)
            self.current_block.add_op(new_op)
            new_op.results[0].name_hint = f"q{reg}_0"
            self.reg_ssa[reg] = new_op.results[0]
            self.reg_version[reg] = 0
            self.val_info[op.results[0]] = ValueInfo(reg, 0, ("binaryimm", (opcode, lhs, imm)))

        elif op.name == "arith.extui":
            (src,) = op.operands
            q_src = self.emit_value(src)
            ctrl = self.get_current_control()
            if ctrl is not None:
                combined = self.combine_controls([ctrl, q_src])
                res = self.emit_controlled_init(combined, 1)
            else:
                res = self.emit_controlled_init(q_src, 1)
            reg = self.next_reg - 1
            self.val_info[op.results[0]] = ValueInfo(reg, 0, ("extui", src))
            self.reg_ssa[reg] = res

        else:
            raise NotImplementedError(f"Unsupported op {op.name}")

    # ------------------ function translation ------------------

    def translate_func(self, func: FuncOp) -> FuncOp:
        """Translate a single function to the quantum dialect."""
        block = func.body.blocks[0]
        self.current_block = Block()
        self.cost_cache.clear()

        # Pre-compute costs for results in this block
        for op in block.ops:
            for res in op.results:
                self.compute_cost(res)

        # Build per-function remaining use counts for all results
        remaining: Dict[SSAValue, int] = {}
        for op in block.ops:
            for res in op.results:
                remaining[res] = self._count_uses(res)

        def dec_remaining(val: SSAValue):
            # ensure key exists; if not, initialize with actual count
            if val not in remaining:
                remaining[val] = self._count_uses(val)
            remaining[val] = max(remaining[val] - 1, 0)

        # Translate ops in order
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
                dec_remaining(lhs)
                dec_remaining(rhs)
                q_lhs = self.emit_value(lhs)
                q_rhs = self.emit_value(rhs)
                if q_lhs is q_rhs:
                    q_rhs = self.duplicate_value(rhs)
                opcode = {AddiOp: "add", SubiOp: "sub", MuliOp: "mul", DivSIOp: "div"}[type(op)]
                reg = self.allocate_reg()
                new_op = self.create_binary_op(opcode, q_lhs, q_rhs)
                self.current_block.add_op(new_op)
                new_op.results[0].name_hint = f"q{reg}_0"
                self.reg_ssa[reg] = new_op.results[0]
                self.val_info[op.results[0]] = ValueInfo(reg, 0, ("binary", (opcode, lhs, rhs)))

            elif op.name in ("iarith.addi_imm", "iarith.subi_imm", "iarith.muli_imm", "iarith.divsi_imm"):
                (lhs,) = op.operands
                imm = int(op.imm.value.data)
                dec_remaining(lhs)
                q_lhs = self.emit_value(lhs)
                opcode = {
                    "iarith.addi_imm": "add",
                    "iarith.subi_imm": "sub",
                    "iarith.muli_imm": "mul",
                    "iarith.divsi_imm": "div",
                }[op.name]
                reg = self.allocate_reg()
                new_op = self.create_binary_imm_op(opcode, q_lhs, imm)
                self.current_block.add_op(new_op)
                new_op.results[0].name_hint = f"q{reg}_0"
                self.reg_ssa[reg] = new_op.results[0]
                self.val_info[op.results[0]] = ValueInfo(reg, 0, ("binaryimm", (opcode, lhs, imm)))

            elif op.name == "cf.cond_br":
                cond_val = self.emit_value(op.operands[0])
                true_block = op.successors[0]
                false_block = op.successors[1]

                # THEN
                self.control_stack.append(cond_val)
                for inner_op in true_block.ops:
                    self.translate_op(inner_op)
                self.control_stack.pop()

                # ELSE with NOT(cond)
                not_op = QNotOp(cond_val)
                self.current_block.add_op(not_op)
                not_reg = self.allocate_reg()
                not_op.results[0].name_hint = f"q{not_reg}_0"
                self.reg_version[not_reg] = 0
                self.reg_ssa[not_reg] = not_op.results[0]

                self.control_stack.append(not_op.results[0])
                for inner_op in false_block.ops:
                    self.translate_op(inner_op)
                self.control_stack.pop()

            elif isinstance(op, ReturnOp):
                if op.operands:
                    q_val = self.emit_value(op.operands[0])
                    ret = ReturnOp(q_val)
                else:
                    ret = ReturnOp([])
                self.current_block.add_op(ret)

            elif op.name == "arith.cmpi":
                lhs, rhs = op.operands
                predicate = int(op.predicate.value.data)
                q_lhs = self.emit_value(lhs)
                q_rhs = self.emit_value(rhs)
                reg = self.allocate_reg()
                cmp_op = QCmpiOp(q_lhs, q_rhs, predicate)
                self.current_block.add_op(cmp_op)
                cmp_op.results[0].name_hint = f"q{reg}_0"
                self.val_info[op.results[0]] = ValueInfo(reg, 0, ("cmpi", lhs, rhs, predicate))
                self.reg_ssa[reg] = cmp_op.results[0]

            elif op.name == "arith.extui":
                (src,) = op.operands
                dec_remaining(src)
                q_src = self.emit_value(src)
                ctrl = self.get_current_control()
                if ctrl is not None:
                    combined = self.combine_controls([ctrl, q_src])
                    res = self.emit_controlled_init(combined, 1)
                else:
                    res = self.emit_controlled_init(q_src, 1)
                reg = self.next_reg - 1
                self.val_info[op.results[0]] = ValueInfo(reg, 0, ("extui", src))
                self.reg_ssa[reg] = res

            else:
                raise NotImplementedError(f"Unsupported op {op.name}")

        # Construct the function with the same signature as the original
        func_type = ([i32] * len(func.function_type.inputs.data), [i32])
        return FuncOp(func.sym_name.data, func_type, Region([self.current_block]))

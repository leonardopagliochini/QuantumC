"""Translate standard arithmetic MLIR operations to a quantum dialect.

This module provides ``QuantumTranslator`` which walks over a module
containing standard arithmetic operations and produces an equivalent
module using the custom quantum dialect defined in ``quantum_dialect``.
The translation keeps track of quantum registers, recreating values
when necessary and attempting to reuse registers when possible.
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
    """Metadata about how a value is produced and stored.

    ``reg``
        Identifier of the quantum register holding the value.

    ``version``
        Version number indicating which value is currently stored in the
        register.  Whenever the register contents change the version is
        incremented so we know if a cached value is stale.

    ``expr``
        A description of how to recompute the value if the register gets
        overwritten.  The translator stores a tuple describing the original
        operation that produced the value so it can be regenerated on demand.
    """

    reg: int
    version: int
    expr: Any

class QuantumTranslator:
    """Translate standard MLIR to quantum-friendly dialect."""

    def __init__(self, module: ModuleOp):
        """Create a translator for the given ``module``.

        Parameters
        ----------
        module:
            The input ``ModuleOp`` containing arithmetic operations that will
            be converted to the quantum dialect.
        """

        # The original module that will be walked and rewritten.
        self.module = module

        # Placeholder for the translated module once ``translate`` is called.
        self.q_module: ModuleOp | None = None

        # ``next_reg`` stores the number of the next free quantum register.
        # Registers are identified by an integer and are allocated sequentially.
        self.next_reg = 0

        # Mapping from SSA values in the original module to ``ValueInfo``
        # records.  These records describe which register currently contains the
        # value and how it can be recomputed if needed.
        self.val_info: Dict[SSAValue, ValueInfo] = {}

        # Track, for each register, which version of the value it currently
        # holds.  This allows the translator to detect when a cached value has
        # been overwritten and needs recomputation.
        self.reg_version: Dict[int, int] = {}

        # Map each register identifier to the most recent SSA value representing
        # its contents in the quantum module being built.
        self.reg_ssa: Dict[int, SSAValue] = {}

        # Number of remaining uses for every SSA value in the original module.
        self.use_count: Dict[SSAValue, int] = {}

        # Cache used by ``compute_cost`` to memoize recomputation costs.
        self.cost_cache: Dict[SSAValue, int] = {}

    # ------------------------------------------------------------------
    def translate(self) -> ModuleOp:
        """Translate the entire module to the quantum dialect."""

        # First compute how many times each SSA value is used.  This information
        # is needed later when deciding whether we can overwrite a register or
        # if we must keep its original value alive.
        self.compute_use_counts()

        # Create a new, empty module that will hold the translated functions.
        self.q_module = ModuleOp([])

        # Translate each function one by one and append the resulting quantum
        # function to the new module.
        for func in self.module.ops:
            q_func = self.translate_func(func)
            self.q_module.body.blocks[0].add_op(q_func)

        # The new module is now populated with quantum dialect operations.
        return self.q_module

    # ------------------------------------------------------------------
    def compute_use_counts(self):
        """Populate ``self.use_count`` with the number of uses for each value."""
        # Walk through all operations in every function and count how many times
        # each SSA value result is referenced.  The result is stored in the
        # ``use_count`` dictionary.
        for func in self.module.ops:
            block = func.body.blocks[0]
            for op in block.ops:
                for res in op.results:
                    self.use_count[res] = len(res.uses)

    # ------------------------------------------------------------------
    def compute_cost(self, val: SSAValue) -> int:
        """Recursively estimate the cost of recomputing ``val``."""

        # ``compute_cost`` is used to decide whether it is cheaper to recompute
        # a value or to keep it alive in a register.  The method walks the
        # expression tree that produced ``val`` and sums a simple cost metric.

        # Memoize results so we do not recompute the same cost multiple times.
        if val in self.cost_cache:
            return self.cost_cache[val]

        op = val.owner

        # Constants are assumed to be very cheap to recreate.
        if isinstance(op, ConstantOp):
            cost = 1

        # Binary arithmetic operations have a base cost of 1 plus the cost of
        # recomputing both operands.
        elif isinstance(op, (AddiOp, SubiOp, MuliOp, DivSIOp)):
            cost = 1 + self.compute_cost(op.operands[0]) + self.compute_cost(op.operands[1])

        # Binary operations with an immediate operand only need to recompute the
        # non-immediate side.
        elif op.name in (
            "mydialect.addi_imm",
            "mydialect.subi_imm",
            "mydialect.muli_imm",
            "mydialect.divsi_imm",
        ):
            cost = 1 + self.compute_cost(op.operands[0])

        # Fallback cost for any other operation type.
        else:
            cost = 1

        # Store the computed cost in the cache and return it.
        self.cost_cache[val] = cost
        return cost

    # ------------------------------------------------------------------
    def remaining_uses(self, val: SSAValue) -> int:
        """Return how many times ``val`` is still used."""

        # ``use_count`` is updated as we traverse operations in a function.
        # If a value is not present in the dictionary it has no remaining uses.
        return self.use_count.get(val, 0)

    # ------------------------------------------------------------------
    def allocate_reg(self) -> int:
        """Allocate a new quantum register identifier."""

        # Registers are numbered sequentially. ``next_reg`` always points to the
        # first unused identifier.
        r = self.next_reg
        self.next_reg += 1

        # Start the version counter for the new register at zero.
        self.reg_version[r] = 0
        return r

    # ------------------------------------------------------------------
    def emit_value(self, val: SSAValue) -> SSAValue:
        """Ensure ``val`` is materialized and return its SSA value."""

        # ``val_info`` tells us which register currently stores ``val`` and
        # which version of the value should be present there.
        info = self.val_info[val]
        reg = info.reg

        # If the register has been updated since ``info`` was recorded we must
        # recompute the value so that the register again holds the desired
        # version.
        if self.reg_version[reg] != info.version:
            self.recompute(val)

        # Return the SSA value associated with the current contents of the
        # register.
        return self.reg_ssa[reg]

    # ------------------------------------------------------------------
    def recompute(self, val: SSAValue):
        """Recompute ``val`` based on the expression stored in ``val_info``."""

        info = self.val_info[val]
        expr = info.expr

        # ``expr`` is a tuple describing how ``val`` was originally produced.
        # The first element selects the kind of expression.
        if expr[0] == "const":
            # The value was produced by a constant operation.
            value = expr[1]
            reg = info.reg
            version = self.reg_version[reg] + 1

            # Allocate a fresh register so that we do not overwrite the
            # previous value. Quantum registers cannot be reset in place without
            # destroying information.
            reg = self.allocate_reg()

            # Emit the initialization of the new register with the constant
            # value.
            op = QuantumInitOp(value)
            self.current_block.add_op(op)

            # Track the new version and SSA value for the register.
            op.results[0].name_hint = f"q{reg}_{version}"
            self.reg_version[reg] = version
            self.reg_ssa[reg] = op.results[0]

            # Update the stored ``ValueInfo`` so future uses know where the
            # value lives.
            info.version = version
            info.reg = reg

        elif expr[0] == "binary":
            # ``val`` was produced by a binary operation with two operands.
            opcode, lhs, rhs, target = expr[1]
            q_lhs = self.emit_value(lhs)
            q_rhs = self.emit_value(rhs)

            # Determine which register will hold the result.  If ``target`` is
            # ``rhs`` we swap the operands because the operation will update the
            # register corresponding to ``rhs``.
            if target is rhs:
                first = q_rhs
                second = q_lhs
                reg = self.val_info[rhs].reg
            else:
                first = q_lhs
                second = q_rhs
                reg = self.val_info[lhs].reg

            # Emit the appropriate quantum binary operation.
            op = self.create_binary_op(opcode, first, second)
            self.current_block.add_op(op)

            # Update bookkeeping for the target register.
            version = self.reg_version[reg] + 1
            op.results[0].name_hint = f"q{reg}_{version}"
            self.reg_version[reg] = version
            self.reg_ssa[reg] = op.results[0]
            info.version = version

        elif expr[0] == "binaryimm":
            # ``val`` came from a binary operation with an immediate operand.
            opcode, lhs, imm = expr[1]
            q_lhs = self.emit_value(lhs)
            reg = self.val_info[lhs].reg
            op = self.create_binary_imm_op(opcode, q_lhs, imm)
            self.current_block.add_op(op)

            # As above, bump the register version and remember the result SSA
            # value.
            version = self.reg_version[reg] + 1
            op.results[0].name_hint = f"q{reg}_{version}"
            self.reg_version[reg] = version
            self.reg_ssa[reg] = op.results[0]
            info.version = version

        else:
            raise NotImplementedError

    # ------------------------------------------------------------------
    def create_binary_op(self, opcode: str, lhs: SSAValue, rhs: SSAValue) -> Operation:
        """Emit a binary quantum op for ``opcode``."""

        # Map the textual opcode to the corresponding quantum operation class.
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
        """Emit an immediate binary op for ``opcode``."""

        # Similar to ``create_binary_op`` but one operand is a Python integer.
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
        """Translate a single function to the quantum dialect."""

        # We only handle single-block functions. ``block`` is the list of
        # arithmetic operations that will be translated.
        block = func.body.blocks[0]

        # ``current_block`` accumulates the newly created quantum operations.
        self.current_block = Block()

        # Clear the cost cache since costs depend on the current function only.
        self.cost_cache.clear()

        # Pre-compute the cost for each produced value.  This information is
        # later used to choose whether to recompute an operand or to store it.
        for op in block.ops:
            for res in op.results:
                self.compute_cost(res)

        # ``remaining`` tracks how many uses of each SSA value remain while we
        # traverse the block.  Start with the global use counts.
        remaining = {val: len(val.uses) for val in self.use_count}

        # Translate each operation in order.
        for op in block.ops:
            if isinstance(op, ConstantOp):
                # Constants simply allocate a new register and initialize it.
                reg = self.allocate_reg()
                init_op = QuantumInitOp(op.value.value.data)
                self.current_block.add_op(init_op)
                init_op.results[0].name_hint = f"q{reg}_0"
                self.val_info[op.results[0]] = ValueInfo(reg, 0, ("const", op.value.value.data))
                self.reg_ssa[reg] = init_op.results[0]

            elif isinstance(op, (AddiOp, SubiOp, MuliOp, DivSIOp)):
                # Binary arithmetic operation with two SSA operands.
                lhs, rhs = op.operands

                # Compute remaining use counts for operands after this
                # operation executes.
                left_count = remaining[lhs] - 1
                right_count = remaining[rhs] - 1
                remaining[lhs] -= 1
                remaining[rhs] -= 1

                # Materialize the current values of the operands.
                q_lhs = self.emit_value(lhs)
                q_rhs = self.emit_value(rhs)

                # Determine the opcode string for convenience.
                opcode = {
                    AddiOp: "add",
                    SubiOp: "sub",
                    MuliOp: "mul",
                    DivSIOp: "div",
                }[type(op)]

                # ``add`` and ``mul`` are commutative.  When possible we update
                # the operand that will not be used again to avoid allocating a
                # new register.
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

                # Emit the quantum binary operation and update bookkeeping for
                # the target register.
                new_op = self.create_binary_op(opcode, first, second)
                self.current_block.add_op(new_op)
                reg = self.val_info[target].reg
                version = self.reg_version[reg] + 1
                new_op.results[0].name_hint = f"q{reg}_{version}"
                self.reg_version[reg] = version
                self.reg_ssa[reg] = new_op.results[0]
                self.val_info[op.results[0]] = ValueInfo(reg, version, ("binary", (opcode, lhs, rhs, target)))

            elif op.name in ("mydialect.addi_imm", "mydialect.subi_imm", "mydialect.muli_imm", "mydialect.divsi_imm"):
                # Binary operation where one operand is an immediate integer.
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
                # Return statements are forwarded directly after materializing
                # the returned value.
                if op.operands:
                    q_val = self.emit_value(op.operands[0])
                    ret = ReturnOp(q_val)
                else:
                    ret = ReturnOp([])
                self.current_block.add_op(ret)

            else:
                # Any other operation is currently unsupported.
                raise NotImplementedError(f"Unsupported op {op.name}")

        # Construct the function with the same signature as the original but
        # containing the newly built block of quantum operations.
        func_type = ([i32] * len(func.function_type.inputs.data), [i32])
        return FuncOp(func.sym_name.data, func_type, Region([self.current_block]))

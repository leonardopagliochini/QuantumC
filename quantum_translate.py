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

        # Return the SSA value associated with the current contents of the
        # register.
        return self.reg_ssa[reg]


    # ------------------------------------------------------------------
    def create_binary_op(self, opcode: str, lhs: SSAValue, rhs: SSAValue, reg: int) -> Operation:
        """Emit a binary quantum op for ``opcode``."""
        
        # properties to pass to operations, only reg for now
        props = {"reg_id": reg}

        # Map the textual opcode to the corresponding quantum operation class.
        if opcode == "add":
            return QAddiOp(lhs, rhs, properties=props)  
        if opcode == "sub":
            return QSubiOp(lhs, rhs, properties=props)  
        if opcode == "mul":
            return QMuliOp(lhs, rhs, properties=props)  
        if opcode == "div":
            return QDivSOp(lhs, rhs, properties=props) 
        raise NotImplementedError(opcode)

    def create_binary_imm_op(self, opcode: str, lhs: SSAValue, imm: int, reg: int) -> Operation:
        """Emit an immediate binary op for ``opcode``."""

        # properties to pass to operations, only reg for now
        props = {"reg_id": reg}  # add

        # Similar to ``create_binary_op`` but one operand is a Python integer.
        if opcode == "add":
            return QAddiImmOp(lhs, imm, properties=props)  # add
        if opcode == "sub":
            return QSubiImmOp(lhs, imm, properties=props)  # add
        if opcode == "mul":
            return QMuliImmOp(lhs, imm, properties=props)  # add
        if opcode == "div":
            return QDivSImmOp(lhs, imm, properties=props)  # add
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

        # Translate each operation in order.
        for op in block.ops:
            if isinstance(op, ConstantOp):
                # Constants simply allocate a new register and initialize it.
                reg = self.allocate_reg()
                init_op = QuantumInitOp(op.value.value.data, reg)
                self.current_block.add_op(init_op)

                # Use naming convention for register versioning.
                init_op.results[0].name_hint = f"q{reg}_0"

                # Track result metadata for register management.
                self.val_info[op.results[0]] = ValueInfo(reg, 0, ("const", op.value.value.data))
                self.reg_ssa[reg] = init_op.results[0]

            elif isinstance(op, (AddiOp, SubiOp, MuliOp, DivSIOp)):
                # Binary arithmetic operation with two SSA operands.
                lhs, rhs = op.operands

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

                # For quantum ops we always overwrite the lhs register.
                target = lhs
                first, second = q_lhs, q_rhs

                # Emit the quantum binary operation and update bookkeeping for
                # the overwritten target register.
                new_op = self.create_binary_op(opcode, first, second)
                self.current_block.add_op(new_op)

                # Retrieve the register associated with the overwritten operand.
                reg = self.val_info[target].reg

                # Increment the version for this register and name the result.
                version = self.reg_version[reg] + 1
                new_op.results[0].name_hint = f"q{reg}_{version}"

                # assing register as a property to the result
                new_op.results[0].properties["reg_id"] = reg

                # Update bookkeeping for register version and SSA mapping.
                self.reg_version[reg] = version
                self.reg_ssa[reg] = new_op.results[0]
                self.val_info[op.results[0]] = ValueInfo(reg, version, ("binary", (opcode, lhs, rhs, target)))

            elif op.name in ("iarith.addi_imm", "iarith.subi_imm", "iarith.muli_imm", "iarith.divsi_imm"):
                # Binary operation where one operand is an immediate integer.
                (lhs,) = op.operands

                # Parse the immediate value from the operation.
                imm = int(op.imm.value.data)

                # Materialize the SSA operand value.
                q_lhs = self.emit_value(lhs)

                # Select the opcode for the quantum dialect equivalent.
                opcode = {
                    "iarith.addi_imm": "add",
                    "iarith.subi_imm": "sub",
                    "iarith.muli_imm": "mul",
                    "iarith.divsi_imm": "div",
                }[op.name]

                # Emit the quantum immediate operation using lhs and imm.
                new_op = self.create_binary_imm_op(opcode, q_lhs, imm)
                self.current_block.add_op(new_op)

                # Retrieve and increment the register version for lhs.
                reg = self.val_info[lhs].reg
                version = self.reg_version[reg] + 1
                new_op.results[0].name_hint = f"q{reg}_{version}"
                
                # assing register as a property to the result
                new_op.results[0].properties["reg_id"] = reg


                # Update bookkeeping for SSA and reg_id mapping.
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

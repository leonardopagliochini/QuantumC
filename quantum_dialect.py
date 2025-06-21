"""Additional quantum-specific MLIR dialect operations.

This module defines a minimal set of operations that operate on quantum
registers rather than plain integers.  They closely mirror their counterparts
in the standard arithmetic dialect so that translated code retains a familiar
shape while being explicit about when quantum state is modified.
"""

from __future__ import annotations
import abc
from typing import ClassVar
from xdsl.ir import SSAValue, Attribute
from xdsl.dialects.builtin import IntegerAttr, IntegerType, IndexType, AnyOf, i32
from xdsl.parser import Parser
from xdsl.printer import Printer
from xdsl.irdl import (
    irdl_op_definition,
    IRDLOperation,
    VarConstraint,
    TypedAttributeConstraint,
    operand_def,
    result_def,
    prop_def,
    traits_def,
)
from xdsl.ir import Operation
from xdsl.traits import Trait
from xdsl.dialects.builtin import StringAttr


# TRAITS COULD BE INTRESTING TO BE EXPLORED MORE OR CUSTOMIZED for quantum operations
# purity makes no sense for quantum register because of: writing in place of the resul on one of the operands, no-cloning theorem
# from xdsl.traits import Pure



################ 
# CUSTOM TRAITS
################

class WriteInPlace(Trait):
    """Trait to enforce that result rewrites the first operand (in-place update)."""
    def verify(self, op: Operation):
        if op.operands[0] is not op.results[0]:
            raise Exception("Operation must write in-place: result must alias lhs.")
        lhs_reg = op.operands[0].owner.properties.get("reg_id")
        result_reg = op.properties.get("reg_id")
        if lhs_reg != result_reg:
            raise Exception(f"reg_id mismatch: lhs={lhs_reg}, result={result_reg}")




################ 
# CHECKS
################

# Matcher used to ensure operands are signless integers or indices.
signlessIntegerLike = AnyOf([IntegerType, IndexType])




@irdl_op_definition
class QuantumInitOp(IRDLOperation):
    """Create and initialize a new quantum register."""

    name = "quantum.init"

    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    result = result_def(T)
    # Initial value of the register stored as a property.
    value = prop_def(TypedAttributeConstraint(IntegerAttr.constr(), T))
    reg_id = prop_def(StringAttr)  # <-- Register id

    assembly_format = "attr-dict $value"

    def __init__(self, value: int | IntegerAttr, reg_id: str, result_type: Attribute = i32):
        """Initialize the operation with ``value`` as the register contents."""
        if isinstance(value, int):
            value = IntegerAttr.from_int_and_width(value, 32)
        super().__init__(
            result_types=[result_type],
            properties={"value": value, "reg_id": StringAttr(reg_id)}  # <-- updated
        )



class QuantumBinaryBase(IRDLOperation, abc.ABC):
    """Base class for binary quantum ops that write in-place to lhs."""

    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    # Both operands and the result share the same integer type ``T``.
    lhs = operand_def(T)
    rhs = operand_def(T)
    result = result_def(T)
    reg_id = prop_def(StringAttr)  # <-- register id

    traits = traits_def(WriteInPlace())

    assembly_format = "$lhs `,` $rhs attr-dict `:` type($result)"

    def __init__(self, lhs: SSAValue, rhs: SSAValue, reg_id: str, result_type: Attribute | None = None):
        """Create the operation using ``lhs`` and ``rhs`` operands."""
        if result_type is None:
            result_type = lhs.type
        super().__init__(
            operands=[lhs, rhs],
            result_types=[result_type],
            properties={"reg_id": StringAttr(reg_id)}  # <-- updated
        )




@irdl_op_definition
class QAddiOp(QuantumBinaryBase):
    """Quantum addition operation."""

    name = "quantum.addi"


@irdl_op_definition
class QSubiOp(QuantumBinaryBase):
    """Quantum subtraction operation."""

    name = "quantum.subi"


@irdl_op_definition
class QMuliOp(QuantumBinaryBase):
    """Quantum multiplication operation."""

    name = "quantum.muli"


@irdl_op_definition
class QDivSOp(QuantumBinaryBase):
    """Quantum signed division operation."""

    name = "quantum.divsi"


class QuantumBinaryImmBase(IRDLOperation, abc.ABC):
    """Quantum binary ops with immediate, in-place write."""

    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    lhs = operand_def(T)
    result = result_def(T)
    imm = prop_def(IntegerAttr)
    reg_id = prop_def(StringAttr)  # <-- NEW

    traits = traits_def(WriteInPlace())
    assembly_format = None

    def __init__(self, lhs: SSAValue, imm: int | IntegerAttr, reg_id: str, result_type: Attribute | None = None):
        """Create a binary operation with an immediate operand."""
        if isinstance(imm, int):
            imm = IntegerAttr.from_int_and_width(imm, 32)
        if result_type is None:
            result_type = lhs.type
        super().__init__(
            operands=[lhs],
            result_types=[result_type],
            properties={
                "imm": imm,
                "reg_id": StringAttr(reg_id)  # <-- updated
            }
        )

    @classmethod
    def parse(cls, parser: Parser):
        lhs = parser.parse_unresolved_operand()
        parser.parse_punctuation(",")
        imm_val = parser.parse_integer()
        parser.parse_optional_attr_dict()
        parser.parse_punctuation(":")
        ty = parser.parse_type()
        (lhs,) = parser.resolve_operands([lhs], [ty], parser.pos)
        return cls(lhs, int(imm_val), ty)

    def print(self, printer: Printer) -> None:
        printer.print(" ")
        printer.print_operand(self.lhs)
        printer.print(", ")
        self.imm.print_without_type(printer)
        printer.print(" : ")
        printer.print_attribute(self.result.type)



@irdl_op_definition
class QAddiImmOp(QuantumBinaryImmBase):
    """Addition with an immediate value."""

    name = "quantum.addi_imm"


@irdl_op_definition
class QSubiImmOp(QuantumBinaryImmBase):
    """Subtraction with an immediate value."""

    name = "quantum.subi_imm"


@irdl_op_definition
class QMuliImmOp(QuantumBinaryImmBase):
    """Multiplication with an immediate value."""

    name = "quantum.muli_imm"


@irdl_op_definition
class QDivSImmOp(QuantumBinaryImmBase):
    """Signed division with an immediate value."""

    name = "quantum.divsi_imm"

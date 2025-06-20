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
from xdsl.traits import Pure

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

    traits = traits_def(Pure())

    assembly_format = "attr-dict $value"

    def __init__(self, value: int | IntegerAttr, result_type: Attribute = i32):
        """Initialize the operation with ``value`` as the register contents."""
        if isinstance(value, int):
            value = IntegerAttr.from_int_and_width(value, 32)
        super().__init__(result_types=[result_type], properties={"value": value})


class QuantumBinaryBase(IRDLOperation, abc.ABC):
    """Common base for binary arithmetic operations."""
    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    # Both operands and the result share the same integer type ``T``.
    lhs = operand_def(T)
    rhs = operand_def(T)
    result = result_def(T)
    traits = traits_def(Pure())
    assembly_format = "$lhs `,` $rhs attr-dict `:` type($result)"

    def __init__(self, lhs: SSAValue, rhs: SSAValue, result_type: Attribute | None = None):
        """Create the operation using ``lhs`` and ``rhs`` operands."""
        if result_type is None:
            result_type = lhs.type
        super().__init__(operands=[lhs, rhs], result_types=[result_type])


@irdl_op_definition
class QAddiOp(QuantumBinaryBase):
    """Quantum addition operation."""

    name = "quant.addi"


@irdl_op_definition
class QSubiOp(QuantumBinaryBase):
    """Quantum subtraction operation."""

    name = "quant.subi"


@irdl_op_definition
class QMuliOp(QuantumBinaryBase):
    """Quantum multiplication operation."""

    name = "quant.muli"


@irdl_op_definition
class QDivSOp(QuantumBinaryBase):
    """Quantum signed division operation."""

    name = "quant.divsi"


class QuantumBinaryImmBase(IRDLOperation, abc.ABC):
    """Base class for binary ops with an immediate operand."""

    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    lhs = operand_def(T)
    result = result_def(T)
    # Immediate operand stored as a property rather than an SSA value.
    imm = prop_def(IntegerAttr)
    traits = traits_def(Pure())
    # Custom print/parse so the immediate value is printed without its type.
    assembly_format = None

    def __init__(self, lhs: SSAValue, imm: int | IntegerAttr, result_type: Attribute | None = None):
        """Create a binary operation with an immediate operand."""
        # Allow passing a Python ``int`` directly for convenience.
        if isinstance(imm, int):
            imm = IntegerAttr.from_int_and_width(imm, 32)
        if result_type is None:
            result_type = lhs.type
        super().__init__(operands=[lhs], result_types=[result_type], properties={"imm": imm})

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

    name = "quant.addi_imm"


@irdl_op_definition
class QSubiImmOp(QuantumBinaryImmBase):
    """Subtraction with an immediate value."""

    name = "quant.subi_imm"


@irdl_op_definition
class QMuliImmOp(QuantumBinaryImmBase):
    """Multiplication with an immediate value."""

    name = "quant.muli_imm"


@irdl_op_definition
class QDivSImmOp(QuantumBinaryImmBase):
    """Signed division with an immediate value."""

    name = "quant.divsi_imm"

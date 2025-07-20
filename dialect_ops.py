# =============================================================================
# Custom IRDL Operations for Immediate Arithmetic
# =============================================================================

"""IRDL operation definitions for arithmetic ops with immediate values.

The standard arithmetic dialect in MLIR does not provide operations that take a
constant immediate operand.  The classes defined here implement such ops using
the `irdl` API so that they integrate nicely with xDSL's type system and
verification facilities.
"""

from __future__ import annotations
import abc
from typing import ClassVar

from xdsl.ir import Operation, SSAValue, Block
from xdsl.irdl import irdl_op_definition, operand_def, attr_def
from xdsl.dialects.builtin import i1
from xdsl.traits import Pure
from xdsl.irdl import successor_def

from xdsl.ir import SSAValue, Attribute
from xdsl.dialects.builtin import IntegerAttr, IntegerType, IndexType, AnyOf
from xdsl.irdl import (
    irdl_op_definition,
    IRDLOperation,
    VarConstraint,
    operand_def,
    result_def,
    prop_def,
    traits_def,
)
from xdsl.dialects.arith import IntegerOverflowAttr
from xdsl.parser import Parser
from xdsl.printer import Printer
from xdsl.traits import Pure
from xdsl.utils.exceptions import VerifyException


# -----------------------------------------------------------------------------
# Type Matcher Utility
# -----------------------------------------------------------------------------

# ``signlessIntegerLike`` matches either an integer or index type.  The helper
# is reused by all operations below for operand and result typing.
signlessIntegerLike = AnyOf([IntegerType, IndexType])


# -----------------------------------------------------------------------------
# Base Classes
# -----------------------------------------------------------------------------

class SignlessIntegerBinaryOpWithImmediate(IRDLOperation, abc.ABC):
    """Base class for binary operations that take an immediate value."""

    name = "iarith.binary_imm"

    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    lhs = operand_def(T)
    result = result_def(T)
    imm = prop_def(IntegerAttr)
    traits = traits_def(Pure())  # Operation has no side effects

    # Custom print/parse replaces assembly format to omit the immediate type.
    assembly_format = None

    def __init__(self, lhs: SSAValue, imm: int | IntegerAttr, result_type: Attribute | None = None):
        """Create the operation with ``lhs`` and an immediate value."""
        # ``imm`` can be provided as a Python int for convenience.  Convert it
        # to an ``IntegerAttr`` using the type of ``lhs``.
        if isinstance(imm, int):
            imm = IntegerAttr(imm, lhs.type)
        if result_type is None:
            result_type = lhs.type
        super().__init__(operands=[lhs], result_types=[result_type], properties={"imm": imm})

    def verify_(self):
        """Check that the immediate has the same type as the operand."""
        # ``irdl`` does not automatically verify property types, so we enforce
        # the immediate to match the operand type here.
        if not isinstance(self.imm, IntegerAttr):
            raise VerifyException("Immediate must be an IntegerAttr")
        if self.lhs.type != self.imm.type:
            raise VerifyException("Operand and immediate must have matching types")

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
        printer.print_attribute(self.lhs.type)

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int | None:
        """Pure Python implementation of the operation used for testing."""
        # Derived classes override this to provide semantics.
        return None

    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        """Return ``True`` if the immediate is a right identity for zero."""
        return False

    @staticmethod
    def is_right_unit(attr: IntegerAttr) -> bool:
        """Return ``True`` if the immediate is a right identity for one."""
        return False


class SignlessIntegerBinaryOpWithImmediateAndOverflow(SignlessIntegerBinaryOpWithImmediate, abc.ABC):
    """Variant supporting overflow flags."""

    name = "iarith.binary_imm_overflow"

    # Optional overflow behavior encoded as a property.
    overflow_flags = prop_def(IntegerOverflowAttr, default_value=IntegerOverflowAttr("none"), prop_name="overflowFlags")
    # Custom print/parse replaces assembly format to omit the immediate type.
    assembly_format = None

    def __init__(
        self,
        lhs: SSAValue,
        imm: int | IntegerAttr,
        result_type: Attribute | None = None,
        overflow: IntegerOverflowAttr = IntegerOverflowAttr("none"),
    ):
        """Create the operation with overflow semantics."""
        if isinstance(imm, int):
            imm = IntegerAttr(imm, lhs.type)
        if result_type is None:
            result_type = lhs.type
        super().__init__(lhs=lhs, imm=imm, result_type=result_type)
        # Store the overflow behavior on the operation instance.
        self.properties["overflowFlags"] = overflow

    @classmethod
    def parse(cls, parser: Parser):
        lhs = parser.parse_unresolved_operand()
        parser.parse_punctuation(",")
        imm_val = parser.parse_integer()
        overflow = IntegerOverflowAttr("none")
        if parser.parse_optional_keyword("overflow") is not None:
            overflow = IntegerOverflowAttr(IntegerOverflowAttr.parse_parameter(parser))
        parser.parse_optional_attr_dict()
        parser.parse_punctuation(":")
        ty = parser.parse_type()
        (lhs,) = parser.resolve_operands([lhs], [ty], parser.pos)
        return cls(lhs, int(imm_val), ty, overflow)

    def print(self, printer: Printer) -> None:
        printer.print(" ")
        printer.print_operand(self.lhs)
        printer.print(", ")
        self.imm.print_without_type(printer)
        if self.overflow_flags.flags:
            printer.print(" overflow")
            self.overflow_flags.print_parameter(printer)
        printer.print(" : ")
        printer.print_attribute(self.lhs.type)


# -----------------------------------------------------------------------------
# Concrete Operations
# -----------------------------------------------------------------------------

@irdl_op_definition
class AddiImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    """Addition with immediate."""

    name = "iarith.addi_imm"
    traits = traits_def(Pure())

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int:
        """Return ``lhs`` plus ``imm``."""
        return lhs + imm

    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        """Check if ``imm`` equals zero."""
        return attr.value.data == 0

    @staticmethod
    def is_right_unit(attr: IntegerAttr) -> bool:
        """Check if ``imm`` is the additive identity (zero)."""
        return attr.value.data == 0


@irdl_op_definition
class SubiImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    """Subtraction with immediate."""

    name = "iarith.subi_imm"
    traits = traits_def(Pure())

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int:
        """Return ``lhs`` minus ``imm``."""
        return lhs - imm

    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        """Check if ``imm`` is zero."""
        return attr.value.data == 0

    @staticmethod
    def is_right_unit(attr: IntegerAttr) -> bool:
        """Check if ``imm`` is zero."""
        return attr.value.data == 0
    
@irdl_op_definition
class BranchOp(IRDLOperation):
    name = "cf.br"

    dest = successor_def()

    def __init__(self, dest: Block):
        super().__init__(successors=[dest])


@irdl_op_definition
class CondBranchOp(IRDLOperation):
    name = "cf.cond_br"

    cond = operand_def(i1)
    true_dest = successor_def()
    false_dest = successor_def()

    def __init__(
        self,
        cond: SSAValue,
        true_block: Block,
        true_args: list[SSAValue],
        false_block: Block,
        false_args: list[SSAValue],
    ):
        super().__init__(
            operands=[cond],
            successors=[true_block, false_block],
        )

@irdl_op_definition
class MuliImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    """Multiplication with immediate."""

    name = "iarith.muli_imm"
    traits = traits_def(Pure())

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int:
        """Return ``lhs`` multiplied by ``imm``."""
        return lhs * imm

    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        """Check if ``imm`` is zero."""
        return attr.value.data == 0

    @staticmethod
    def is_right_unit(attr: IntegerAttr) -> bool:
        """Check if ``imm`` equals one."""
        return attr.value.data == 1


@irdl_op_definition
class DivSImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    """Signed division with immediate."""

    name = "iarith.divsi_imm"
    traits = traits_def(Pure())

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int | None:
        """Return ``lhs`` divided by ``imm`` or ``None`` if dividing by zero."""
        if imm == 0:
            return None
        return lhs // imm

    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        """Division has no zero identity on the right."""
        return False

    @staticmethod
    def is_right_unit(attr: IntegerAttr) -> bool:
        """Check if ``imm`` equals one."""
        return attr.value.data == 1


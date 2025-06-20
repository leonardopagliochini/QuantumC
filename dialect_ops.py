# =============================================================================
# Custom IRDL Operations for Immediate Arithmetic
# =============================================================================

"""IRDL operation definitions for arithmetic ops with immediate values."""

from __future__ import annotations
import abc
from typing import ClassVar

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
from xdsl.traits import Pure
from xdsl.utils.exceptions import VerifyException


# -----------------------------------------------------------------------------
# Type Matcher Utility
# -----------------------------------------------------------------------------

signlessIntegerLike = AnyOf([IntegerType, IndexType])


# -----------------------------------------------------------------------------
# Base Classes
# -----------------------------------------------------------------------------

class SignlessIntegerBinaryOpWithImmediate(IRDLOperation, abc.ABC):
    """Base class for binary operations that take an immediate value."""

    name = "mydialect.binary_imm"

    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    lhs = operand_def(T)
    result = result_def(T)
    imm = prop_def(IntegerAttr)
    traits = traits_def(Pure())

    assembly_format = "$lhs `,` $imm attr-dict `:` type($lhs)"

    def __init__(self, lhs: SSAValue, imm: int | IntegerAttr, result_type: Attribute | None = None):
        """Create the operation with ``lhs`` and an immediate value."""
        if isinstance(imm, int):
            imm = IntegerAttr(imm, lhs.type)
        if result_type is None:
            result_type = lhs.type
        super().__init__(operands=[lhs], result_types=[result_type], properties={"imm": imm})

    def verify_(self):
        """Check that the immediate has the same type as the operand."""
        if not isinstance(self.imm, IntegerAttr):
            raise VerifyException("Immediate must be an IntegerAttr")
        if self.lhs.type != self.imm.type:
            raise VerifyException("Operand and immediate must have matching types")

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int | None:
        """Pure Python implementation of the operation used for testing."""
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

    name = "mydialect.binary_imm_overflow"

    overflow_flags = prop_def(IntegerOverflowAttr, default_value=IntegerOverflowAttr("none"), prop_name="overflowFlags")
    assembly_format = "$lhs `,` $imm (`overflow` `` $overflowFlags^)? attr-dict `:` type($lhs)"

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
        self.properties["overflowFlags"] = overflow


# -----------------------------------------------------------------------------
# Concrete Operations
# -----------------------------------------------------------------------------

@irdl_op_definition
class AddiImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    """Addition with immediate."""

    name = "mydialect.addi_imm"
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

    name = "mydialect.subi_imm"
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
class MuliImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    """Multiplication with immediate."""

    name = "mydialect.muli_imm"
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

    name = "mydialect.divsi_imm"
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


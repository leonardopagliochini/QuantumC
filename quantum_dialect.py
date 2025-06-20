from __future__ import annotations
import abc
from typing import ClassVar
from xdsl.ir import SSAValue, Attribute
from xdsl.dialects.builtin import IntegerAttr, IntegerType, IndexType, AnyOf, i32
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

signlessIntegerLike = AnyOf([IntegerType, IndexType])

@irdl_op_definition
class QuantumInitOp(IRDLOperation):
    name = "quantum.init"

    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    result = result_def(T)
    value = prop_def(TypedAttributeConstraint(IntegerAttr.constr(), T))

    traits = traits_def(Pure())

    assembly_format = "attr-dict $value"

    def __init__(self, value: int | IntegerAttr, result_type: Attribute = i32):
        if isinstance(value, int):
            value = IntegerAttr.from_int_and_width(value, 32)
        super().__init__(result_types=[result_type], properties={"value": value})


class QuantumBinaryBase(IRDLOperation, abc.ABC):
    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    lhs = operand_def(T)
    rhs = operand_def(T)
    result = result_def(T)
    traits = traits_def(Pure())
    assembly_format = "$lhs `,` $rhs attr-dict `:` type($result)"

    def __init__(self, lhs: SSAValue, rhs: SSAValue, result_type: Attribute | None = None):
        if result_type is None:
            result_type = lhs.type
        super().__init__(operands=[lhs, rhs], result_types=[result_type])


@irdl_op_definition
class QAddiOp(QuantumBinaryBase):
    name = "quant.addi"


@irdl_op_definition
class QSubiOp(QuantumBinaryBase):
    name = "quant.subi"


@irdl_op_definition
class QMuliOp(QuantumBinaryBase):
    name = "quant.muli"


@irdl_op_definition
class QDivSOp(QuantumBinaryBase):
    name = "quant.divsi"


class QuantumBinaryImmBase(IRDLOperation, abc.ABC):
    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    lhs = operand_def(T)
    result = result_def(T)
    imm = prop_def(IntegerAttr)
    traits = traits_def(Pure())
    assembly_format = "$lhs `,` $imm attr-dict `:` type($result)"

    def __init__(self, lhs: SSAValue, imm: int | IntegerAttr, result_type: Attribute | None = None):
        if isinstance(imm, int):
            imm = IntegerAttr.from_int_and_width(imm, 32)
        if result_type is None:
            result_type = lhs.type
        super().__init__(operands=[lhs], result_types=[result_type], properties={"imm": imm})

    def __init__(self, lhs: SSAValue, imm: int | IntegerAttr, result_type: Attribute | None = None):
        if isinstance(imm, int):
            imm = IntegerAttr.from_int_and_width(imm, 32)
        if result_type is None:
            result_type = lhs.type
        super().__init__(operands=[lhs], result_types=[result_type], properties={"imm": imm})


@irdl_op_definition
class QAddiImmOp(QuantumBinaryImmBase):
    name = "quant.addi_imm"


@irdl_op_definition
class QSubiImmOp(QuantumBinaryImmBase):
    name = "quant.subi_imm"


@irdl_op_definition
class QMuliImmOp(QuantumBinaryImmBase):
    name = "quant.muli_imm"


@irdl_op_definition
class QDivSImmOp(QuantumBinaryImmBase):
    name = "quant.divsi_imm"
